"""Structural checks for the silver curated promotion DAG pair.

Follows the same AST-parse + identifier-search pattern as
test_excel_validation_dag.py: cheap tests that avoid installing Airflow
in the test venv but still catch rename/regression drift in the DAG
contract (topic names, task ids, shared-lib imports).
"""

from __future__ import annotations

import ast
from pathlib import Path

DAG_FILE = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "pipeline-orchestrator"
    / "dags"
    / "silver_curated_promotion.py"
)


def test_dag_file_parses():
    source = DAG_FILE.read_text()
    ast.parse(source)


def test_dag_declares_listener_and_promotion_dag_ids():
    source = DAG_FILE.read_text()
    assert 'dag_id="silver_curated_listener"' in source
    assert 'dag_id="silver_curated_promotion"' in source


def test_dag_subscribes_to_salesforce_bronze_ready():
    source = DAG_FILE.read_text()
    assert "ingest.salesforce.bronze.ready.v1" in source


def test_dag_emits_silver_completed_and_failed_events():
    source = DAG_FILE.read_text()
    assert "pipeline.silver.completed.v1" in source
    assert "pipeline.silver.failed.v1" in source


def test_dag_has_required_transform_tasks():
    source = DAG_FILE.read_text()
    for task_id in (
        "open_curated_run",
        "stage_and_mask_bronze",
        "merge_into_silver",
        "record_checkpoint_and_emit_event",
    ):
        assert task_id in source, f"missing task_id {task_id!r}"


def test_dag_imports_shared_libs():
    source = DAG_FILE.read_text()
    assert "libs.platform_events" in source
    assert "libs.platform_masking" in source


def test_dag_uses_curated_promotion_pipeline_name():
    source = DAG_FILE.read_text()
    assert "curated_promotion" in source
    assert "PipelineClass.curated" in source


def test_dag_records_silver_checkpoint():
    source = DAG_FILE.read_text()
    assert "append_silver_checkpoint" in source


def test_dag_closes_run_on_failure():
    source = DAG_FILE.read_text()
    assert "close_run" in source
    assert 'status="failed"' in source
    assert 'status="completed"' in source
