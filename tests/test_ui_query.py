"""Unit coverage for the UI query-plane read models.

The route handlers are plain functions whose `Depends(...)` are only default
values, so they are exercised directly with a fake SQLAlchemy session instead
of an HTTP client. This keeps the read-model SQL/shape contract under test
without a live event-store database.
"""

from __future__ import annotations

import os
from uuid import UUID

# config.Settings has required fields; provide them before importing the app
# modules so engine construction (lazy, no connection) succeeds at import time.
os.environ.setdefault("EVENT_STORE_DB", "test_event_store")
os.environ.setdefault("EVENT_QUERY_DB_USER", "test_reader")
os.environ.setdefault("EVENT_QUERY_DB_PASSWORD", "test_password")

import pytest
from fastapi import HTTPException

from routes import ui_query

RUN_ID = "11111111-1111-1111-1111-111111111111"


class _Result:
    """Minimal stand-in for a SQLAlchemy Result over a list of mapping rows."""

    def __init__(self, rows):
        self._rows = list(rows)

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self._rows)

    def one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self):
        if not self._rows:
            return None
        row = self._rows[0]
        return next(iter(row.values())) if isinstance(row, dict) else row


class FakeSession:
    """Routes each execute() to canned rows and records the rendered SQL."""

    def __init__(self, router):
        self._router = router
        self.calls: list[tuple[str, dict]] = []

    def execute(self, clause, params=None):
        sql = str(clause)
        params = params or {}
        self.calls.append((sql, params))
        return _Result(self._router(sql, params))


def _exists_router(data_rows, *, exists=True):
    """Answer the run-existence probe, then return data rows for everything else."""

    def router(sql, _params):
        if "SELECT 1 FROM event_store.pipeline_run WHERE run_id" in sql:
            return [{"x": 1}] if exists else []
        return data_rows

    return router


def test_list_runs_maps_summaries_without_filter():
    rows = [
        {
            "run_id": RUN_ID,
            "pipeline_class": "ingestion",
            "pipeline_name": "excel_ingestion",
            "source_system": "excel",
            "status": "completed",
            "latest_stage": "ingest.excel.bronze.ready.v1",
            "started_at": "2026-05-20T12:00:00+00:00",
            "completed_at": None,
        }
    ]
    session = FakeSession(lambda *_: rows)
    result = ui_query.list_runs(db=session, pipeline_name=None)
    assert len(result) == 1
    assert str(result[0].run_id) == RUN_ID
    assert "WHERE pr.pipeline_name" not in session.calls[0][0]


def test_list_runs_applies_pipeline_name_filter():
    session = FakeSession(lambda *_: [])
    ui_query.list_runs(db=session, pipeline_name=["excel_ingestion", "cdc_ingestion"])
    sql, params = session.calls[0]
    assert "WHERE pr.pipeline_name = ANY(:pipeline_names)" in sql
    assert params["pipeline_names"] == ["excel_ingestion", "cdc_ingestion"]


def test_list_alerts_is_bounded_and_maps():
    rows = [
        {
            "alert_id": "22222222-2222-2222-2222-222222222222",
            "run_id": RUN_ID,
            "severity": "high",
            "category": "cdc_fraud_high_risk",
            "summary": "High-risk transaction flagged",
            "details": {"risk_score": 0.97},
            "occurred_at": "2026-05-20T12:01:00+00:00",
        }
    ]
    session = FakeSession(lambda *_: rows)
    out = ui_query.list_alerts(db=session, run_id=None, limit=100)
    sql, params = session.calls[0]
    assert "LIMIT :limit" in sql
    assert "WHERE run_id" not in sql
    assert params["limit"] == 100
    assert out[0].severity == "high"
    assert out[0].details == {"risk_score": 0.97}


def test_list_alerts_scopes_to_run_id():
    rid = UUID(RUN_ID)
    session = FakeSession(lambda *_: [])
    ui_query.list_alerts(db=session, run_id=rid, limit=25)
    sql, params = session.calls[0]
    assert "WHERE run_id = :run_id" in sql
    assert params["run_id"] == rid
    assert params["limit"] == 25


def test_get_run_raises_404_when_missing():
    session = FakeSession(_exists_router([], exists=False))
    with pytest.raises(HTTPException) as exc:
        ui_query.get_run(run_id=UUID(RUN_ID), db=session)
    assert exc.value.status_code == 404


def test_get_run_returns_detail():
    detail = {
        "run_id": RUN_ID,
        "pipeline_class": "ingestion",
        "pipeline_name": "excel_ingestion",
        "source_system": "excel",
        "trigger_type": "minio_object_created",
        "trigger_event_ref": "minio:bucket:key:etag",
        "status": "completed",
        "initiator": "james.beringer@meridian.example.com",
        "parent_run_id": None,
        "started_at": "2026-05-20T12:00:00+00:00",
        "completed_at": "2026-05-20T12:05:00+00:00",
        "latest_stage": "ingest.excel.bronze.ready.v1",
    }
    session = FakeSession(_exists_router([detail]))
    result = ui_query.get_run(run_id=UUID(RUN_ID), db=session)
    assert result.initiator == "james.beringer@meridian.example.com"
    assert result.parent_run_id is None


def test_list_recent_transactions_maps_risk_fields():
    rows = [
        {
            "transaction_id": "33333333-3333-3333-3333-333333333333",
            "account_id": "44444444-4444-4444-4444-444444444444",
            "instrument": "AAPL",
            "amount": "12345.67",
            "executed_at": "2026-05-20T12:00:00+00:00",
            "risk_score": "0.9700",
            "risk_flags": ["amount_gt_10k_aapl"],
        }
    ]
    session = FakeSession(lambda *_: rows)
    out = ui_query.list_recent_transactions(db=session, limit=25)
    assert out[0].instrument == "AAPL"
    assert str(out[0].amount) == "12345.67"
    assert out[0].risk_flags == ["amount_gt_10k_aapl"]


def test_list_events_and_lineage_and_artifacts_map():
    events = [
        {
            "occurred_at": "2026-05-20T12:00:00+00:00",
            "event_type": "ingest.excel.uploaded.v1",
            "source": "ingest",
            "run_id": RUN_ID,
            "trace_id": None,
            "message": "File uploaded to landing",
        }
    ]
    session = FakeSession(_exists_router(events))
    assert ui_query.list_events(run_id=UUID(RUN_ID), db=session)[0].source == "ingest"

    lineage = [
        {
            "event_id": "55555555-5555-5555-5555-555555555555",
            "occurred_at": "2026-05-20T12:00:00+00:00",
            "stage": "silver",
            "input_uris": ["s3://lake/bronze/x"],
            "output_uris": ["s3://lake/silver/y"],
            "transform_id": "normalize_dedupe_mask",
            "transform_version": "v1",
            "event_type": "pipeline.silver.completed.v1",
        }
    ]
    session = FakeSession(_exists_router(lineage))
    assert ui_query.list_lineage(run_id=UUID(RUN_ID), db=session)[0].stage == "silver"

    artifacts = [
        {
            "event_id": "66666666-6666-6666-6666-666666666666",
            "occurred_at": "2026-05-20T12:00:00+00:00",
            "stage": "bronze",
            "artifact_role": "output",
            "format": "parquet",
            "uri": "s3://lake/bronze/z",
            "event_type": "ingest.excel.bronze.ready.v1",
        }
    ]
    session = FakeSession(_exists_router(artifacts))
    assert ui_query.list_artifacts(run_id=UUID(RUN_ID), db=session)[0].artifact_role == "output"
