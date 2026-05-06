"""Shared utilities for gold curated DAGs."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dag_runtime import build_event_producer, now_utc, open_event_store_conn

SOURCE_SYSTEM = "curated"
TOPIC_SILVER_COMPLETED = "pipeline.silver.completed.v1"
TOPIC_GOLD_STARTED = "pipeline.gold.started.v1"
TOPIC_GOLD_COMPLETED = "pipeline.gold.completed.v1"
TOPIC_GOLD_FAILED = "pipeline.gold.failed.v1"
GOLD_METRIC = "pipeline_conversion"
GOLD_TABLE = "lakehouse.gold.kpi_pipeline_conversion"
TRIGGER_TYPE = "event"
INITIATOR = "airflow"

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
GOLD_DDL_SQL_PATH = SQL_DIR / "gold_kpi_pipeline_conversion_ddl.sql"
AGG_SQL_PATH = SQL_DIR / "gold_kpi_pipeline_conversion_insert.sql"

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


def _build_producer():
    return build_event_producer(
        client_id="gold-curated-aggregation-dag",
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
