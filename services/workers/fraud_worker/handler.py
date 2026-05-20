"""
Fraud worker handler: Debezium raw -> risk_flag + assessed envelope.

Failure ordering is deliberate:
    1. OLTP `risk_flag` upsert (idempotent via unique(raw_topic, raw_partition, raw_offset))
    2. `open_run` + internal started event append on event-store
    3. Produce `cdc.oltp.assessed.v1`
    4. `append_event` + `close_run` on event-store
    5. Kafka commit (caller's responsibility)

Any failure before step 5 causes Kafka to redeliver. Step 1 no-ops on replay;
steps 3-4 are idempotent via the event-log dedupe key.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import text

from meridian.libs.redpanda_events.envelope import Envelope, EventSource, PipelineClass, PipelineName
from meridian.libs.event_store import ManagedConnection, PgEventStore

from .scorer import RiskAssessment, score_transaction

logger = logging.getLogger(__name__)

TOPIC_ASSESSED = "cdc.oltp.assessed.v1"
TOPIC_INTERNAL = "event_store.internal"
TOPIC_ASSESSED_STARTED = "cdc.oltp.assessed.started.v1"
TRIGGER_TYPE = "cdc_raw_event"
INITIATOR = "fraud_worker"
SOURCE_SYSTEM = "cdc"
FRAUD_RULE_LABEL = "demo_continuous_risk"


class EventEmitter(Protocol):
    def produce(self, topic: str, envelope: Envelope, *, key: str) -> tuple[int, int]: ...


@dataclass
class RawMessage:
    """
    What the handler needs from a Debezium raw record.
    """
    topic: str
    partition: int
    offset: int
    value: dict[str, Any]
    key: str | None


def _extract_debezium_fields(value: dict[str, Any]) -> dict[str, Any]:
    """
    Pull the `payload` body from a Debezium envelope.

    Debezium Postgres emits `{schema, payload}`; with JSON schema stripping it
    may also emit just the payload. Handle both.
    """
    if "payload" in value and isinstance(value["payload"], dict):
        return value["payload"]

    return value


def parse_raw(raw: RawMessage) -> dict[str, Any] | None:
    """
    Return the parsed row dict (from `after`, or `before` on delete).

    Returns None if the envelope is not a known transaction change (e.g. a
    tombstone or a change against a table other than trading.transaction).
    """
    payload = _extract_debezium_fields(raw.value)
    op = payload.get("op")

    if op not in ("c", "u", "r", "d"):
        return None

    source = payload.get("source") or {}
    source_table = f"{source.get('schema', '')}.{source.get('table', '')}"

    if source_table not in (
        "trading.transaction",
        "trading.loan",
        "trading.loan_payment",
        "trading.loan_status_history",
    ):
        # risk_flag and unrelated table changes loop back through CDC; skip them.
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
    oltp_conn: ManagedConnection,
    *,
    transaction_id: str,
    event_id: UUID,
    assessment: RiskAssessment,
    raw: RawMessage,
) -> bool:
    """
    Insert risk_flag row. Returns True if inserted, False if replay dedupe.
    """
    # TECH-DEBT: SQL statements should be in separate files
    row = oltp_conn.execute(
        text(
            """
            INSERT INTO trading.risk_flag (
                transaction_id, event_id, fraud_rule_version,
                risk_score, risk_flags,
                raw_topic, raw_partition, raw_offset
            )
            VALUES (
                :transaction_id,
                :event_id,
                :fraud_rule_version,
                :risk_score,
                CAST(:risk_flags AS jsonb),
                :raw_topic,
                :raw_partition,
                :raw_offset
            )
            ON CONFLICT (raw_topic, raw_partition, raw_offset) DO NOTHING
            RETURNING risk_flag_id
            """
        ),
        {
            "transaction_id": transaction_id,
            "event_id": str(event_id),
            "fraud_rule_version": FRAUD_RULE_LABEL,
            "risk_score": assessment.risk_score,
            "risk_flags": json.dumps(assessment.risk_flags, separators=(",", ":")),
            "raw_topic": raw.topic,
            "raw_partition": raw.partition,
            "raw_offset": raw.offset,
        },
    ).fetchone()

    return row is not None


@dataclass
class FraudHandler:
    """
    Handler for Debezium raw messages. Responsibilities:
    1. Parse raw message and skip if not a transaction-related change.
    2. Score transaction changes; assign default assessment for non-transaction changes.
    3. Idempotently upsert risk_flag for transaction changes.
    4. Emit assessed event to Kafka with risk assessment and metadata.
    5. Log event in event-store with dedupe key (topic+partition+offset) to prevent duplicate emits on replay.
    """
    oltp_conn: ManagedConnection
    event_store_conn: ManagedConnection
    producer: EventEmitter


    def handle(self, raw: RawMessage) -> bool:
        """
        Returns True if a new assessed event was emitted (i.e. not a skip).

        TECH-DEBT: This method is doing a lot; consider splitting into smaller methods or functions.
        """
        parsed = parse_raw(raw)

        if parsed is None:
            return False

        row = parsed["row"]
        transaction_id = str(row.get("transaction_id"))
        source_table = str(parsed["source_table"])
        business_key = transaction_id

        if source_table == "trading.loan":
            business_key = str(row.get("loan_id"))
        elif source_table == "trading.loan_payment":
            business_key = str(row.get("payment_id"))
        elif source_table == "trading.loan_status_history":
            business_key = str(row.get("status_event_id"))

        if not business_key or business_key == "None":
            logger.warning(
                "skip raw without business key topic=%s partition=%s offset=%s",
                raw.topic, raw.partition, raw.offset,
            )

            return False

        assessment = score_transaction(row) if source_table == "trading.transaction" else RiskAssessment(risk_score=0, risk_flags=[])
        event_id = uuid4()
        run_id = uuid4()
        trace_id = uuid4()
        trigger_event_ref = f"{raw.topic}:{raw.partition}:{raw.offset}"

        if source_table == "trading.transaction":
            # Idempotent OLTP write first; replays no-op here.
            try:
                with self.oltp_conn.begin():
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

        # Open run and write a first internal event-log row in one transaction.
        with self.event_store_conn.begin():
            effective_run_id = PgEventStore.open_run(
                self.event_store_conn,
                run_id=run_id,
                pipeline_class=PipelineClass.ingestion,
                pipeline_name=PipelineName.cdc_ingestion,
                source_system=SOURCE_SYSTEM,
                trigger_type=TRIGGER_TYPE,
                trigger_event_ref=trigger_event_ref,
                initiator=INITIATOR,
            )

            started_envelope = Envelope.build(
                event_type=TOPIC_ASSESSED_STARTED,
                source=EventSource.cdc,
                run_id=effective_run_id,
                pipeline_class=PipelineClass.ingestion,
                pipeline_name=PipelineName.cdc_ingestion,
                trigger_event_ref=trigger_event_ref,
                trace_id=trace_id,
                payload={
                    "stage": "assessed",
                    "state": "started",
                    "source_table": parsed["source_table"],
                    "topic": raw.topic,
                    "partition": raw.partition,
                    "offset": raw.offset,
                },
            )

            PgEventStore.append_event(
                self.event_store_conn,
                started_envelope,
                topic=TOPIC_INTERNAL,
                partition=-1,
                kafka_offset=-1,
            )

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
                "fraud_rule_version": FRAUD_RULE_LABEL,
                "transaction_id": transaction_id,
                "account_id": row.get("account_id"),
                "loan_id": row.get("loan_id"),
                "payment_id": row.get("payment_id"),
                "payment_amount": _decimal_to_float(row.get("amount")) if source_table == "trading.loan_payment" else None,
                "payment_due_date": str(row.get("due_date")) if row.get("due_date") is not None else None,
                "payment_posted_at": str(row.get("posted_at")) if row.get("posted_at") is not None else None,
                "status_code": row.get("status_code"),
                "status_at": str(row.get("status_at")) if row.get("status_at") is not None else None,
                "principal_balance": _decimal_to_float(row.get("principal_balance")) if row.get("principal_balance") is not None else None,
                "days_past_due": int(row.get("days_past_due")) if row.get("days_past_due") is not None else None,
                "commission_adjustment_amount": None,
                "commission_reason": None,
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
                TOPIC_ASSESSED, envelope, key=f"{parsed['source_table']}:{business_key}"
            )
        except Exception:
            with self.event_store_conn.begin():
                PgEventStore.raise_alert(
                    self.event_store_conn,
                    run_id=effective_run_id,
                    severity="high",
                    category="cdc_assessed_produce_failed",
                    summary="fraud worker failed to produce assessed event",
                    details={"raw": trigger_event_ref},
                    occurred_at=datetime.now(timezone.utc),
                )
                PgEventStore.close_run(self.event_store_conn, effective_run_id, status="failed")
            raise

        with self.event_store_conn.begin():
            PgEventStore.append_event(
                self.event_store_conn,
                envelope,
                topic=TOPIC_ASSESSED,
                partition=partition,
                kafka_offset=offset,
            )

            PgEventStore.close_run(self.event_store_conn, effective_run_id, status="completed")

        return True


def _decimal_to_float(value: Decimal) -> float:
    # payload JSON must round-trip; floats are acceptable here because the
    # authoritative numeric is stored in risk_flag.risk_score (NUMERIC).
    return float(value)


def decode_message(value_bytes: bytes) -> dict[str, Any]:
    return json.loads(value_bytes.decode("utf-8"))
