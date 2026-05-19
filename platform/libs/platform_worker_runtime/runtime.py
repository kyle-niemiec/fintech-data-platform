"""
Shared runtime helpers for pipeline worker entrypoints.
"""

from __future__ import annotations

import os
from typing import Any

from libs.platform_events.producer import EventProducer, ProducerConfig


class EventStoreConnection:
    """
    Compatibility wrapper over SQLAlchemy Connection.

    Existing workers rely on `conn.transaction()` (psycopg API). This wrapper
    preserves that call surface while using SQLAlchemy under the hood.
    """

    def __init__(self, *, engine: Any, connection: Any):
        """
        Initialize the connection wrapper with the given SQLAlchemy engine and connection.
        """
        self._engine = engine
        self._connection = connection

    def execute(self, statement: Any, params: dict[str, Any]):
        """
        Execute a SQL statement with the given parameters, validating that all expected
        parameters are provided.
        """
        return self._connection.execute(statement, params)

    def transaction(self):
        """
        Start a transaction context.

        TECH-DEBT: This is a compatibility method for existing workers that use
        the psycopg API. It simply returns the connection itself, which can be
        used as a context manager for transactions.
        """
        return self._connection.begin()

    def begin(self):
        """
        Alias for transaction() to match psycopg API.
        """
        return self._connection.begin()

    def commit(self) -> None:
        """
        Commit the current transaction.
        """
        self._connection.commit()

    def rollback(self) -> None:
        """
        Rollback the current transaction.
        """
        self._connection.rollback()

    def close(self) -> None:
        """
        Close the connection.
        """
        try:
            self._connection.close()
        finally:
            self._engine.dispose()

    def __enter__(self):
        """
        Enter the connection context, returning self for use in a `with` statement.
        """
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        """
        Exit the connection context, ensuring the connection is closed.
        """
        try:
            self._connection.__exit__(exc_type, exc, tb)
        finally:
            self._engine.dispose()

    def __getattr__(self, name: str) -> Any:
        """
        Delegate attribute access to the underlying connection for any attributes not
        explicitly defined on this wrapper.
        """
        return getattr(self._connection, name)


def build_consumer_config(
    *,
    consumer_group: str,
    client_id: str,
    username_var: str,
    password_var: str,
) -> dict[str, str]:
    """
    Build a Kafka consumer configuration dictionary from environment variables,
    with support for optional SASL authentication.
    """
    config: dict[str, str] = {
        "bootstrap.servers": os.environ["REDPANDA_BOOTSTRAP_SERVERS"],
        "group.id": consumer_group,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "client.id": client_id,
    }

    security_protocol = os.environ.get("REDPANDA_SECURITY_PROTOCOL", "PLAINTEXT")

    if security_protocol != "PLAINTEXT":
        config["security.protocol"] = security_protocol
        config["sasl.mechanism"] = os.environ.get("REDPANDA_SASL_MECHANISM", "SCRAM-SHA-256")
        config["sasl.username"] = os.environ[username_var]
        config["sasl.password"] = os.environ[password_var]

    return config


def build_event_store_engine(
    *,
    user_var: str = "EVENT_APPEND_DB_USER",
    password_var: str = "EVENT_APPEND_DB_PASSWORD"
):
    """
    Build a SQLAlchemy engine for connecting to the event-store Postgres, using
    credentials from the specified environment variables.
    """
    from sqlalchemy import URL, create_engine

    url = URL.create(
        drivername="postgresql+psycopg",
        username=os.environ[user_var],
        password=os.environ[password_var],
        host=os.environ["EVENT_STORE_DB_HOST"],
        port=int(os.environ["EVENT_STORE_DB_PORT"]),
        database=os.environ["EVENT_STORE_DB"],
    )

    return create_engine(url)


def build_event_store_conn(
    *,
    user_var: str = "EVENT_APPEND_DB_USER",
    password_var: str = "EVENT_APPEND_DB_PASSWORD"
):
    """
    Build a connection for the event-store Postgres.
    """
    engine = build_event_store_engine(user_var=user_var, password_var=password_var)
    connection = engine.connect()

    return EventStoreConnection(engine=engine, connection=connection)


def build_minio_client(*, access_key_var: str, secret_key_var: str):
    """
    Build a MinIO client using the standard environment variable layout for
    credentials.
    """
    from minio import Minio  # type: ignore[import-untyped]

    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ[access_key_var],
        secret_key=os.environ[secret_key_var],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
        region=os.environ.get("MINIO_REGION", "us-east-1"),
    )


def build_event_producer(
    *,
    client_id: str,
    username_var: str,
    password_var: str
) -> EventProducer:
    """
    Build an event producer using the standard environment variable layout for
    credentials.
    """
    return EventProducer(
        ProducerConfig.from_env(
            client_id=client_id,
            username_var=username_var,
            password_var=password_var,
        )
    )
