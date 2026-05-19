"""Event-store connection/runtime helpers."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator


class ManagedConnection:
    """
    Small wrapper that closes/disposes engine together.
    """

    def __init__(self, *, engine: Any, connection: Any):
        self._engine = engine
        self._connection = connection

    def begin(self):
        return self._connection.begin()

    def execute(self, statement: Any, params: dict[str, Any] | None = None):
        return self._connection.execute(statement, params or {})

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        try:
            self._connection.close()
        finally:
            self._engine.dispose()

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        try:
            self._connection.__exit__(exc_type, exc, tb)
        finally:
            self._engine.dispose()

    def __getattr__(self, name: str):
        return getattr(self._connection, name)


def build_event_store_engine(
    *,
    user_var: str = "EVENT_APPEND_DB_USER",
    password_var: str = "EVENT_APPEND_DB_PASSWORD",
):
    """
    Build a SQLAlchemy engine for event-store connections, using credentials
    from env vars.
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
    password_var: str = "EVENT_APPEND_DB_PASSWORD",
) -> ManagedConnection:
    """
    Build a connection for event-store operations, using credentials from env vars.
    """
    engine = build_event_store_engine(user_var=user_var, password_var=password_var)
    connection = engine.connect()

    return ManagedConnection(engine=engine, connection=connection)


@contextmanager
def open_event_store_conn(
    *,
    user_var: str,
    password_var: str,
) -> Iterator[ManagedConnection]:
    """
    Context manager for event-store connections, using credentials from env vars.
    """
    conn = build_event_store_conn(user_var=user_var, password_var=password_var)

    try:
        yield conn
    finally:
        conn.close()
