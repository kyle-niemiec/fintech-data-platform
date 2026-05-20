"""Structural audit checks for event-store connection factory adoption."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

EVENT_WRITER_ENTRYPOINTS = (
    "services/workers/excel_scanner/main.py",
    "services/workers/excel_bronze_writer/main.py",
    "services/workers/salesforce_bronze_writer/main.py",
    "services/workers/cdc_bronze_writer/main.py",
    "services/workers/fraud_worker/main.py",
)

PIPELINE_EVENT_WRITERS = (
    "services/pipeline/excel_validation/tasks/emit_event.py",
    "services/pipeline/salesforce_pull/tasks/pull_sobject.py",
    "services/pipeline/silver_curated/tasks/record_checkpoint_and_emit_event.py",
    "services/pipeline/gold_curated/tasks/record_checkpoint_and_emit_event.py",
    "services/pipeline/curated_dag_helpers.py",
)


def test_worker_event_writer_entrypoints_do_not_use_build_event_store_conn():
    for rel_path in EVENT_WRITER_ENTRYPOINTS:
        source = (REPO_ROOT / rel_path).read_text()
        assert "build_event_store_conn" not in source, rel_path
        assert "open_event_store_conn" in source, rel_path


def test_pipeline_event_writers_use_open_event_store_conn():
    for rel_path in PIPELINE_EVENT_WRITERS:
        source = (REPO_ROOT / rel_path).read_text()
        assert "open_event_store_conn" in source, rel_path
