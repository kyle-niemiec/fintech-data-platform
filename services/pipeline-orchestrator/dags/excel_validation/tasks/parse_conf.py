"""Task callable for excel_validation.parse_conf."""

from __future__ import annotations

from typing import Any

from airflow.exceptions import AirflowException

from excel_validation.common import DEFAULT_CONTRACT_ID


def parse_conf(context: dict[str, Any]) -> dict[str, Any]:
    """
    Parse the conf passed to the DAG run and validate that required fields are present.
    """
    conf = (context["dag_run"].conf or {}) if context.get("dag_run") else {}
    required = {"bucket", "object_key", "run_id", "trigger_event_ref", "trace_id"}
    missing = required - conf.keys()

    if missing:
        raise AirflowException(f"dag_run.conf missing fields: {sorted(missing)}")

    conf.setdefault("schema_contract_id", DEFAULT_CONTRACT_ID)
    return conf
