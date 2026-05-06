"""Shared utilities for silver curated DAGs."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dag_runtime import build_event_producer, build_minio_client, now_utc, open_event_store_conn

SOURCE_SYSTEM = "curated"
TOPIC_BRONZE_READY = "ingest.salesforce.bronze.ready.v1"
TOPIC_SILVER_STARTED = "pipeline.silver.started.v1"
TOPIC_SILVER_COMPLETED = "pipeline.silver.completed.v1"
TOPIC_SILVER_FAILED = "pipeline.silver.failed.v1"
SILVER_DOMAIN = "salesforce_opportunity"
SILVER_TABLE = "lakehouse.silver.dim_opportunity"
STAGING_PREFIX = "bronze/source=salesforce/object=Opportunity"
TRIGGER_TYPE = "event"
INITIATOR = "airflow"

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
SILVER_DDL_SQL_PATH = SQL_DIR / "silver_dim_opportunity_ddl.sql"
MERGE_SQL_PATH = SQL_DIR / "silver_dim_opportunity_merge.sql"

default_args = {
    "owner": "curated_promotion",
    "depends_on_past": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=2),
    "email_on_failure": False,
    "email_on_retry": False,
}


def _now_utc():
    return now_utc()


def _iter_sql_statements(sql_text: str):
    cleaned_lines = []

    for line in sql_text.splitlines():
        cleaned = line.split("--", 1)[0].strip()
        if cleaned:
            cleaned_lines.append(cleaned)

    for stmt in "\n".join(cleaned_lines).split(";"):
        normalized = stmt.strip()
        if normalized:
            yield normalized


def _open_event_store_conn():
    return open_event_store_conn()


def _get_minio_client():
    return build_minio_client(
        access_key_var="MINIO_TRINO_WRITE_USER",
        secret_key_var="MINIO_TRINO_WRITE_SECRET",
    )


def _build_producer():
    return build_event_producer(
        client_id="silver-curated-promotion-dag",
        username_var="REDPANDA_ORCHESTRATOR_SERVICE_USER",
        password_var="REDPANDA_ORCHESTRATOR_SERVICE_PASSWORD",
    )


def _trino_cursor():
    from trino.dbapi import connect

    conn = connect(
        host=os.environ.get("TRINO_HOST", "trino"),
        port=int(os.environ.get("TRINO_PORT", "8080")),
        user=os.environ.get("TRINO_USER", "trino_etl"),
        catalog="lakehouse",
    )

    return conn, conn.cursor()
