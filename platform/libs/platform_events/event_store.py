"""psycopg helpers for writing to event_store.

Schema invariants (see infra/db/event-store-migrations/01_create_event_store_schema.sql):
- `pipeline_run` requires at least one `event_log` row by commit (deferred trigger).
  Callers MUST open a run, append its trigger event, and commit in one transaction.
- Run idempotency key is `(pipeline_name, trigger_event_ref)`.
- Event log dedupe key is `(topic, partition, kafka_offset, occurred_at)`
  (occurred_at included because event_log is partitioned by it).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from .envelope import Envelope, PipelineClass, PipelineName


def open_run(
    conn: psycopg.Connection,
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
    """Idempotently create a pipeline_run. Returns the effective run_id.

    If a run already exists for (pipeline_name, trigger_event_ref), its
    existing run_id is returned and the caller's `run_id` argument is
    ignored. Callers must use the returned value on subsequent events.
    """
    pipeline_class_v = pipeline_class.value if isinstance(pipeline_class, PipelineClass) else pipeline_class
    pipeline_name_v = pipeline_name.value if isinstance(pipeline_name, PipelineName) else pipeline_name

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO event_store.pipeline_run (
                run_id, pipeline_class, pipeline_name, source_system,
                trigger_type, trigger_event_ref, status, initiator, parent_run_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (pipeline_name, trigger_event_ref) DO NOTHING
            RETURNING run_id
            """,
            (
                str(run_id),
                pipeline_class_v,
                pipeline_name_v,
                source_system,
                trigger_type,
                trigger_event_ref,
                status,
                initiator,
                str(parent_run_id) if parent_run_id else None,
            ),
        )
        row = cur.fetchone()
        if row is not None:
            return UUID(str(row[0]))

        cur.execute(
            """
            SELECT run_id FROM event_store.pipeline_run
            WHERE pipeline_name = %s AND trigger_event_ref = %s
            """,
            (pipeline_name_v, trigger_event_ref),
        )
        existing = cur.fetchone()
        if existing is None:
            raise RuntimeError(
                "open_run conflict but existing row not found — schema invariant violated"
            )
        return UUID(str(existing[0]))


def append_event(
    conn: psycopg.Connection,
    envelope: Envelope,
    *,
    topic: str,
    partition: int,
    kafka_offset: int,
) -> bool:
    """Append one event_log row. Returns True if inserted, False if deduped.

    Dedupe is by (topic, partition, kafka_offset, occurred_at). occurred_at is
    included because event_log is partitioned by occurred_at and Postgres
    requires the partition key to appear in any parent-level unique constraint
    used as an ON CONFLICT target.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO event_store.event_log (
                event_id, run_id, event_type, topic, partition, kafka_offset,
                occurred_at, trace_id, payload, payload_hash, schema_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (topic, partition, kafka_offset, occurred_at) DO NOTHING
            RETURNING event_id
            """,
            (
                str(envelope.event_id),
                str(envelope.run_id),
                envelope.event_type,
                topic,
                partition,
                kafka_offset,
                envelope.occurred_at,
                str(envelope.trace_id) if envelope.trace_id else None,
                Jsonb(envelope.payload),
                envelope.payload_hash,
                envelope.schema_version,
            ),
        )
        return cur.fetchone() is not None


def close_run(
    conn: psycopg.Connection,
    run_id: UUID,
    *,
    status: str,
    completed_at: Optional[datetime] = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE event_store.pipeline_run
            SET status = %s,
                completed_at = COALESCE(%s, now())
            WHERE run_id = %s
            """,
            (status, completed_at or datetime.now(timezone.utc), str(run_id)),
        )


def raise_alert(
    conn: psycopg.Connection,
    *,
    run_id: UUID,
    severity: str,
    category: str,
    summary: str,
    details: dict[str, Any],
    occurred_at: Optional[datetime] = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO event_store.alert_event (
                run_id, severity, category, summary, details, occurred_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                str(run_id),
                severity,
                category,
                summary,
                Jsonb(details),
                occurred_at or datetime.now(timezone.utc),
            ),
        )


def append_cdc_checkpoint(
    conn: psycopg.Connection,
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
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO event_store.cdc_checkpoint (
                run_id, source_table, lsn_start, lsn_end,
                kafka_partition, offset_start, offset_end, record_count
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(run_id),
                source_table,
                lsn_start,
                lsn_end,
                kafka_partition,
                offset_start,
                offset_end,
                record_count,
            ),
        )


def append_sf_cursor_checkpoint(
    conn: psycopg.Connection,
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
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO event_store.sf_cursor_checkpoint (
                run_id, sobject, cursor_ts, cursor_id,
                kafka_partition, offset_start, offset_end, record_count
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(run_id),
                sobject,
                cursor_ts,
                cursor_id,
                kafka_partition,
                offset_start,
                offset_end,
                record_count,
            ),
        )


def latest_sf_cursor(
    conn: psycopg.Connection,
    *,
    sobject: str,
) -> Optional[tuple[datetime, str]]:
    """Return the most recent (cursor_ts, cursor_id) for an SObject, or None."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT cursor_ts, cursor_id
            FROM event_store.sf_cursor_checkpoint
            WHERE sobject = %s
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (sobject,),
        )
        row = cur.fetchone()
        return (row[0], row[1]) if row else None


__all__ = [
    "open_run",
    "append_event",
    "close_run",
    "raise_alert",
    "append_cdc_checkpoint",
    "append_sf_cursor_checkpoint",
    "latest_sf_cursor",
]
