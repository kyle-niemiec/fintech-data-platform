"""CDC assessed -> bronze Parquet writer.

Zero-transformation: every Debezium/envelope field the assessed message
carries is preserved in the Parquet output so legal reconstruction from
bronze is possible without joining other sources.

Batch flush boundary = one run. The batch's first and last LSN bracket the
data included; replays produce new `run_id`s (and new object paths) rather
than overwriting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import io
import json
import logging
from typing import Any, Protocol
from uuid import UUID, uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from libs.platform_events.envelope import Envelope, EventSource, PipelineClass, PipelineName


TOPIC_ASSESSED = "cdc.oltp.assessed.v1"
TOPIC_BRONZE_READY = "cdc.oltp.bronze.ready.v1"
SOURCE_SYSTEM = "cdc"
INITIATOR = "cdc_bronze_writer"
TRIGGER_TYPE = "cdc_bronze_batch"


@dataclass
class AssessedRecord:
    """Normalized view of a consumed assessed event plus its Kafka coords."""
    envelope: dict[str, Any]
    kafka_topic: str
    kafka_partition: int
    kafka_offset: int


@dataclass
class BatchRow:
    """One row as it lands in bronze Parquet. Mirrors the assessed payload
    plus Kafka coordinates and the upstream Debezium op/before/after."""
    op: str | None
    transaction_id: str | None
    source_table: str | None
    source_lsn: str | None
    source_ts_ms: int | None
    kafka_topic: str
    kafka_partition: int
    kafka_offset: int
    event_id: str
    fraud_rule_version: str | None
    risk_score: float | None
    risk_flags: list[str]
    assessed_payload: str  # JSON blob preserves everything else verbatim


class ObjectStore(Protocol):
    def write_uri(self, uri: str, data: bytes, *, content_type: str, kms_key_id: str) -> None: ...


class EventEmitter(Protocol):
    def produce(self, topic: str, envelope: Envelope, *, key: str) -> tuple[int, int]: ...


def assessed_record_to_row(rec: AssessedRecord) -> BatchRow:
    env = rec.envelope
    payload = env.get("payload") or {}
    orig = payload.get("original_topic_metadata") or {}
    return BatchRow(
        op=payload.get("op"),
        transaction_id=payload.get("transaction_id"),
        source_table=payload.get("source_table"),
        source_lsn=orig.get("lsn"),
        source_ts_ms=orig.get("source_ts_ms"),
        kafka_topic=rec.kafka_topic,
        kafka_partition=rec.kafka_partition,
        kafka_offset=rec.kafka_offset,
        event_id=str(env.get("event_id")),
        fraud_rule_version=payload.get("fraud_rule_version"),
        risk_score=_coerce_float(payload.get("risk_score")),
        risk_flags=list(payload.get("risk_flags") or []),
        assessed_payload=json.dumps(payload, sort_keys=True, separators=(",", ":")),
    )


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def rows_to_parquet_bytes(rows: list[BatchRow]) -> bytes:
    table = pa.table({
        "op": [r.op for r in rows],
        "transaction_id": [r.transaction_id for r in rows],
        "source_table": [r.source_table for r in rows],
        "source_lsn": [r.source_lsn for r in rows],
        "source_ts_ms": [r.source_ts_ms for r in rows],
        "kafka_topic": [r.kafka_topic for r in rows],
        "kafka_partition": [r.kafka_partition for r in rows],
        "kafka_offset": [r.kafka_offset for r in rows],
        "event_id": [r.event_id for r in rows],
        "fraud_rule_version": [r.fraud_rule_version for r in rows],
        "risk_score": [r.risk_score for r in rows],
        "risk_flags": [r.risk_flags for r in rows],
        "assessed_payload": [r.assessed_payload for r in rows],
    })
    buf = io.BytesIO()
    pq.write_table(table, buf)
    return buf.getvalue()


def bronze_object_key(
    *, bucket: str, source_table: str, run_id: UUID, written_at: datetime
) -> str:
    dt = written_at.astimezone(timezone.utc)
    return (
        f"bronze/source=cdc/table={source_table}"
        f"/year={dt.year:04d}/month={dt.month:02d}/day={dt.day:02d}/hour={dt.hour:02d}"
        f"/run_id={run_id}/part-0.parquet"
    )


def bronze_uri(*, bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


def _sort_key(row: BatchRow) -> tuple:
    # LSN is a hex-ish string (e.g. "0/16B5C10"); compare lexicographically
    # with a None-safe prefix, then fall back to Kafka offset for ordering
    # within the same LSN or when LSN is missing.
    return (row.source_lsn is None, row.source_lsn or "", row.kafka_offset)


@dataclass
class CdcBronzeWriter:
    store: ObjectStore
    producer: EventEmitter
    kms_key_id: str
    bucket: str

    def build_flush(self, records: list[AssessedRecord]) -> "FlushResult":
        rows = [assessed_record_to_row(r) for r in records]
        # Group by source_table. Each table gets its own Parquet object.
        by_table: dict[str, list[BatchRow]] = {}
        for row in rows:
            key = row.source_table or "unknown"
            by_table.setdefault(key, []).append(row)
        for table_rows in by_table.values():
            table_rows.sort(key=_sort_key)
        return FlushResult(by_table=by_table, records=records)

    def write_and_emit(
        self, flush: "FlushResult", *, now: datetime | None = None
    ) -> list["EmittedBatch"]:
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        emitted: list[EmittedBatch] = []

        for source_table, rows in flush.by_table.items():
            parquet_bytes = rows_to_parquet_bytes(rows)
            run_id = uuid4()
            trace_id = uuid4()
            key = bronze_object_key(
                bucket=self.bucket,
                source_table=source_table,
                run_id=run_id,
                written_at=moment,
            )
            uri = bronze_uri(bucket=self.bucket, key=key)

            self.store.write_uri(
                uri,
                parquet_bytes,
                content_type="application/octet-stream",
                kms_key_id=self.kms_key_id,
            )

            first_lsn = rows[0].source_lsn
            last_lsn = rows[-1].source_lsn
            kafka_offsets = [r.kafka_offset for r in rows]
            kafka_partitions = sorted({r.kafka_partition for r in rows})
            input_uris = sorted({
                f"kafka://{r.kafka_topic}/{r.kafka_partition}/{r.kafka_offset}"
                for r in rows
            })
            trigger_event_ref = (
                f"cdc_bronze_batch:{source_table}:"
                f"{kafka_partitions[0]}:{kafka_offsets[0]}-{kafka_offsets[-1]}"
            )

            envelope = Envelope.build(
                event_type=TOPIC_BRONZE_READY,
                source=EventSource.cdc,
                run_id=run_id,
                pipeline_class=PipelineClass.ingestion,
                pipeline_name=PipelineName.cdc_bronze_write,
                trigger_event_ref=trigger_event_ref,
                trace_id=trace_id,
                payload={
                    "stage": "bronze",
                    "format": "parquet",
                    "input_uris": input_uris,
                    "output_uris": [uri],
                    "record_count": len(rows),
                    "first_lsn": first_lsn,
                    "last_lsn": last_lsn,
                    "source_table": source_table,
                },
            )
            partition, offset = self.producer.produce(
                TOPIC_BRONZE_READY, envelope, key=f"{source_table}:{run_id}"
            )

            emitted.append(
                EmittedBatch(
                    run_id=run_id,
                    source_table=source_table,
                    first_lsn=first_lsn,
                    last_lsn=last_lsn,
                    kafka_partition=kafka_partitions[0],
                    offset_start=min(kafka_offsets),
                    offset_end=max(kafka_offsets),
                    record_count=len(rows),
                    bronze_uri=uri,
                    envelope=envelope,
                    produce_partition=partition,
                    produce_offset=offset,
                    trigger_event_ref=trigger_event_ref,
                )
            )

        return emitted


@dataclass
class FlushResult:
    by_table: dict[str, list[BatchRow]] = field(default_factory=dict)
    records: list[AssessedRecord] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.by_table


@dataclass
class EmittedBatch:
    run_id: UUID
    source_table: str
    first_lsn: str | None
    last_lsn: str | None
    kafka_partition: int
    offset_start: int
    offset_end: int
    record_count: int
    bronze_uri: str
    envelope: Envelope
    produce_partition: int
    produce_offset: int
    trigger_event_ref: str
