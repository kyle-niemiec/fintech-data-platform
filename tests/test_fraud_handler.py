"""Unit coverage for fraud handler envelope parsing and produce shape."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from workers.fraud_worker.handler import RawMessage, parse_raw


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
