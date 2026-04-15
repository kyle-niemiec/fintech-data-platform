"""Fraud worker handler: Debezium raw -> risk_flag + assessed envelope.

Failure ordering is deliberate:
    1. OLTP `risk_flag` upsert (idempotent via unique(raw_topic, raw_partition, raw_offset))
    2. Produce `cdc.oltp.assessed.v1`
    3. `append_event` + `close_run` on event-store
    4. Kafka commit (caller's responsibility)

Any failure before step 4 causes Kafka to redeliver. Step 1 no-ops on replay;
steps 2-3 are idempotent via the event-log dedupe key.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
from typing import Any, Protocol
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from libs.platform_events.envelope import Envelope, EventSource, PipelineClass, PipelineName
from libs.platform_events.event_store import append_event, close_run, open_run, raise_alert

from .scorer import RiskAssessment, score_transaction

logger = logging.getLogger(__name__)

TOPIC_ASSESSED = "cdc.oltp.assessed.v1"
TRIGGER_TYPE = "cdc_raw_event"
INITIATOR = "fraud_worker"
SOURCE_SYSTEM = "oltp_postgres"


class EventEmitter(Protocol):
    def produce(self, topic: str, envelope: Envelope, *, key: str) -> tuple[int, int]: ...


@dataclass
class RawMessage:
    """What the handler needs from a Debezium raw record."""
    topic: str
    partition: int
    offset: int
    value: dict[str, Any]
    key: str | None


def _extract_debezium_fields(value: dict[str, Any]) -> dict[str, Any]:
    """Pull the `payload` body from a Debezium envelope.

    Debezium Postgres emits `{schema, payload}`; with JSON schema stripping it
    may also emit just the payload. Handle both.
    """
    if "payload" in value and isinstance(value["payload"], dict):
        return value["payload"]
    return value


def parse_raw(raw: RawMessage) -> dict[str, Any] | None:
    """Return the parsed row dict (from `after`, or `before` on delete).

    Returns None if the envelope is not a known transaction change (e.g. a
    tombstone or a change against a table other than trading.transaction).
    """
    payload = _extract_debezium_fields(raw.value)
    op = payload.get("op")
    if op not in ("c", "u", "r", "d"):
        return None

    source = payload.get("source") or {}
    source_table = f"{source.get('schema', '')}.{source.get('table', '')}"
    if source_table != "trading.transaction":
        # risk_flag changes loop back through CDC; we only score transactions.
        return None

    after = payload.get("after")
    before = payload.get("before")
    row = after if op != "d" else before
    if not isinstance(row, dict):
        return None

    return {
        "op": op,
        "source_ts_ms": payload.get("ts_ms") or source.get("ts_ms"),
        "lsn": source.get("lsn"),
        "source_table": source_table,
        "row": row,
    }


def _upsert_risk_flag(
    oltp_conn: psycopg.Connection,
    *,
    transaction_id: str,
    event_id: UUID,
    assessment: RiskAssessment,
    raw: RawMessage,
) -> bool:
    """Insert risk_flag row. Returns True if inserted, False if replay dedupe."""
    with oltp_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO trading.risk_flag (
                transaction_id, event_id, fraud_rule_version,
                risk_score, risk_flags,
                raw_topic, raw_partition, raw_offset
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (raw_topic, raw_partition, raw_offset) DO NOTHING
            RETURNING risk_flag_id
            """,
            (
                transaction_id,
                str(event_id),
                assessment.fraud_rule_version,
                assessment.risk_score,
                Jsonb(assessment.risk_flags),
                raw.topic,
                raw.partition,
                raw.offset,
            ),
        )
        return cur.fetchone() is not None


