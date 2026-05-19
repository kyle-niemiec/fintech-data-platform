"""
Event-store helpers for writing to event_store via SQLAlchemy text statements.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional
from uuid import UUID

from psycopg.types.json import Jsonb

from .envelope import Envelope, PipelineClass, PipelineName
from .event_store_sql import SqlStatement, load_event_store_statements

_EVENT_STORE_SQL: dict[str, SqlStatement] = load_event_store_statements()


def _execute(conn: Any, statement_name: str, params: Mapping[str, Any]):
    """
    Execute a named statement with params, validating that all expected binds
    are provided.
    """
    statement = _EVENT_STORE_SQL[statement_name]
    provided = frozenset(params.keys())

    if provided != statement.bind_names:
        raise RuntimeError(
            "event-store SQL bind mismatch for "
            f"{statement_name}: expected {sorted(statement.bind_names)} got {sorted(provided)}"
        )

    return conn.execute(statement.text_clause, dict(params))


class PgEventStore:
    """
    Namespace API for event-store helpers.
    """

    @staticmethod
    def open_run(
        conn: Any,
        *,
        run_id: UUID,
        pipeline_class: PipelineClass | str,
        pipeline_name: PipelineName | str,
        source_system: str,
        trigger_type: str,
        trigger_event_ref: str,
        initiator: str,
        status: str = "running",
        parent_run_id: Optional[UUID] = None,
    ) -> UUID:
        """
        Idempotently create a pipeline_run. Returns the effective run_id.

        If a run already exists for (pipeline_name, trigger_event_ref), its
        existing run_id is returned and the caller's `run_id` argument is
        ignored. Callers must use the returned value on subsequent events.
        """
        pipeline_class_v = pipeline_class.value if isinstance(pipeline_class, PipelineClass) else pipeline_class
        pipeline_name_v = pipeline_name.value if isinstance(pipeline_name, PipelineName) else pipeline_name

        row = _execute(
            conn,
            "open_run_insert",
            {
                "run_id": str(run_id),
                "pipeline_class": pipeline_class_v,
                "pipeline_name": pipeline_name_v,
                "source_system": source_system,
                "trigger_type": trigger_type,
                "trigger_event_ref": trigger_event_ref,
                "status": status,
                "initiator": initiator,
                "parent_run_id": str(parent_run_id) if parent_run_id else None,
            },
        ).fetchone()

        if row is not None:
            return UUID(str(row[0]))

        existing = _execute(
            conn,
            "open_run_select_existing",
            {
                "pipeline_name": pipeline_name_v,
                "trigger_event_ref": trigger_event_ref,
            },
        ).fetchone()

        if existing is None:
            raise RuntimeError(
                "open_run conflict but existing row not found — schema invariant violated"
            )
        return UUID(str(existing[0]))

    @staticmethod
    def append_event(
        conn: Any,
        envelope: Envelope,
        *,
        topic: str,
        partition: int,
        kafka_offset: int,
    ) -> bool:
        """
        Append one event_log row. Returns True if inserted, False if deduped.

        Dedupe is by (topic, partition, kafka_offset, occurred_at). occurred_at is
        included because event_log is partitioned by occurred_at and Postgres
        requires the partition key to appear in any parent-level unique constraint
        used as an ON CONFLICT target.
        """
        row = _execute(
            conn,
            "append_event",
            {
                "event_id": str(envelope.event_id),
                "run_id": str(envelope.run_id),
                "event_type": envelope.event_type,
                "topic": topic,
                "partition": partition,
                "kafka_offset": kafka_offset,
                "occurred_at": envelope.occurred_at,
                "trace_id": str(envelope.trace_id) if envelope.trace_id else None,
                "payload": Jsonb(envelope.payload),
                "payload_hash": envelope.payload_hash,
                "schema_version": envelope.schema_version,
            },
        ).fetchone()
        return row is not None

    @staticmethod
    def close_run(
        conn: Any,
        run_id: UUID,
        *,
        status: str,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """
        Close a run by setting its status and completed_at.
        """
        _execute(
            conn,
            "close_run",
            {
                "run_id": str(run_id),
                "status": status,
                "completed_at": completed_at or datetime.now(timezone.utc),
            },
        )

    @staticmethod
    def raise_alert(
        conn: Any,
        *,
        run_id: UUID,
        severity: str,
        category: str,
        summary: str,
        details: dict[str, Any],
        occurred_at: Optional[datetime] = None,
    ) -> None:
        """
        Create an alert_event linked to a run. Alerts are for human consumption
        and have no schema requirements on details.
        """
        _execute(
            conn,
            "raise_alert",
            {
                "run_id": str(run_id),
                "severity": severity,
                "category": category,
                "summary": summary,
                "details": Jsonb(details),
                "occurred_at": occurred_at or datetime.now(timezone.utc),
            },
        )

    @staticmethod
    def append_cdc_checkpoint(
        conn: Any,
        *,
        run_id: UUID,
        source_table: str,
        lsn_start: Optional[str],
        lsn_end: Optional[str],
        kafka_partition: int,
        offset_start: int,
        offset_end: int,
        record_count: int,
    ) -> None:
        """
        Append a CDC checkpoint to the event store.
        """
        _execute(
            conn,
            "append_cdc_checkpoint",
            {
                "run_id": str(run_id),
                "source_table": source_table,
                "lsn_start": lsn_start,
                "lsn_end": lsn_end,
                "kafka_partition": kafka_partition,
                "offset_start": offset_start,
                "offset_end": offset_end,
                "record_count": record_count,
            },
        )

    @staticmethod
    def append_sf_cursor_checkpoint(
        conn: Any,
        *,
        run_id: UUID,
        sobject: str,
        cursor_ts: datetime,
        cursor_id: str,
        kafka_partition: int,
        offset_start: int,
        offset_end: int,
        record_count: int,
    ) -> None:
        """
        Append a Salesforce CDC cursor checkpoint to the event store.
        """
        _execute(
            conn,
            "append_sf_cursor_checkpoint",
            {
                "run_id": str(run_id),
                "sobject": sobject,
                "cursor_ts": cursor_ts,
                "cursor_id": cursor_id,
                "kafka_partition": kafka_partition,
                "offset_start": offset_start,
                "offset_end": offset_end,
                "record_count": record_count,
            },
        )

    @staticmethod
    def latest_sf_cursor(
        conn: Any,
        *,
        sobject: str,
    ) -> Optional[tuple[datetime, str]]:
        """
        Return the most recent SF cursor.
        """
        row = _execute(
            conn,
            "latest_sf_cursor",
            {"sobject": sobject},
        ).fetchone()
        return (row[0], row[1]) if row else None

    @staticmethod
    def append_silver_checkpoint(
        conn: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID,
        silver_domain: str,
        input_uris: list[str],
        output_table: str,
        output_uris: list[str],
        record_count: int,
        merge_inserted: int = 0,
        merge_updated: int = 0,
        merge_closed: int = 0,
    ) -> None:
        """
        Append a silver checkpoint to the event store.
        """
        _execute(
            conn,
            "append_silver_checkpoint",
            {
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id),
                "silver_domain": silver_domain,
                "input_uris": Jsonb(input_uris),
                "output_table": output_table,
                "output_uris": Jsonb(output_uris),
                "record_count": record_count,
                "merge_inserted": merge_inserted,
                "merge_updated": merge_updated,
                "merge_closed": merge_closed,
            },
        )

    @staticmethod
    def append_gold_checkpoint(
        conn: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID,
        metric: str,
        input_uris: list[str],
        output_table: str,
        output_uris: list[str],
        record_count: int,
    ) -> None:
        """
        Append a gold checkpoint to the event store.
        """
        _execute(
            conn,
            "append_gold_checkpoint",
            {
                "run_id": str(run_id),
                "parent_run_id": str(parent_run_id),
                "metric": metric,
                "input_uris": Jsonb(input_uris),
                "output_table": output_table,
                "output_uris": Jsonb(output_uris),
                "record_count": record_count,
            },
        )


__all__ = ["PgEventStore"]
