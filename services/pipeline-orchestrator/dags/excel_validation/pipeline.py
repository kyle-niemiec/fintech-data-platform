from __future__ import annotations

from typing import Any

import pendulum
from airflow import DAG
from airflow.decorators import task
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator

from excel_validation.common import default_args
from excel_validation.tasks.download_object import download_object as download_object_task
from excel_validation.tasks.emit_event import emit_event as emit_event_task
from excel_validation.tasks.parse_conf import parse_conf as parse_conf_task

from excel_validation.tasks.route_validation_outcome import (
    route_validation_outcome,
)

from excel_validation.tasks.validate import validate as validate_task
from excel_validation.tasks.write_quarantine import write_quarantine as write_quarantine_task
from excel_validation.tasks.write_raw import write_raw as write_raw_task

"""Excel validation DAG.

Triggered per-scanned upload via ``dag_run.conf``. The expected conf shape
is the ``ingest.excel.scanned.pass.v1`` envelope's ``payload`` plus the
originating ``run_id``, ``trigger_event_ref`` and ``trace_id`` fields.

Flow:
    download -> validate -> branch -> write_raw | write_quarantine -> emit

The DAG emits ``ingest.excel.raw.ready.v1`` or ``ingest.excel.quarantined.v1``
to Redpanda and persists both the copy event and any stage_failed retries
to the event store. Airflow's retry policy drives stage_failed emissions.
"""
with DAG(
    dag_id="excel_validation",
    description="Schema-validate a scanned Excel upload and branch raw vs quarantine.",
    default_args=default_args,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=16,
    is_paused_upon_creation=False,
    tags=["excel", "ingestion"],
) as validation_dag:

    @task(task_id="parse_conf")
    def parse_conf(**context) -> dict[str, Any]:
        return parse_conf_task(context)

    @task(task_id="download_object")
    def download_object(parsed: dict[str, Any]) -> dict[str, Any]:
        return download_object_task(parsed)

    @task(task_id="validate")
    def validate(downloaded: dict[str, Any]) -> dict[str, Any]:
        return validate_task(downloaded)

    branch = BranchPythonOperator(task_id="branch", python_callable=route_validation_outcome)

    @task(task_id="write_raw")
    def write_raw(validated: dict[str, Any]) -> dict[str, Any]:
        return write_raw_task(validated)

    @task(task_id="write_quarantine")
    def write_quarantine(validated: dict[str, Any]) -> dict[str, Any]:
        return write_quarantine_task(validated)

    @task(task_id="emit_event", trigger_rule="none_failed_min_one_success")
    def emit_event(*branch_outputs: dict[str, Any]) -> None:
        emit_event_task(*branch_outputs)

    end = EmptyOperator(task_id="end", trigger_rule="none_failed_min_one_success")

    parsed = parse_conf()
    downloaded = download_object(parsed)
    validated = validate(downloaded)

    raw_out = write_raw(validated)
    quar_out = write_quarantine(validated)

    validated >> branch
    branch >> [raw_out, quar_out]
    emitted = emit_event(raw_out, quar_out)
    emitted >> end
