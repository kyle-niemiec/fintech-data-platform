"""Light DAG smoke test for Salesforce incremental pull packaging."""

from __future__ import annotations

import ast
from pathlib import Path

DAGS_ROOT = Path(__file__).resolve().parents[1] / "services" / "pipeline-orchestrator" / "dags"
DAG_FILE = DAGS_ROOT / "salesforce_pull" / "incremental.py"
COMMON_FILE = DAGS_ROOT / "salesforce_pull" / "common.py"
PULL_TASK_FILE = DAGS_ROOT / "salesforce_pull" / "tasks" / "pull_sobject.py"


def test_salesforce_pull_package_files_parse():
    for path in (DAG_FILE, COMMON_FILE, PULL_TASK_FILE):
        ast.parse(path.read_text())


def test_dag_file_declares_required_tasks_and_dag_id():
    source = DAG_FILE.read_text()
    for identifier in ("salesforce_incremental_pull", "list_sobjects", "pull_sobject"):
        assert identifier in source, f"expected identifier {identifier!r} in DAG"


def test_task_module_imports_shared_libs_and_event_contracts():
    source = PULL_TASK_FILE.read_text()
    assert "libs.platform_events" in source
    assert "open_run" in source
    assert "append_event" in source


def test_raw_ready_topic_and_transform_identifier_are_preserved():
    common_source = COMMON_FILE.read_text()
    task_source = PULL_TASK_FILE.read_text()
    assert "ingest.salesforce.raw.ready.v1" in common_source
    assert "salesforce_incremental_pull" in task_source
