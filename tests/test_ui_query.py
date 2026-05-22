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
    result = ui_query.list_runs(db=session, pipeline_name=None, limit=25, offset=0)
    assert len(result.items) == 1
    assert result.total == 1
    assert result.limit == 25 and result.offset == 0
    assert str(result.items[0].run_id) == RUN_ID
    sql = session.calls[0][0]
    assert "WHERE pr.pipeline_name" not in sql
    assert "LIMIT :limit OFFSET :offset" in sql


def test_list_runs_applies_pipeline_name_filter():
    session = FakeSession(lambda *_: [])
    ui_query.list_runs(
        db=session,
        pipeline_name=["excel_ingestion", "cdc_ingestion"],
        limit=25,
        offset=0,
    )
    sql, params = session.calls[0]
    assert "WHERE pr.pipeline_name = ANY(:pipeline_names)" in sql
    assert params["pipeline_names"] == ["excel_ingestion", "cdc_ingestion"]


def test_list_runs_applies_backfill_filter():
    session = FakeSession(lambda *_: [])
    ui_query.list_runs(db=session, pipeline_name=None, backfill=True, limit=25, offset=0)
    sql = session.calls[0][0]
    assert "strpos(coalesce(pr.trigger_event_ref, ''), 'backfill_') > 0" in sql
    assert "NOT (" not in sql


def test_list_runs_excludes_backfill_when_false():
    session = FakeSession(lambda *_: [])
    ui_query.list_runs(db=session, pipeline_name=None, backfill=False, limit=25, offset=0)
    sql = session.calls[0][0]
    assert "NOT (strpos(coalesce(pr.trigger_event_ref, ''), 'backfill_') > 0" in sql


def test_list_runs_binds_limit_and_offset():
    session = FakeSession(lambda *_: [])
    ui_query.list_runs(db=session, pipeline_name=None, limit=50, offset=100)
    sql, params = session.calls[0]
    assert "LIMIT :limit OFFSET :offset" in sql
    assert params["limit"] == 50 and params["offset"] == 100


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
    out = ui_query.list_alerts(db=session, run_id=None, limit=100, offset=0)
    sql, params = session.calls[0]
    assert "LIMIT :limit OFFSET :offset" in sql
    assert "WHERE run_id" not in sql
    assert params["limit"] == 100 and params["offset"] == 0
    assert out.items[0].severity == "high"
    assert out.items[0].details == {"risk_score": 0.97}
    assert out.total == 1


def test_list_alerts_scopes_to_run_id():
    rid = UUID(RUN_ID)
    session = FakeSession(lambda *_: [])
    ui_query.list_alerts(db=session, run_id=rid, limit=25, offset=0)
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
    out = ui_query.list_recent_transactions(db=session, limit=25, offset=0)
    sql = session.calls[0][0]
    assert "LIMIT :limit OFFSET :offset" in sql
    assert out.items[0].instrument == "AAPL"
    assert str(out.items[0].amount) == "12345.67"
    assert out.items[0].risk_flags == ["amount_gt_10k_aapl"]
    # Unscored canned row (no event_id) → no run link and no event-store query.
    assert out.items[0].run_id is None


EVENT_ID = UUID("77777777-7777-7777-7777-777777777777")
TXN_ID = "33333333-3333-3333-3333-333333333333"


def _recent_tx_row(**overrides):
    row = {
        "transaction_id": TXN_ID,
        "account_id": "44444444-4444-4444-4444-444444444444",
        "instrument": "AAPL",
        "amount": "12345.67",
        "executed_at": "2026-05-20T12:00:00+00:00",
        "origin": None,
        "risk_score": "0.9700",
        "risk_flags": ["amount_gt_10k_aapl"],
        "event_id": None,
    }
    row.update(overrides)
    return row


def test_list_recent_transactions_attaches_run_id_and_origin():
    tx_rows = [_recent_tx_row(origin="manual_demo", event_id=EVENT_ID)]
    link_rows = [{"event_id": EVENT_ID, "run_id": UUID(RUN_ID)}]

    def router(sql, _params):
        if "trading.transaction" in sql:
            return tx_rows
        if "event_store.event_log" in sql:
            return link_rows
        return []

    oltp = FakeSession(router)
    query = FakeSession(router)
    out = ui_query.list_recent_transactions(db=oltp, query_db=query, limit=25, offset=0)

    assert str(out.items[0].run_id) == RUN_ID
    assert out.items[0].origin == "manual_demo"
    # The link lookup is an exact event_id IN-list against the event store.
    link_sql, link_params = query.calls[0]
    assert "WHERE event_id = ANY(:event_ids)" in link_sql
    assert link_params["event_ids"] == [EVENT_ID]


def test_list_recent_transactions_skips_link_query_when_unscored():
    oltp = FakeSession(lambda *_: [_recent_tx_row(event_id=None)])
    query = FakeSession(lambda *_: [])
    out = ui_query.list_recent_transactions(db=oltp, query_db=query, limit=25, offset=0)
    assert out.items[0].run_id is None
    # No event_ids → the (separate) event-store DB is never touched.
    assert query.calls == []


