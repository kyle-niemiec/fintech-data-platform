"""Unit coverage for Excel validation trigger worker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from workers.excel_validation_trigger.trigger import (
    DEFAULT_SCHEMA_CONTRACT_ID,
    build_dag_run_id,
    build_dag_run_payload,
    trigger_dag_run,
)


def _scanned_pass_envelope(payload_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "message": "Excel upload passed scan",
        "scan_result": "pass",
        "bucket": "fintech-lakehouse",
        "object_key": "landing/source=excel/year=2026/month=04/day=14/run_id=abc/payroll.xlsx",
    }
    if payload_overrides:
        payload.update(payload_overrides)
    return {
        "event_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "event_type": "ingest.excel.scanned.pass.v1",
        "source": "excel",
        "run_id": "11111111-1111-1111-1111-111111111111",
        "pipeline_class": "ingestion",
        "pipeline_name": "excel_ingestion",
        "parent_run_id": None,
        "trigger_event_ref": "minio:fintech-lakehouse:landing/source=excel/payroll.xlsx:etag-1",
        "trace_id": "22222222-2222-2222-2222-222222222222",
        "occurred_at": "2026-04-14T00:00:00Z",
        "schema_version": "v1",
        "payload_hash": "sha256-" + ("0" * 64),
        "payload": payload,
    }


def test_build_dag_run_id_is_deterministic():
    run_id = "11111111-1111-1111-1111-111111111111"
    assert build_dag_run_id(run_id) == f"excel_validation__{run_id}"


def test_build_dag_run_payload_maps_required_fields():
    envelope = _scanned_pass_envelope()
    payload = build_dag_run_payload(envelope)
    assert payload["run_id"] == envelope["run_id"]
    assert payload["trace_id"] == envelope["trace_id"]
    assert payload["trigger_event_ref"] == envelope["trigger_event_ref"]
    assert payload["bucket"] == envelope["payload"]["bucket"]
    assert payload["object_key"] == envelope["payload"]["object_key"]
    assert payload["schema_contract_id"] == DEFAULT_SCHEMA_CONTRACT_ID


def test_build_dag_run_payload_uses_contract_from_event_when_present():
    envelope = _scanned_pass_envelope({"schema_contract_id": "payroll_v2"})
    payload = build_dag_run_payload(envelope)
    assert payload["schema_contract_id"] == "payroll_v2"


@dataclass
class _FakeResponse:
    status_code: int
    text: str = ""

    def json(self) -> dict[str, Any]:
        return {"status_code": self.status_code}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}: {self.text}")


class _FakeSession:
    def __init__(self, response: _FakeResponse):
        self.response = response
        self.called_with: dict[str, Any] | None = None

    def post(self, url: str, json: dict[str, Any], timeout: float):  # noqa: A003
        self.called_with = {"url": url, "json": json, "timeout": timeout}
        return self.response


def test_trigger_dag_run_treats_201_as_success():
    session = _FakeSession(_FakeResponse(status_code=201))
    assert trigger_dag_run(
        session=session,
        airflow_base_url="http://airflow-webserver:8080",
        dag_id="excel_validation",
        dag_run_id="excel_validation__r1",
        conf={"run_id": "r1"},
    )


def test_trigger_dag_run_treats_409_as_idempotent_success():
    session = _FakeSession(_FakeResponse(status_code=409, text="already exists"))
    assert trigger_dag_run(
        session=session,
        airflow_base_url="http://airflow-webserver:8080",
        dag_id="excel_validation",
        dag_run_id="excel_validation__r1",
        conf={"run_id": "r1"},
    )


def test_trigger_dag_run_raises_on_other_errors():
    session = _FakeSession(_FakeResponse(status_code=500, text="boom"))
    with pytest.raises(RuntimeError):
        trigger_dag_run(
            session=session,
            airflow_base_url="http://airflow-webserver:8080",
            dag_id="excel_validation",
            dag_run_id="excel_validation__r1",
            conf={"run_id": "r1"},
        )
