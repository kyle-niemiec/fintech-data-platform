"""Helpers for triggering the excel_validation Airflow DAG from Kafka events."""

from __future__ import annotations

from typing import Any

DEFAULT_SCHEMA_CONTRACT_ID = "payroll_v1"


def build_dag_run_id(run_id: str) -> str:
    return f"excel_validation__{run_id}"


def build_dag_run_payload(envelope: dict[str, Any]) -> dict[str, Any]:
    payload = envelope.get("payload") or {}
    bucket = payload["bucket"]
    object_key = payload["object_key"]
    schema_contract_id = payload.get("schema_contract_id") or DEFAULT_SCHEMA_CONTRACT_ID
    return {
        "run_id": envelope["run_id"],
        "trace_id": envelope["trace_id"],
        "trigger_event_ref": envelope["trigger_event_ref"],
        "bucket": bucket,
        "object_key": object_key,
        "schema_contract_id": schema_contract_id,
    }


def trigger_dag_run(
    *,
    session: Any,
    airflow_base_url: str,
    dag_id: str,
    dag_run_id: str,
    conf: dict[str, Any],
    bearer_token: str,
    timeout: float = 10.0,
) -> bool:
    url = f"{airflow_base_url.rstrip('/')}/api/v2/dags/{dag_id}/dagRuns"
    response = session.post(
        url,
        headers={"Authorization": f"Bearer {bearer_token}"},
        json={"dag_run_id": dag_run_id, "conf": conf},
        timeout=timeout,
    )
    if response.status_code in {200, 201, 409}:
        return True
    response.raise_for_status()
    return False


def fetch_api_bearer_token(
    *,
    session: Any,
    airflow_base_url: str,
    username: str,
    password: str,
    timeout: float = 10.0,
) -> str:
    response = session.post(
        f"{airflow_base_url.rstrip('/')}/auth/token",
        json={"username": username, "password": password},
        timeout=timeout,
    )

    response.raise_for_status()
    token = str((response.json() or {}).get("access_token") or "")

    if not token:
        raise RuntimeError("Airflow auth token response missing access_token")

    return token
