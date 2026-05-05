"""Shared utilities for silver curated DAGs."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


def _now_utc() -> datetime:
    """
    Get the current UTC time as a timezone-aware datetime object.
    """
    return datetime.now(timezone.utc)


def _iter_sql_statements(sql_text: str):
    """
    Parse a SQL file into individual statements, removing comments and empty lines.
    """
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
    """
    Open a new connection to the event store database using environment variables for configuration.
    """
    import psycopg

    return psycopg.connect(
        host=os.environ["EVENT_STORE_DB_HOST"],
        port=int(os.environ["EVENT_STORE_DB_PORT"]),
        dbname=os.environ["EVENT_STORE_DB"],
        user=os.environ["EVENT_APPEND_DB_USER"],
        password=os.environ["EVENT_APPEND_DB_PASSWORD"],
        autocommit=False,
    )


def _get_minio_client():
    """
    Create and return a Minio client configured with environment variables.
    """
    from minio import Minio

    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_TRINO_WRITE_USER"],
        secret_key=os.environ["MINIO_TRINO_WRITE_SECRET"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
        region=os.environ.get("MINIO_REGION", "us-east-1"),
    )


def _build_producer():
    """
    Build and return an EventProducer configured with environment variables.
    """
    from libs.platform_events.producer import EventProducer, ProducerConfig

    return EventProducer(
        ProducerConfig.from_env(
            client_id="silver-curated-promotion-dag",
            username_var="REDPANDA_ORCHESTRATOR_SERVICE_USER",
            password_var="REDPANDA_ORCHESTRATOR_SERVICE_PASSWORD",
        )
    )


def _trino_cursor():
    """
    Create and return a new Trino connection and cursor using environment variables for configuration.
    """
    from trino.dbapi import connect

    conn = connect(
        host=os.environ.get("TRINO_HOST", "trino"),
        port=int(os.environ.get("TRINO_PORT", "8080")),
        user=os.environ.get("TRINO_USER", "trino_etl"),
        catalog="lakehouse",
    )

    return conn, conn.cursor()
