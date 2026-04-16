"""Structural checks for the gold curated aggregation DAG pair.

Same pattern as tests/test_silver_curated_promotion_dag.py — AST parse
and identifier checks; avoids installing Airflow in the test venv.
"""

from __future__ import annotations

import ast
from pathlib import Path

DAG_FILE = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "pipeline-orchestrator"
    / "dags"
    / "gold_curated_aggregation.py"
)


def test_dag_file_parses():
    source = DAG_FILE.read_text()
    ast.parse(source)


def test_dag_declares_listener_and_aggregation_dag_ids():
    source = DAG_FILE.read_text()
    assert 'dag_id="gold_curated_listener"' in source
    assert 'dag_id="gold_curated_aggregation"' in source


def test_dag_subscribes_to_silver_completed():
    source = DAG_FILE.read_text()
    assert "pipeline.silver.completed.v1" in source


def test_dag_emits_gold_completed_and_failed_events():
    source = DAG_FILE.read_text()
    assert "pipeline.gold.completed.v1" in source
    assert "pipeline.gold.failed.v1" in source


def test_dag_has_required_aggregation_tasks():
    source = DAG_FILE.read_text()
    for task_id in (
        "open_curated_run",
        "run_aggregation_sql",
        "record_checkpoint_and_emit_event",
    ):
        assert task_id in source, f"missing task_id {task_id!r}"


def test_dag_imports_shared_libs():
    source = DAG_FILE.read_text()
    assert "libs.platform_events" in source


def test_dag_uses_curated_promotion_pipeline_name():
    source = DAG_FILE.read_text()
    assert "curated_promotion" in source
    assert "PipelineClass.curated" in source


def test_dag_records_gold_checkpoint():
    source = DAG_FILE.read_text()
    assert "append_gold_checkpoint" in source


def test_dag_closes_run_on_failure():
    source = DAG_FILE.read_text()
    assert "close_run" in source
    assert 'status="failed"' in source
    assert 'status="completed"' in source
