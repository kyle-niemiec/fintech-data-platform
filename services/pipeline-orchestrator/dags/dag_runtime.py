"""
Shared runtime helpers for Airflow DAG modules.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from libs.platform_worker_runtime.runtime import EventStoreConnection, build_event_store_engine


def now_utc() -> datetime:
    """
    Return current timezone-aware UTC timestamp.
    """
    return datetime.now(timezone.utc)


def open_event_store_conn(*, user_var: str = "EVENT_APPEND_DB_USER", password_var: str = "EVENT_APPEND_DB_PASSWORD"):
    """
    Open a SQLAlchemy-backed connection to the event-store Postgres.
    """
    engine = build_event_store_engine(user_var=user_var, password_var=password_var)
    return EventStoreConnection(engine=engine, connection=engine.connect())


def build_minio_client(*, access_key_var: str, secret_key_var: str):
    """
    Create a MinIO client using the standard environment layout.
    """
    from minio import Minio

    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ[access_key_var],
        secret_key=os.environ[secret_key_var],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
        region=os.environ.get("MINIO_REGION", "us-east-1"),
    )


def build_event_producer(*, client_id: str, username_var: str, password_var: str):
    """
    Build an event producer from standard Redpanda env vars.
    """
    from libs.platform_events.producer import EventProducer, ProducerConfig

    return EventProducer(
        ProducerConfig.from_env(
            client_id=client_id,
            username_var=username_var,
            password_var=password_var,
        )
    )