@dataclass
class FraudHandler:
    oltp_conn: psycopg.Connection
    event_store_conn: psycopg.Connection
    producer: EventEmitter

    def handle(self, raw: RawMessage) -> bool:
        """Returns True if a new assessed event was emitted (i.e. not a skip)."""
        parsed = parse_raw(raw)
        if parsed is None:
            return False

        row = parsed["row"]
        transaction_id = str(row.get("transaction_id"))
        if not transaction_id or transaction_id == "None":
            logger.warning(
                "skip raw without transaction_id topic=%s partition=%s offset=%s",
                raw.topic, raw.partition, raw.offset,
            )
            return False

        assessment = score_transaction(row)
        event_id = uuid4()
        run_id = uuid4()
        trace_id = uuid4()
        trigger_event_ref = f"{raw.topic}:{raw.partition}:{raw.offset}"

        # Idempotent OLTP write first; replays no-op here.
        try:
            self.oltp_conn.autocommit = True
            _upsert_risk_flag(
                self.oltp_conn,
                transaction_id=transaction_id,
                event_id=event_id,
                assessment=assessment,
                raw=raw,
            )
        except Exception:
            logger.exception(
                "risk_flag upsert failed topic=%s partition=%s offset=%s",
                raw.topic, raw.partition, raw.offset,
            )
            raise

        # Open/append/close run on event-store in one transaction.
        try:
            effective_run_id = open_run(
                self.event_store_conn,
                run_id=run_id,
                pipeline_class=PipelineClass.ingestion,
                pipeline_name=PipelineName.cdc_ingestion,
                source_system=SOURCE_SYSTEM,
                trigger_type=TRIGGER_TYPE,
                trigger_event_ref=trigger_event_ref,
                initiator=INITIATOR,
            )
        except Exception:
            self.event_store_conn.rollback()
            raise

        envelope = Envelope.build(
            event_id=event_id,
            event_type=TOPIC_ASSESSED,
            source=EventSource.cdc,
            run_id=effective_run_id,
            pipeline_class=PipelineClass.ingestion,
            pipeline_name=PipelineName.cdc_ingestion,
            trigger_event_ref=trigger_event_ref,
            trace_id=trace_id,
            payload={
                "risk_score": _decimal_to_float(assessment.risk_score),
                "risk_flags": assessment.risk_flags,
                "fraud_rule_version": assessment.fraud_rule_version,
                "transaction_id": transaction_id,
                "op": parsed["op"],
                "source_table": parsed["source_table"],
                "original_topic_metadata": {
                    "topic": raw.topic,
                    "partition": raw.partition,
                    "offset": raw.offset,
                    "lsn": parsed["lsn"],
                    "source_ts_ms": parsed["source_ts_ms"],
                },
            },
        )

        try:
            partition, offset = self.producer.produce(
                TOPIC_ASSESSED, envelope, key=f"{parsed['source_table']}:{transaction_id}"
            )
        except Exception:
            try:
                raise_alert(
                    self.event_store_conn,
                    run_id=effective_run_id,
                    severity="high",
                    category="cdc_assessed_produce_failed",
                    summary="fraud worker failed to produce assessed event",
                    details={"raw": trigger_event_ref},
                    occurred_at=datetime.now(timezone.utc),
                )
                close_run(self.event_store_conn, effective_run_id, status="failed")
                self.event_store_conn.commit()
            except Exception:
                self.event_store_conn.rollback()
            raise

        try:
            with self.event_store_conn.transaction():
                append_event(
                    self.event_store_conn,
                    envelope,
                    topic=TOPIC_ASSESSED,
                    partition=partition,
                    kafka_offset=offset,
                )
                close_run(self.event_store_conn, effective_run_id, status="completed")
        except Exception:
            raise

        return True


def _decimal_to_float(value: Decimal) -> float:
    # payload JSON must round-trip; floats are acceptable here because the
    # authoritative numeric is stored in risk_flag.risk_score (NUMERIC).
    return float(value)


def decode_message(value_bytes: bytes) -> dict[str, Any]:
    return json.loads(value_bytes.decode("utf-8"))
