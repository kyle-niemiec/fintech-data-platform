"""
Shared utilities for the Salesforce pull DAG.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional
from urllib.parse import quote

from airflow.exceptions import AirflowException
from dag_runtime import (
    build_event_producer,
    build_minio_client,
    now_utc,
    open_event_store_conn,
)

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
    """
    Read the comma-separated SALESFORCE_SOBJECTS environment variable.
    """
    raw = os.environ.get("SALESFORCE_SOBJECTS")

    if not raw:
        return DEFAULT_SOBJECTS

    return tuple(sobject.strip() for sobject in raw.split(",") if sobject.strip())


def _build_producer():
    """
    Build a RedPanda event producer using credentials from environment variables.
    """
    return build_event_producer(
        client_id="salesforce-incremental-pull-dag",
        username_var="REDPANDA_AIRFLOW_USER",
        password_var="REDPANDA_AIRFLOW_PASSWORD",
    )


def _latest_cursor(sobject: str) -> Optional[datetime]:
    """
    Query the event store for the latest cursor timestamp for the given SObject.
    """
    from libs.platform_events.event_store import latest_sf_cursor

    with open_event_store_conn() as conn:
        with conn.transaction():
            result = latest_sf_cursor(conn, sobject=sobject)

    if result is None:
        return None

    cursor_ts, _cursor_id = result
    return cursor_ts


def _fetch_token(session, base_url: str) -> str:
    """
    Exchange client credentials for a short-lived bearer token from the Salesforce token endpoint.
    """
    url = f"{base_url.rstrip('/')}/services/oauth2/token"

    response = session.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["SALESFORCE_CLIENT_ID"],
            "client_secret": os.environ["SALESFORCE_CLIENT_SECRET"],
        },
        timeout=10,
    )

    if response.status_code != 200:
        raise AirflowException(f"salesforce token exchange failed: {response.status_code} {response.text}")

    return response.json()["access_token"]


def _build_soql(sobject: str, fields: Iterable[str], since_ts: Optional[datetime], page_size: int) -> str:
    """
    Build a SOQL query string for the given SObject, fields, and optional cursor timestamp.
    """
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
    """
    Follow nextRecordsUrl pagination until done.
    """
    headers = {"Authorization": f"Bearer {token}"}
    first_url = f"{base_url.rstrip('/')}/services/data/{api_version}/query?q={quote(soql)}"
    pages: list[dict[str, Any]] = []
    url: Optional[str] = first_url

    while url is not None:
        response = session.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            raise AirflowException(f"salesforce query failed: {response.status_code} {response.text}")

        page = response.json()
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
    """
    Construct the MinIO object key for a given SObject, DAG run ID, and page index.
    """
    now = now_utc()

    return (
        f"{RAW_PREFIX}/object={sobject}"
        f"/year={now:%Y}/month={now:%m}/day={now:%d}"
        f"/run_id={run_id}/page-{page_idx:04d}.json"
    )


def _write_pages_to_minio(bucket: str, sobject: str, run_id: str, pages: list[dict[str, Any]]) -> list[str]:
    """
    Write the given pages of query results to MinIO as JSON files, and return
    the list of S3 URIs.
    """
    import io

    from minio.sse import SseKMS

    client = build_minio_client(
        access_key_var="MINIO_INGEST_USER",
        secret_key_var="MINIO_INGEST_SECRET",
    )

    kms_key = os.environ["MINIO_KMS_KEY_ID"]
    output_uris: list[str] = []

    # Write each page to MinIO with server-side encryption, and collect the output URIs for event payload
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