def _run_detail_row(**overrides):
    detail = {
        "run_id": RUN_ID,
        "pipeline_class": "ingestion",
        "pipeline_name": "cdc_ingestion",
        "source_system": "cdc",
        "trigger_type": "cdc",
        "trigger_event_ref": "topic:0:1",
        "status": "completed",
        "initiator": "cdc_fraud_worker",
        "parent_run_id": None,
        "started_at": "2026-05-20T12:00:00+00:00",
        "completed_at": "2026-05-20T12:00:05+00:00",
        "latest_stage": "cdc.assessed.v1",
    }
    detail.update(overrides)
    return detail


def test_get_run_preview_kind_cdc_transaction():
    detail = _run_detail_row()

    def router(sql, _params):
        if "SELECT 1 FROM event_store.pipeline_run WHERE run_id" in sql:
            return [{"x": 1}]
        if "source_table" in sql:  # is-transaction probe
            return [{"x": 1}]
        return [detail]

    result = ui_query.get_run(run_id=UUID(RUN_ID), db=FakeSession(router))
    assert result.preview_kind == "cdc_transaction"


def test_get_run_preview_kind_none_for_loan_cdc_run():
    detail = _run_detail_row()

    def router(sql, _params):
        if "SELECT 1 FROM event_store.pipeline_run WHERE run_id" in sql:
            return [{"x": 1}]
        if "source_table" in sql:  # not a transaction → empty
            return []
        return [detail]

    result = ui_query.get_run(run_id=UUID(RUN_ID), db=FakeSession(router))
    assert result.preview_kind is None


def test_get_run_preview_kind_none_for_quarantined_excel():
    detail = _run_detail_row(
        pipeline_name="excel_ingestion", source_system="excel", status="quarantined"
    )
    result = ui_query.get_run(run_id=UUID(RUN_ID), db=FakeSession(_exists_router([detail])))
    assert result.preview_kind is None


def test_get_run_preview_404_for_non_previewable_run():
    def router(sql, _params):
        if "SELECT 1 FROM event_store.pipeline_run WHERE run_id" in sql:
            return [{"x": 1}]
        if "SELECT pipeline_name, status" in sql:
            return [{"pipeline_name": "salesforce_ingestion", "status": "completed"}]
        return []

    with pytest.raises(HTTPException) as exc:
        ui_query.get_run_preview(
            run_id=UUID(RUN_ID), db=FakeSession(router), oltp_db=FakeSession(lambda *_: [])
        )
    assert exc.value.status_code == 404


def test_get_run_preview_returns_cdc_transaction():
    def query_router(sql, _params):
        if "SELECT 1 FROM event_store.pipeline_run WHERE run_id" in sql:
            return [{"x": 1}]
        if "SELECT pipeline_name, status" in sql:
            return [{"pipeline_name": "cdc_ingestion", "status": "completed"}]
        if "transaction_id' AS transaction_id" in sql:
            return [{"transaction_id": TXN_ID}]
        if "source_table" in sql:  # is-transaction probe
            return [{"x": 1}]
        return []

    def oltp_router(sql, _params):
        if "trading.transaction" in sql:
            return [_recent_tx_row(origin="manual_demo")]
        return []

    out = ui_query.get_run_preview(
        run_id=UUID(RUN_ID), db=FakeSession(query_router), oltp_db=FakeSession(oltp_router)
    )
    assert out.kind == "cdc_transaction"
    assert out.transaction is not None
    assert out.transaction.origin == "manual_demo"
    assert str(out.transaction.run_id) == RUN_ID


def test_get_run_preview_returns_excel(monkeypatch):
    monkeypatch.setattr(ui_query, "read_object", lambda **_: b"fake-xlsx-bytes")
    monkeypatch.setattr(
        ui_query,
        "parse_xlsx_preview",
        lambda data, max_rows=10: ("payroll", ["employee_id", "gross_amount"], [["E1", 100.0]]),
    )

    def query_router(sql, _params):
        if "SELECT 1 FROM event_store.pipeline_run WHERE run_id" in sql:
            return [{"x": 1}]
        if "SELECT pipeline_name, status" in sql:
            return [{"pipeline_name": "excel_ingestion", "status": "completed"}]
        if "LIKE '%.xlsx'" in sql:
            return [{"uri": "s3://fintech-lakehouse/landing/payroll.xlsx"}]
        return []

    out = ui_query.get_run_preview(
        run_id=UUID(RUN_ID), db=FakeSession(query_router), oltp_db=FakeSession(lambda *_: [])
    )
    assert out.kind == "excel"
    assert out.excel is not None
    assert out.excel.sheet_name == "payroll"
    assert out.excel.columns == ["employee_id", "gross_amount"]
    assert out.excel.rows == [["E1", 100.0]]


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
