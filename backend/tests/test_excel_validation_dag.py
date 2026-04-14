"""Light DAG smoke test: syntax-parse + structural identifier checks.

A full DagBag load would require installing Airflow in the test venv,
which is a heavy dependency for unit tests. The real import check runs
when the Airflow scheduler loads the DAG on container start. Here we
verify the file parses as valid Python and declares the tasks and
topic names the rest of the platform depends on.
"""

from __future__ import annotations

import ast
from pathlib import Path

DAG_FILE = (
    Path(__file__).resolve().parents[1]
    / "airflow"
    / "dags"
    / "excel_validation.py"
)


def test_dag_file_parses():
    source = DAG_FILE.read_text()
    ast.parse(source)


def test_dag_file_declares_required_topics_and_tasks():
    source = DAG_FILE.read_text()
    for identifier in (
        "ingest.excel.raw.ready.v1",
        "ingest.excel.quarantined.v1",
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


def test_dag_imports_shared_libs():
    source = DAG_FILE.read_text()
    assert "libs.platform_events" in source
    assert "libs.excel_validation" in source
