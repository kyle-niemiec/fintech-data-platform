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

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pendulum
from airflow import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowException
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator

CONTRACTS_ROOT = Path(
    os.environ.get("EXCEL_CONTRACTS_DIR", "/opt/airflow/platform_libs/libs/platform_events/excel_schemas")
)
DEFAULT_CONTRACT_ID = os.environ.get("EXCEL_DEFAULT_CONTRACT_ID", "payroll_v1")
RAW_PREFIX = "raw/source=excel"
QUARANTINE_PREFIX = "quarantine/source=excel"

TOPIC_RAW_READY = "ingest.excel.raw.ready.v1"
TOPIC_QUARANTINED = "ingest.excel.quarantined.v1"
TRANSFORM_ID = "excel_schema_validate"
TRANSFORM_VERSION = "v1"

default_args = {
    "owner": "excel_ingestion",
    "depends_on_past": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=1),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=15),
    "email_on_failure": False,
    "email_on_retry": False,
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _get_minio_client():
    from minio import Minio

    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_VALIDATION_USER"],
        secret_key=os.environ["MINIO_VALIDATION_SECRET"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
        region=os.environ.get("MINIO_REGION", "us-east-1"),
    )


def _open_db_conn():
    import psycopg

    return psycopg.connect(
        host=os.environ["EVENT_STORE_DB_HOST"],
        port=int(os.environ["EVENT_STORE_DB_PORT"]),
        dbname=os.environ["EVENT_STORE_DB"],
        user=os.environ["EVENT_APPEND_DB_USER"],
        password=os.environ["EVENT_APPEND_DB_PASSWORD"],
        autocommit=False,
    )


def _build_producer():
    from libs.platform_events.producer import EventProducer, ProducerConfig

    return EventProducer(
        ProducerConfig.from_env(
            client_id="excel-validation-dag",
            username_var="REDPANDA_AIRFLOW_USER",
            password_var="REDPANDA_AIRFLOW_PASSWORD",
        )
    )


def _raw_key(object_key: str, run_id: str) -> str:
    now = _now_utc()
    filename = object_key.rsplit("/", 1)[-1]
    return (
        f"{RAW_PREFIX}/year={now:%Y}/month={now:%m}/day={now:%d}"
        f"/run_id={run_id}/{filename}"
    )


def _quarantine_key(object_key: str, run_id: str) -> str:
    now = _now_utc()
    filename = object_key.rsplit("/", 1)[-1]
    return (
        f"{QUARANTINE_PREFIX}/year={now:%Y}/month={now:%m}/day={now:%d}"
        f"/run_id={run_id}/{filename}"
    )


