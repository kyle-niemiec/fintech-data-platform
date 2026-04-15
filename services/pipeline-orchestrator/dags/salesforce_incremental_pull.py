"""Salesforce incremental-pull DAG.

Scheduled hourly. For each configured SObject:
  1. Reads the latest cursor from event_store.sf_cursor_checkpoint.
  2. Obtains a short-lived bearer token from the (mock) Salesforce token endpoint.
  3. Paginates a SOQL SELECT ... WHERE SystemModstamp > :cursor ORDER BY SystemModstamp, Id query.
  4. Writes each response page as JSON to MinIO raw/source=salesforce/object=.../page-N.json.
  5. Opens a salesforce_ingestion pipeline_run, emits ingest.salesforce.raw.ready.v1,
     and leaves the run in 'running' state. The salesforce_bronze_writer will append
     the bronze_ready event, record the cursor checkpoint, and close the run.

SObjects with no new rows since the last cursor are skipped (no event, no run).
The cursor does not advance until the bronze writer successfully flushes Parquet.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional
from urllib.parse import quote
from uuid import UUID, uuid4

import pendulum
from airflow import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowException

SOURCE_SYSTEM = "salesforce"
TOPIC_RAW_READY = "ingest.salesforce.raw.ready.v1"
TRIGGER_TYPE = "schedule"
INITIATOR = "airflow"
RAW_PREFIX = "raw/source=salesforce"

DEFAULT_SOBJECTS = ("Account", "Contact", "Opportunity")
SOBJECT_FIELDS: dict[str, tuple[str, ...]] = {
    "Account": ("Id", "Name", "Industry", "AnnualRevenue", "NumberOfEmployees", "SystemModstamp"),
    "Contact": ("Id", "FirstName", "LastName", "Email", "AccountId", "Title", "SystemModstamp"),
    "Opportunity": ("Id", "Name", "AccountId", "StageName", "Amount", "CloseDate", "SystemModstamp"),
}

default_args = {
    "owner": "salesforce_ingestion",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=15),
    "email_on_failure": False,
    "email_on_retry": False,
}


def _configured_sobjects() -> tuple[str, ...]:
    raw = os.environ.get("SALESFORCE_SOBJECTS")
    if not raw:
        return DEFAULT_SOBJECTS
    return tuple(s.strip() for s in raw.split(",") if s.strip())


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
            client_id="salesforce-incremental-pull-dag",
            username_var="REDPANDA_AIRFLOW_USER",
            password_var="REDPANDA_AIRFLOW_PASSWORD",
        )
    )


def _latest_cursor(sobject: str) -> Optional[datetime]:
    from libs.platform_events.event_store import latest_sf_cursor

    with _open_db_conn() as conn:
        with conn.transaction():
            result = latest_sf_cursor(conn, sobject=sobject)
    if result is None:
        return None
    cursor_ts, _cursor_id = result
    return cursor_ts


def _fetch_token(session, base_url: str) -> str:
    url = f"{base_url.rstrip('/')}/services/oauth2/token"
    resp = session.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["SALESFORCE_CLIENT_ID"],
            "client_secret": os.environ["SALESFORCE_CLIENT_SECRET"],
        },
        timeout=10,
    )
    if resp.status_code != 200:
        raise AirflowException(f"salesforce token exchange failed: {resp.status_code} {resp.text}")
    return resp.json()["access_token"]


def _build_soql(sobject: str, fields: Iterable[str], since_ts: Optional[datetime], page_size: int) -> str:
    field_list = ", ".join(fields)
    clauses = [f"SELECT {field_list} FROM {sobject}"]
    if since_ts is not None:
        ts_literal = since_ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        clauses.append(f"WHERE SystemModstamp > {ts_literal}")
    clauses.append("ORDER BY SystemModstamp ASC, Id ASC")
    clauses.append(f"LIMIT {page_size}")
    return " ".join(clauses)


def _pull_pages(
    session,
    base_url: str,
    token: str,
    api_version: str,
    soql: str,
) -> list[dict[str, Any]]:
    """Follow nextRecordsUrl pagination until done. Returns list of page dicts."""
    headers = {"Authorization": f"Bearer {token}"}
    first_url = f"{base_url.rstrip('/')}/services/data/{api_version}/query?q={quote(soql)}"
    pages: list[dict[str, Any]] = []
    url: Optional[str] = first_url
    while url is not None:
        resp = session.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise AirflowException(f"salesforce query failed: {resp.status_code} {resp.text}")
        page = resp.json()
        pages.append(page)
        if page.get("done", True):
            url = None
        else:
            next_path = page.get("nextRecordsUrl")
            if not next_path:
                url = None
            else:
                url = f"{base_url.rstrip('/')}{next_path}"
    return pages


def _raw_key(sobject: str, run_id: str, page_idx: int) -> str:
    now = _now_utc()
    return (
        f"{RAW_PREFIX}/object={sobject}"
        f"/year={now:%Y}/month={now:%m}/day={now:%d}"
        f"/run_id={run_id}/page-{page_idx:04d}.json"
    )


def _write_pages_to_minio(bucket: str, sobject: str, run_id: str, pages: list[dict[str, Any]]) -> list[str]:
    import io

    from minio.sse import SseKMS

    client = _get_minio_client()
    kms_key = os.environ["MINIO_KMS_KEY_ID"]
    output_uris: list[str] = []
    for idx, page in enumerate(pages):
        key = _raw_key(sobject, run_id, idx)
        body = json.dumps(page, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")
        client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=io.BytesIO(body),
            length=len(body),
            content_type="application/json",
            sse=SseKMS(kms_key, {}),
        )
        output_uris.append(f"s3://{bucket}/{key}")
    return output_uris


with DAG(
    dag_id="salesforce_incremental_pull",
    description="Hourly incremental pull from (mock) Salesforce per SObject.",
    default_args=default_args,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule="0 * * * *",
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["salesforce", "ingestion"],
) as dag:

    @task
    def list_sobjects() -> list[str]:
        return list(_configured_sobjects())

    @task(map_index_template="{{ task.op_kwargs.get('sobject', '') }}")
    def pull_sobject(sobject: str, **context) -> dict[str, Any]:
        import requests
        from libs.platform_events.envelope import (
            Envelope,
            EventSource,
            PipelineClass,
            PipelineName,
        )
        from libs.platform_events.event_store import append_event, open_run

        if sobject not in SOBJECT_FIELDS:
            raise AirflowException(f"unknown SObject: {sobject}")

        dag_run = context["dag_run"]
        logical_ts = dag_run.logical_date.isoformat() if dag_run.logical_date else dag_run.run_id
        trigger_event_ref = f"salesforce_incremental_pull__{logical_ts}__{sobject}"

        base_url = os.environ["SALESFORCE_BASE_URL"]
        api_version = os.environ.get("SALESFORCE_API_VERSION", "v59.0")
        page_size = int(os.environ.get("SALESFORCE_PAGE_SIZE", "200"))
        bucket = os.environ["MINIO_BUCKET_NAME"]

        fields = SOBJECT_FIELDS[sobject]
        since_ts = _latest_cursor(sobject)

        session = requests.Session()
        try:
            token = _fetch_token(session, base_url)
            soql = _build_soql(sobject, fields, since_ts, page_size)
            pages = _pull_pages(session, base_url, token, api_version, soql)
        finally:
            session.close()

        records_flat: list[dict[str, Any]] = []
        for page in pages:
            records_flat.extend(page.get("records", []))

        if not records_flat:
            return {
                "sobject": sobject,
                "row_count": 0,
                "trigger_event_ref": trigger_event_ref,
            }

        run_id = uuid4()
        trace_id = uuid4()
        output_uris = _write_pages_to_minio(bucket, sobject, str(run_id), pages)

        last = records_flat[-1]
        proposed_cursor_ts = last["SystemModstamp"]
        proposed_cursor_id = last["Id"]

        payload: dict[str, Any] = {
            "message": f"Salesforce incremental pull landed {len(records_flat)} {sobject} rows to raw.",
            "stage": "raw",
            "sobject": sobject,
            "since_cursor_ts": since_ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if since_ts else None,
            "proposed_cursor_ts": proposed_cursor_ts,
            "proposed_cursor_id": proposed_cursor_id,
            "row_count": len(records_flat),
            "page_count": len(pages),
            "fields": list(fields),
            "api_version": api_version,
            "input_uris": [f"{base_url.rstrip('/')}/services/data/{api_version}/query"],
            "output_uris": output_uris,
            "transform_id": "salesforce_incremental_pull",
            "transform_version": "v1",
        }

        envelope = Envelope.build(
            event_type=TOPIC_RAW_READY,
            source=EventSource.salesforce,
            run_id=run_id,
            pipeline_class=PipelineClass.ingestion,
            pipeline_name=PipelineName.salesforce_ingestion,
            trigger_event_ref=trigger_event_ref,
            trace_id=trace_id,
            payload=payload,
        )

        producer = _build_producer()
        try:
            partition, offset = producer.produce(TOPIC_RAW_READY, envelope, key=f"{sobject}:{run_id}")
        finally:
            producer.close()

        with _open_db_conn() as conn:
            with conn.transaction():
                effective_run_id = open_run(
                    conn,
                    run_id=run_id,
                    pipeline_class=PipelineClass.ingestion,
                    pipeline_name=PipelineName.salesforce_ingestion,
                    source_system=SOURCE_SYSTEM,
                    trigger_type=TRIGGER_TYPE,
                    trigger_event_ref=trigger_event_ref,
                    initiator=INITIATOR,
                )
                append_event(
                    conn,
                    envelope,
                    topic=TOPIC_RAW_READY,
                    partition=partition,
                    kafka_offset=offset,
                )

        return {
            "sobject": sobject,
            "row_count": len(records_flat),
            "run_id": str(effective_run_id),
            "trigger_event_ref": trigger_event_ref,
            "output_uris": output_uris,
            "proposed_cursor_ts": proposed_cursor_ts,
            "proposed_cursor_id": proposed_cursor_id,
        }

    sobjects = list_sobjects()
    pull_sobject.expand(sobject=sobjects)
