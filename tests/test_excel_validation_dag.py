"""Light DAG smoke test: syntax-parse + structural identifier checks."""

from __future__ import annotations

import ast
from pathlib import Path

DAGS_ROOT = Path(__file__).resolve().parents[1] / "services" / "pipeline-orchestrator" / "dags"
DAG_FILE = DAGS_ROOT / "excel_validation" / "pipeline.py"
COMMON_FILE = DAGS_ROOT / "excel_validation" / "common.py"
VALIDATE_TASK_FILE = DAGS_ROOT / "excel_validation" / "tasks" / "validate.py"
EMIT_EVENT_TASK_FILE = DAGS_ROOT / "excel_validation" / "tasks" / "emit_event.py"


def test_excel_validation_package_files_parse():
    for path in (
        DAG_FILE,
        COMMON_FILE,
        VALIDATE_TASK_FILE,
        EMIT_EVENT_TASK_FILE,
    ):
        ast.parse(path.read_text())


def test_dag_file_declares_required_tasks_and_dag_id():
    source = DAG_FILE.read_text()
    for identifier in (
        "parse_conf",
        "download_object",
        "validate",
        "branch",
        "write_raw",
        "write_quarantine",
        "emit_event",
        "excel_validation",
    ):
        assert identifier in source, f"expected identifier {identifier!r} in DAG"


def test_task_modules_import_shared_libs():
    validate_source = VALIDATE_TASK_FILE.read_text()
    emit_source = EMIT_EVENT_TASK_FILE.read_text()

    assert "libs.excel_validation" in validate_source
    assert "libs.platform_events" in emit_source


def test_emit_task_handles_run_state_boundaries():
    task_source = EMIT_EVENT_TASK_FILE.read_text()
    common_source = COMMON_FILE.read_text()
    assert "ingest.excel.raw.ready.v1" in common_source
    assert "ingest.excel.quarantined.v1" in common_source
    assert "close_run" in task_source
    assert 'status="running" if is_raw else "quarantined"' in task_source
