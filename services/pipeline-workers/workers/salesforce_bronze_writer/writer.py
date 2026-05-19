"""Salesforce raw JSON -> bronze Parquet writer.

Consumes one `ingest.salesforce.raw.ready.v1` event at a time. Each event
carries the `output_uris` list of raw JSON pages produced by the pull DAG
for a single (run_id, sobject) pull. For each event the writer:

  1. Reads all raw JSON pages and flattens their `records` arrays.
  2. Writes a single Parquet object to bronze/source=salesforce/object=X/...
     (SSE-KMS).
  3. Emits `ingest.salesforce.bronze.ready.v1`.
  4. In one DB transaction: append_event, append_sf_cursor_checkpoint,
     PgEventStore.close_run(status='completed').

Zero-record events close the run without writing Parquet or advancing
the cursor (no checkpoint row).
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import UUID

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq

from libs.platform_events.envelope import Envelope, EventSource, PipelineClass, PipelineName
from libs.platform_events.event_store import PgEventStore

logger = logging.getLogger("salesforce_bronze_writer")

TOPIC_RAW_READY = "ingest.salesforce.raw.ready.v1"
TOPIC_BRONZE_READY = "ingest.salesforce.bronze.ready.v1"
TRANSFORM_ID = "salesforce_json_to_parquet"
TRANSFORM_VERSION = "v1"


def split_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"invalid s3 uri: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def raw_uri_to_bronze_uri(raw_uri: str) -> str:
    """raw/source=salesforce/object=X/year=.../run_id=.../page-NNNN.json
    -> bronze/source=salesforce/object=X/year=.../run_id=.../part-0.parquet"""
    bucket, key = split_s3_uri(raw_uri)
    if not key.startswith("raw/source=salesforce/"):
        raise ValueError(f"raw uri is not salesforce raw path: {raw_uri}")
    bronze_prefix = key.replace("raw/source=salesforce/", "bronze/source=salesforce/", 1)
    parent, _sep, _leaf = bronze_prefix.rpartition("/")
    bronze_key = f"{parent}/part-0.parquet" if parent else "part-0.parquet"
    return f"s3://{bucket}/{bronze_key}"


class ObjectStore(Protocol):
    def read_uri(self, uri: str) -> bytes: ...
    def write_uri(self, uri: str, data: bytes, *, content_type: str, kms_key_id: str) -> None: ...


class EventEmitter(Protocol):
    def produce(self, topic: str, envelope: Envelope, *, key: str) -> tuple[int, int]: ...


@dataclass
class RawReadyMessage:
    envelope: dict[str, Any]
    kafka_topic: str
    kafka_partition: int
    kafka_offset: int


def records_to_parquet(records: list[dict[str, Any]]) -> tuple[bytes, str]:
    """Flatten a list of SObject record dicts into Parquet.

    All non-primitive values (nested dicts/lists like `attributes`) are
    preserved as JSON strings so the bronze layer stays zero-transformation.
    """
    if not records:
        raise ValueError("records_to_parquet requires at least one record")

    keys: list[str] = []
    seen: set[str] = set()
    for rec in records:
        for k in rec.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)

    columns: dict[str, list[Any]] = {k: [] for k in keys}
    for rec in records:
        for k in keys:
            v = rec.get(k)
            if isinstance(v, (dict, list)):
                columns[k].append(json.dumps(v, sort_keys=True, separators=(",", ":"), default=str))
            else:
                columns[k].append(v)

    table = pa.table(columns)
    out = io.BytesIO()
    pq.write_table(table, out, compression="snappy")
    signature = "|".join(f"{name}:{str(table.schema.field(name).type)}" for name in keys)
    fingerprint = "sha256-" + hashlib.sha256(signature.encode("utf-8")).hexdigest()
    return out.getvalue(), fingerprint


def _parse_cursor_ts(raw: str) -> datetime:
    ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


@dataclass
class SalesforceBronzeWriter:
    store: ObjectStore
    producer: EventEmitter
    db: psycopg.Connection
    kms_key_id: str

    def handle_raw_ready(self, msg: RawReadyMessage) -> bool:
        envelope = msg.envelope
        payload = envelope.get("payload") or {}
        run_id = UUID(str(envelope["run_id"]))
        trace_id = UUID(str(envelope["trace_id"]))
        trigger_event_ref = str(envelope["trigger_event_ref"])
        sobject = str(payload["sobject"])
        raw_uris: list[str] = list(payload.get("output_uris") or [])
        row_count_reported = int(payload.get("row_count") or 0)

        if row_count_reported == 0 or not raw_uris:
            with self.db.transaction():
                PgEventStore.close_run(self.db, run_id, status="completed")
            logger.info("salesforce raw.ready with zero rows closed run run_id=%s sobject=%s", run_id, sobject)
            return True

        try:
            records: list[dict[str, Any]] = []
            for uri in raw_uris:
                body = self.store.read_uri(uri)
                page = json.loads(body)
                records.extend(page.get("records") or [])

            if not records:
                with self.db.transaction():
                    PgEventStore.close_run(self.db, run_id, status="completed")
                return True

            parquet_bytes, schema_fingerprint = records_to_parquet(records)
            bronze_uri = raw_uri_to_bronze_uri(raw_uris[0])
            self.store.write_uri(
                bronze_uri,
                parquet_bytes,
                content_type="application/octet-stream",
                kms_key_id=self.kms_key_id,
            )

            last = records[-1]
            cursor_ts = _parse_cursor_ts(str(last["SystemModstamp"]))
            cursor_id = str(last["Id"])

            bronze_envelope = Envelope.build(
                event_type=TOPIC_BRONZE_READY,
                source=EventSource.salesforce,
                run_id=run_id,
                pipeline_class=PipelineClass.ingestion,
                pipeline_name=PipelineName.salesforce_ingestion,
                trigger_event_ref=trigger_event_ref,
                trace_id=trace_id,
                payload={
                    "message": f"Salesforce {sobject} raw transformed to bronze parquet: {bronze_uri}",
                    "stage": "bronze",
                    "format": "parquet",
                    "sobject": sobject,
                    "input_uris": raw_uris,
                    "output_uris": [bronze_uri],
                    "record_count": len(records),
                    "parquet_schema_fingerprint": schema_fingerprint,
                    "advanced_cursor_ts": cursor_ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "advanced_cursor_id": cursor_id,
                    "transform_id": TRANSFORM_ID,
                    "transform_version": TRANSFORM_VERSION,
                },
            )
            partition, offset = self.producer.produce(
                TOPIC_BRONZE_READY, bronze_envelope, key=f"{sobject}:{run_id}"
            )
            with self.db.transaction():
                PgEventStore.append_event(
                    self.db,
                    bronze_envelope,
                    topic=TOPIC_BRONZE_READY,
                    partition=partition,
                    kafka_offset=offset,
                )
                PgEventStore.append_sf_cursor_checkpoint(
                    self.db,
                    run_id=run_id,
                    sobject=sobject,
                    cursor_ts=cursor_ts,
                    cursor_id=cursor_id,
                    kafka_partition=msg.kafka_partition,
                    offset_start=msg.kafka_offset,
                    offset_end=msg.kafka_offset,
                    record_count=len(records),
                )
                PgEventStore.close_run(self.db, run_id, status="completed")
            return True

        except Exception as exc:
            logger.exception("salesforce bronze write failed run_id=%s sobject=%s", run_id, sobject)
            try:
                with self.db.transaction():
                    PgEventStore.raise_alert(
                        self.db,
                        run_id=run_id,
                        severity="high",
                        category="salesforce_bronze_write_failed",
                        summary="Salesforce bronze write failed",
                        details={"error": str(exc), "sobject": sobject, "raw_uris": raw_uris},
                        occurred_at=datetime.now(timezone.utc),
                    )
                    PgEventStore.close_run(self.db, run_id, status="failed")
            except Exception:
                logger.exception("alert/close_run also failed for run_id=%s", run_id)
            return False
