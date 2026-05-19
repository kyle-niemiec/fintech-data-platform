"""Shared runtime helpers for Airflow DAG modules."""

from __future__ import annotations

from datetime import datetime, timezone

from meridian.libs.event_store import open_event_store_conn
from meridian.libs.minio_store import build_minio_client
from meridian.libs.service_runtime import build_event_producer


def now_utc() -> datetime:
    """
    Return current timezone-aware UTC timestamp.
    """
    return datetime.now(timezone.utc)


__all__ = [
    "build_event_producer",
    "build_minio_client",
    "now_utc",
    "open_event_store_conn",
]