with DAG(
    dag_id="excel_validation",
    description="Schema-validate a scanned Excel upload and branch raw vs quarantine.",
    default_args=default_args,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=16,
    tags=["excel", "ingestion"],
) as dag:

    @task
    def parse_conf(**context) -> dict[str, Any]:
        conf = (context["dag_run"].conf or {}) if context.get("dag_run") else {}
        required = {"bucket", "object_key", "run_id", "trigger_event_ref", "trace_id"}
        missing = required - conf.keys()
        if missing:
            raise AirflowException(f"dag_run.conf missing fields: {sorted(missing)}")
        conf.setdefault("schema_contract_id", DEFAULT_CONTRACT_ID)
        return conf

    @task
    def download_object(parsed: dict[str, Any]) -> dict[str, Any]:
        client = _get_minio_client()
        response = client.get_object(parsed["bucket"], parsed["object_key"])
        try:
            payload_bytes = response.read()
        finally:
            response.close()
            response.release_conn()
        return {**parsed, "payload_size_bytes": len(payload_bytes), "_payload_b64": _b64(payload_bytes)}

    @task
    def validate(downloaded: dict[str, Any]) -> dict[str, Any]:
        from libs.excel_validation import load_contract, load_workbook, validate_dataframe

        contract = load_contract(CONTRACTS_ROOT / f"{downloaded['schema_contract_id']}.json")
        payload = _b64_decode(downloaded["_payload_b64"])
        df = load_workbook(payload, sheet_name=contract.sheet_name)
        result = validate_dataframe(df, contract)
        return {
            **downloaded,
            "passed": result.passed,
            "row_count": result.row_count,
            "errors": result.errors_as_list(),
            "contract_id": contract.contract_id,
        }

    def _route(ti) -> str:
        validated = ti.xcom_pull(task_ids="validate")
        return "write_raw" if validated["passed"] else "write_quarantine"

    branch = BranchPythonOperator(task_id="branch", python_callable=_route)

    @task
    def write_raw(validated: dict[str, Any]) -> dict[str, Any]:
        client = _get_minio_client()
        dest_key = _raw_key(validated["object_key"], validated["run_id"])
        from minio.commonconfig import CopySource

        client.copy_object(
            bucket_name=validated["bucket"],
            object_name=dest_key,
            source=CopySource(validated["bucket"], validated["object_key"]),
        )
        return {
            **validated,
            "stage": "raw",
            "output_key": dest_key,
        }

    @task
    def write_quarantine(validated: dict[str, Any]) -> dict[str, Any]:
        client = _get_minio_client()
        dest_key = _quarantine_key(validated["object_key"], validated["run_id"])
        from minio.commonconfig import CopySource
        from minio.sseconfig import SseKmsConfig  # type: ignore[attr-defined]
        from minio.sse import SseKMS

        client.copy_object(
            bucket_name=validated["bucket"],
            object_name=dest_key,
            source=CopySource(validated["bucket"], validated["object_key"]),
            sse=SseKMS(os.environ["MINIO_KMS_KEY_ID"], {}),
        )
        return {
            **validated,
            "stage": "quarantine",
            "output_key": dest_key,
        }

    @task(trigger_rule="none_failed_min_one_success")
    def emit_event(*branch_outputs: dict[str, Any]) -> None:
        from libs.platform_events.envelope import (
            Envelope,
            EventSource,
            PipelineClass,
            PipelineName,
        )
        from libs.platform_events.event_store import append_event, close_run

        outcome = next((b for b in branch_outputs if b), None)
        if outcome is None:
            raise AirflowException("emit_event received no branch output")

        stage = outcome["stage"]
        is_raw = stage == "raw"
        topic = TOPIC_RAW_READY if is_raw else TOPIC_QUARANTINED
        event_type = topic

        payload: dict[str, Any] = {
            "message": (
                f"Excel upload accepted and landed to raw: {outcome['output_key']}"
                if is_raw
                else f"Excel upload failed schema validation: {outcome['output_key']}"
            ),
            "stage": stage,
            "input_uris": [f"s3://{outcome['bucket']}/{outcome['object_key']}"],
            "output_uris": [f"s3://{outcome['bucket']}/{outcome['output_key']}"],
            "row_count": outcome["row_count"],
            "transform_id": TRANSFORM_ID,
            "transform_version": TRANSFORM_VERSION,
        }
        if is_raw:
            payload["schema_contract_id"] = outcome["contract_id"]
        else:
            payload["errors"] = outcome["errors"]

        envelope = Envelope.build(
            event_type=event_type,
            source=EventSource.excel,
            run_id=UUID(outcome["run_id"]),
            pipeline_class=PipelineClass.ingestion,
            pipeline_name=PipelineName.excel_ingestion,
            trigger_event_ref=outcome["trigger_event_ref"],
            trace_id=UUID(outcome["trace_id"]),
            payload=payload,
        )

        producer = _build_producer()
        try:
            partition, offset = producer.produce(topic, envelope, key=outcome["run_id"])
        finally:
            producer.close()

        with _open_db_conn() as conn:
            with conn.transaction():
                append_event(
                    conn,
                    envelope,
                    topic=topic,
                    partition=partition,
                    kafka_offset=offset,
                )
                close_run(
                    conn,
                    UUID(outcome["run_id"]),
                    status="running" if is_raw else "quarantined",
                )

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


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")


def _b64_decode(data: str) -> bytes:
    import base64

    return base64.b64decode(data.encode("ascii"))
