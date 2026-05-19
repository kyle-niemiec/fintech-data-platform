"""Coverage for PgEventStore namespace API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from meridian.libs.redpanda_events.envelope import Envelope, EventSource, PipelineClass, PipelineName
from meridian.libs.event_store import PgEventStore


@dataclass
class _StubResult:
    rows: list[tuple[Any, ...] | None] = field(default_factory=list)

    def fetchone(self):
        if not self.rows:
            return None
        return self.rows.pop(0)


@dataclass
class _StubConn:
    rows_by_call: list[tuple[Any, ...] | None] = field(default_factory=list)
    executed: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def execute(self, statement: Any, params: dict[str, Any]) -> _StubResult:
        self.executed.append((str(statement), dict(params)))
        row = self.rows_by_call.pop(0) if self.rows_by_call else None
        return _StubResult(rows=[row] if row is not None else [])


def test_pg_event_store_open_run_insert_path() -> None:
    run_id = uuid4()
    conn = _StubConn(rows_by_call=[(str(run_id),)])

    effective = PgEventStore.open_run(
        conn,
        run_id=run_id,
        pipeline_class=PipelineClass.ingestion,
        pipeline_name=PipelineName.excel_ingestion,
        source_system="excel",
        trigger_type="minio_object_created",
        trigger_event_ref="minio:bucket:key:etag",
        initiator="minio_ingest",
    )

    assert effective == run_id
    assert len(conn.executed) == 1
    assert "INSERT INTO event_store.pipeline_run" in conn.executed[0][0]


def test_pg_event_store_append_event_sql_shape() -> None:
    run_id = uuid4()
    trace_id = uuid4()
    env = Envelope.build(
        event_type="ingest.excel.scanned.pass.v1",
        source=EventSource.excel,
        run_id=run_id,
        pipeline_class=PipelineClass.ingestion,
        pipeline_name=PipelineName.excel_ingestion,
        trigger_event_ref="minio:bucket:key:etag",
        trace_id=trace_id,
        payload={"stage": "scan", "scan_result": "pass"},
        occurred_at=datetime.now(timezone.utc),
    )

    conn = _StubConn(rows_by_call=[(str(env.event_id),)])

    inserted = PgEventStore.append_event(
        conn,
        env,
        topic="ingest.excel.scanned.pass.v1",
        partition=0,
        kafka_offset=10,
    )

    assert inserted is True
    assert len(conn.executed) == 1
    sql, params = conn.executed[0]
    assert "INSERT INTO event_store.event_log" in sql
    assert "ON CONFLICT (topic, partition, kafka_offset, occurred_at) DO NOTHING" in sql
    assert params["event_id"] == str(env.event_id)
    assert params["run_id"] == str(run_id)
