"""Structural checks for the gold curated aggregation DAG pair.

Same pattern as tests/test_silver_curated_promotion_dag.py — AST parse
and identifier checks; avoids installing Airflow in the test venv.
"""

from __future__ import annotations

import ast
from pathlib import Path

LISTENER_FILE = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "pipeline-orchestrator"
    / "dags"
    / "gold_curated"
    / "listener.py"
)

AGGREGATION_FILE = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "pipeline-orchestrator"
    / "dags"
    / "gold_curated"
    / "aggregation.py"
)

TASKS_FILE = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "pipeline-orchestrator"
    / "dags"
    / "gold_curated"
    / "tasks"
    / "open_curated_run.py"
)

RUN_AGGREGATION_SQL_FILE = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "pipeline-orchestrator"
    / "dags"
    / "gold_curated"
    / "tasks"
    / "run_aggregation_sql.py"
)

RECORD_CHECKPOINT_FILE = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "pipeline-orchestrator"
    / "dags"
    / "gold_curated"
    / "tasks"
    / "record_checkpoint_and_emit_event.py"
)


def test_dag_file_parses():
    ast.parse(LISTENER_FILE.read_text())
    ast.parse(AGGREGATION_FILE.read_text())
    ast.parse(TASKS_FILE.read_text())
    ast.parse(RUN_AGGREGATION_SQL_FILE.read_text())
    ast.parse(RECORD_CHECKPOINT_FILE.read_text())


def test_dag_declares_listener_and_aggregation_dag_ids():
    listener_source = LISTENER_FILE.read_text()
    aggregation_source = AGGREGATION_FILE.read_text()
    assert 'dag_id="gold_curated_listener"' in listener_source
    assert 'dag_id="gold_curated_aggregation"' in aggregation_source


def test_dag_subscribes_to_silver_completed():
    source = LISTENER_FILE.read_text()
    assert "pipeline.silver.completed.v1" in source


def test_dag_emits_gold_completed_and_failed_events():
    task_source = TASKS_FILE.read_text()
    dag_source = AGGREGATION_FILE.read_text()
    assert "pipeline.gold.completed.v1" in task_source
    assert "pipeline.gold.failed.v1" in dag_source


def test_dag_has_required_aggregation_tasks():
    source = AGGREGATION_FILE.read_text()
    for task_id in (
        "open_curated_run",
        "run_aggregation_sql",
        "record_checkpoint_and_emit_event",
    ):
        assert task_id in source, f"missing task_id {task_id!r}"


def test_dag_imports_shared_libs():
    source = TASKS_FILE.read_text() + RECORD_CHECKPOINT_FILE.read_text()
    assert "libs.platform_events" in source


def test_dag_uses_curated_promotion_pipeline_name():
    source = TASKS_FILE.read_text()
    assert "curated_promotion" in source
    assert "PipelineClass.curated" in source


def test_dag_records_gold_checkpoint():
    source = TASKS_FILE.read_text()
    assert "append_gold_checkpoint" in source


def test_dag_closes_run_on_failure():
    task_source = TASKS_FILE.read_text()
    dag_source = AGGREGATION_FILE.read_text()
    assert "close_run" in task_source
    assert 'status="failed"' in dag_source
    assert 'status="completed"' in task_source
