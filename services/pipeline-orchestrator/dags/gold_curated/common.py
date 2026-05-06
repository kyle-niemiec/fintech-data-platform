"""Shared utilities for gold curated DAGs."""

from __future__ import annotations

import os
from datetime import timedelta

from dag_runtime import build_event_producer

SOURCE_SYSTEM = "curated"
TOPIC_SILVER_COMPLETED = "pipeline.silver.completed.v1"
TOPIC_GOLD_STARTED = "pipeline.gold.started.v1"
TOPIC_GOLD_COMPLETED = "pipeline.gold.completed.v1"
TOPIC_GOLD_FAILED = "pipeline.gold.failed.v1"
GOLD_METRIC = "pipeline_conversion"
GOLD_TABLE = "lakehouse.gold.kpi_pipeline_conversion"
TRIGGER_TYPE = "event"
INITIATOR = "airflow"

default_args = {
    "owner": "curated_promotion",
    "depends_on_past": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=2),
    "email_on_failure": False,
    "email_on_retry": False,
}


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
