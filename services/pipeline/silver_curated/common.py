"""Shared utilities for silver curated DAGs."""

from __future__ import annotations

import os
from datetime import timedelta

from dag_runtime import build_event_producer

SOURCE_SYSTEM = "curated"
TOPICS_BRONZE_READY = (
    "ingest.salesforce.bronze.ready.v1",
    "cdc.oltp.bronze.ready.v1",
    "ingest.excel.bronze.ready.v1",
)
TOPIC_SILVER_STARTED = "pipeline.silver.started.v1"
TOPIC_SILVER_COMPLETED = "pipeline.silver.completed.v1"
TOPIC_SILVER_FAILED = "pipeline.silver.failed.v1"
SILVER_DOMAIN = "salesforce_opportunity"
SILVER_TABLE = "lakehouse.silver.dim_opportunity"
STAGING_PREFIX = "warehouse/_staging"
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
