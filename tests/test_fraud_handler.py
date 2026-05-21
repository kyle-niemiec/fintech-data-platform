"""Unit coverage for fraud handler envelope parsing and produce shape."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from uuid import UUID

from meridian.libs.event_store import PgEventStore
from workers.fraud_worker.handler import (
    FraudHandler,
    RawMessage,
    SOURCE_SYSTEM,
    TOPIC_ASSESSED_STARTED,
    TOPIC_INTERNAL,
    parse_raw,
)


def _debezium_envelope(*, op: str = "c", instrument: str = "AAPL", amount: str = "15000",
                        lsn: str = "0/16B5C10", table: str = "transaction") -> dict[str, Any]:
    return {
        "payload": {
            "op": op,
            "ts_ms": 1700000000000,
            "before": None,
            "after": {
                "transaction_id": "11111111-1111-1111-1111-111111111111",
                "account_id": "22222222-2222-2222-2222-222222222222",
                "instrument": instrument,
                "amount": amount,
                "executed_at": "2026-04-14T00:00:00Z",
            },
            "source": {
                "schema": "trading",
                "table": table,
                "lsn": lsn,
                "ts_ms": 1700000000000,
            },
        }
    }


def test_parse_raw_returns_row_and_metadata() -> None:
    raw = RawMessage(
        topic="cdc.oltp.raw.v1", partition=3, offset=42,
        value=_debezium_envelope(), key=None,
    )
    parsed = parse_raw(raw)
    assert parsed is not None
    assert parsed["op"] == "c"
    assert parsed["lsn"] == "0/16B5C10"
    assert parsed["source_table"] == "trading.transaction"
    assert parsed["row"]["instrument"] == "AAPL"


def test_parse_raw_skips_non_transaction_table() -> None:
    raw = RawMessage(
        topic="cdc.oltp.raw.v1", partition=0, offset=1,
        value=_debezium_envelope(table="risk_flag"), key=None,
    )
    assert parse_raw(raw) is None


def test_parse_raw_handles_delete_from_before() -> None:
    env = _debezium_envelope(op="d")
    env["payload"]["before"] = env["payload"]["after"]
    env["payload"]["after"] = None
    raw = RawMessage(topic="cdc.oltp.raw.v1", partition=0, offset=1, value=env, key=None)
    parsed = parse_raw(raw)
    assert parsed is not None
    assert parsed["op"] == "d"
    assert parsed["row"]["transaction_id"] == "11111111-1111-1111-1111-111111111111"


def test_parse_raw_treats_snapshot_like_create() -> None:
    raw = RawMessage(
        topic="cdc.oltp.raw.v1", partition=0, offset=0,
        value=_debezium_envelope(op="r"), key=None,
    )
    parsed = parse_raw(raw)
    assert parsed is not None
    assert parsed["op"] == "r"


def test_cdc_source_system_matches_event_store_domain_contract() -> None:
    assert SOURCE_SYSTEM == "cdc"


def test_fraud_started_event_contract_constants_are_stable() -> None:
    assert TOPIC_INTERNAL == "event_store.internal"
    assert TOPIC_ASSESSED_STARTED == "cdc.oltp.assessed.started.v1"


class _Begin:
    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _FakeRow:
    def __init__(self, value):
        self._value = value

    def fetchone(self):
        return self._value


class _FakeConn:
    def begin(self):
        return _Begin()

    def execute(self, *_a, **_k):
        # Only exercised by the risk_flag upsert; a truthy row means "inserted".
        return _FakeRow((1,))


class _FactoryCtx:
    def __enter__(self):
        return _FakeConn()

    def __exit__(self, *_a):
        return False


class _FakeProducer:
    def produce(self, _topic, _envelope, *, key):  # noqa: ARG002
        return (0, 0)


def _make_handler() -> FraudHandler:
    return FraudHandler(
        oltp_conn=_FakeConn(),
        event_store_connection_factory=lambda: _FactoryCtx(),
        producer=_FakeProducer(),
    )


def _patch_event_store(monkeypatch) -> list[dict]:
    """Replace event-store writes with spies; return the captured raise_alert calls."""
    alerts: list[dict] = []
    run_id = UUID("99999999-9999-9999-9999-999999999999")
    monkeypatch.setattr(PgEventStore, "open_run", staticmethod(lambda _conn, **_k: run_id))
    monkeypatch.setattr(PgEventStore, "append_event", staticmethod(lambda _conn, _env, **_k: True))
    monkeypatch.setattr(PgEventStore, "close_run", staticmethod(lambda _conn, _rid, **_k: None))
    monkeypatch.setattr(PgEventStore, "raise_alert", staticmethod(lambda _conn, **k: alerts.append(k)))
    return alerts


def test_handle_raises_alert_for_high_risk_transaction(monkeypatch) -> None:
    alerts = _patch_event_store(monkeypatch)
    raw = RawMessage(
        topic="cdc.oltp.raw.v1", partition=0, offset=1,
        value=_debezium_envelope(instrument="AAPL", amount="15000"), key=None,
    )

    assert _make_handler().handle(raw) is True
    assert len(alerts) == 1
    assert alerts[0]["category"] == "cdc_fraud_high_risk"
    assert alerts[0]["severity"] == "high"
    assert "risk_threshold_exceeded" in alerts[0]["details"]["risk_flags"]


def test_handle_does_not_alert_for_normal_transaction(monkeypatch) -> None:
    alerts = _patch_event_store(monkeypatch)
    raw = RawMessage(
        topic="cdc.oltp.raw.v1", partition=0, offset=2,
        value=_debezium_envelope(instrument="AAPL", amount="100"), key=None,
    )

    assert _make_handler().handle(raw) is True
    assert alerts == []


def test_handle_does_not_alert_when_assessed_event_deduped(monkeypatch) -> None:
    # Replay: append_event returns False (deduped) -> no duplicate alert.
    alerts = _patch_event_store(monkeypatch)
    monkeypatch.setattr(PgEventStore, "append_event", staticmethod(lambda _conn, _env, **_k: False))
    raw = RawMessage(
        topic="cdc.oltp.raw.v1", partition=0, offset=3,
        value=_debezium_envelope(instrument="AAPL", amount="15000"), key=None,
    )

    assert _make_handler().handle(raw) is True
    assert alerts == []


def test_fraud_handler_uses_event_store_connection_factory() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "workers"
        / "fraud_worker"
        / "handler.py"
    ).read_text()

    assert "event_store_connection_factory" in source
    assert "with self.event_store_connection_factory() as event_store_conn:" in source
