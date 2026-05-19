"""
Shared utilities for the excel validation DAG.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dag_runtime import (
    build_event_producer,
    now_utc,
)

CONTRACTS_ROOT = Path(
    os.environ.get("EXCEL_CONTRACTS_DIR", "/opt/airflow/meridian/libs/event_schemas")
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


def _build_producer():
    """
    Build a RedPanda event producer using credentials from environment variables.
    """
    return build_event_producer(
        client_id="excel-validation-dag",
        username_var="REDPANDA_AIRFLOW_USER",
        password_var="REDPANDA_AIRFLOW_PASSWORD",
    )


def _raw_key(object_key: str, run_id: str) -> str:
    """
    Build an S3 key for a raw Excel file based on the original object key and the
    current date. The key is partitioned by year, month, and day, and includes
    the run ID for traceability.
    
    E.G.: raw/source=excel/year=2024/month=06/day=20/run_id=abc123/filename.xlsx
    """
    now = now_utc()
    filename = object_key.rsplit("/", 1)[-1]

    return (
        f"{RAW_PREFIX}/year={now:%Y}/month={now:%m}/day={now:%d}"
        f"/run_id={run_id}/{filename}"
    )


def _quarantine_key(object_key: str, run_id: str) -> str:
    """
    Build an S3 key for a quarantined Excel file based on the original object
    key and the current date.
    """
    now = now_utc()
    filename = object_key.rsplit("/", 1)[-1]

    return (
        f"{QUARANTINE_PREFIX}/year={now:%Y}/month={now:%m}/day={now:%d}"
        f"/run_id={run_id}/{filename}"
    )


def _b64(data: bytes) -> str:
    """
    A helper function to base64-encode bytes data and return it as an ASCII string.
    """
    import base64
    return base64.b64encode(data).decode("ascii")


def _b64_decode(data: str) -> bytes:
    """
    A helper function to decode a base64-encoded ASCII string back into bytes.
    """
    import base64

    return base64.b64decode(data.encode("ascii"))
