"""Unit coverage for shared runtime helper modules."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass

from meridian.libs.event_store import runtime as event_store_runtime
from meridian.libs.minio_store import minio_client as minio_runtime
from meridian.libs.service_runtime import runtime as service_runtime


def test_build_consumer_config_plaintext(monkeypatch) -> None:
    monkeypatch.setenv("REDPANDA_BOOTSTRAP_SERVERS", "redpanda:9092")
    monkeypatch.setenv("REDPANDA_SECURITY_PROTOCOL", "PLAINTEXT")

    config = service_runtime.build_consumer_config(
        consumer_group="group-1",
        client_id="client-1",
        username_var="REDPANDA_USER",
        password_var="REDPANDA_PASS",
    )

    assert config["bootstrap.servers"] == "redpanda:9092"
    assert config["group.id"] == "group-1"
    assert config["client.id"] == "client-1"
    assert "security.protocol" not in config


def test_build_consumer_config_sasl(monkeypatch) -> None:
    monkeypatch.setenv("REDPANDA_BOOTSTRAP_SERVERS", "redpanda:9092")
    monkeypatch.setenv("REDPANDA_SECURITY_PROTOCOL", "SASL_PLAINTEXT")
    monkeypatch.setenv("REDPANDA_SASL_MECHANISM", "SCRAM-SHA-256")
    monkeypatch.setenv("REDPANDA_USER", "user")
    monkeypatch.setenv("REDPANDA_PASS", "pass")

    config = service_runtime.build_consumer_config(
        consumer_group="group-1",
        client_id="client-1",
        username_var="REDPANDA_USER",
        password_var="REDPANDA_PASS",
    )

    assert config["security.protocol"] == "SASL_PLAINTEXT"
    assert config["sasl.mechanism"] == "SCRAM-SHA-256"
    assert config["sasl.username"] == "user"
    assert config["sasl.password"] == "pass"


def test_build_event_store_engine_uses_expected_env(monkeypatch) -> None:
    monkeypatch.setenv("EVENT_STORE_DB_HOST", "event-store")
    monkeypatch.setenv("EVENT_STORE_DB_PORT", "5432")
    monkeypatch.setenv("EVENT_STORE_DB", "event_store")
    monkeypatch.setenv("EVENT_APPEND_DB_USER", "app")
    monkeypatch.setenv("EVENT_APPEND_DB_PASSWORD", "secret")

    captured = {}

    def _fake_create_engine(url, **kwargs):  # noqa: ANN001
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    import sqlalchemy

    monkeypatch.setattr(sqlalchemy, "create_engine", _fake_create_engine)

    engine = event_store_runtime.build_event_store_engine()

    assert engine is not None
    assert captured["url"].drivername == "postgresql+psycopg"
    assert captured["url"].host == "event-store"
    assert captured["url"].port == 5432
    assert captured["url"].database == "event_store"
    assert captured["url"].username == "app"
    assert captured["url"].password == "secret"
    assert captured["kwargs"]["pool_pre_ping"] is True
    assert captured["kwargs"]["pool_recycle"] == 1800


def test_build_event_store_conn_wraps_engine_connection(monkeypatch) -> None:
    class _FakeConnection:
        def __init__(self):
            self.closed = False

        def execute(self, statement, params):  # noqa: ANN001
            return (statement, params)

        def begin(self):
            return object()

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            self.closed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            self.close()
            return None

    class _FakeEngine:
        def __init__(self):
            self.disposed = False
            self.connection = _FakeConnection()

        def connect(self):
            return self.connection

        def dispose(self):
            self.disposed = True

    fake_engine = _FakeEngine()
    monkeypatch.setattr(event_store_runtime, "build_event_store_engine", lambda **_: fake_engine)

    conn = event_store_runtime.build_event_store_conn()

    assert isinstance(conn, event_store_runtime.ManagedConnection)
    conn.close()
    assert fake_engine.connection.closed is True
    assert fake_engine.disposed is True


def test_build_minio_client_uses_expected_env(monkeypatch) -> None:
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setenv("MINIO_INGEST_USER", "ingest-user")
    monkeypatch.setenv("MINIO_INGEST_SECRET", "ingest-secret")
    monkeypatch.setenv("MINIO_SECURE", "true")
    monkeypatch.setenv("MINIO_REGION", "us-east-1")

    captured = {}

    class _FakeMinio:
        def __init__(self, endpoint, access_key, secret_key, secure, region):  # noqa: ANN001
            captured["args"] = (endpoint, access_key, secret_key, secure, region)

    fake_minio_module = types.SimpleNamespace(Minio=_FakeMinio)
    monkeypatch.setitem(sys.modules, "minio", fake_minio_module)

    client = minio_runtime.build_minio_client(
        access_key_var="MINIO_INGEST_USER",
        secret_key_var="MINIO_INGEST_SECRET",
    )

    assert isinstance(client, _FakeMinio)
    assert captured["args"] == ("minio:9000", "ingest-user", "ingest-secret", True, "us-east-1")


def test_build_event_producer_uses_from_env(monkeypatch) -> None:
    @dataclass
    class _FakeConfig:
        client_id: str
        username_var: str
        password_var: str

    calls = {}

    def _fake_from_env(*, client_id: str, username_var: str, password_var: str):
        calls["args"] = (client_id, username_var, password_var)
        return _FakeConfig(client_id, username_var, password_var)

    class _FakeProducer:
        def __init__(self, config):
            self.config = config

    monkeypatch.setattr(service_runtime.ProducerConfig, "from_env", staticmethod(_fake_from_env))
    monkeypatch.setattr(service_runtime, "EventProducer", _FakeProducer)

    producer = service_runtime.build_event_producer(
        client_id="worker-a",
        username_var="USER_VAR",
        password_var="PASS_VAR",
    )

    assert calls["args"] == ("worker-a", "USER_VAR", "PASS_VAR")
    assert isinstance(producer, _FakeProducer)
    assert producer.config.client_id == "worker-a"
