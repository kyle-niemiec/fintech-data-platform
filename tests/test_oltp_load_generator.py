from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from workers.oltp_load_generator.main import (
    INSERT_LOAN_SQL,
    INSERT_PAYMENT_SQL,
    INSERT_STATUS_SQL,
    PRIMARY_EVENT_TYPES,
    SELECT_RANDOM_ACTIVE_LOAN_SQL,
    UPDATE_LOAN_STATE_SQL,
    _emit_loan_event,
    _emit_loan_payment_event,
    _emit_loan_status_history_event,
    _next_delay_seconds,
    _read_interval_bounds_seconds,
)


class _FakeResult:
    def __init__(self, row: dict[str, Any] | None):
        self._row = row

    def mappings(self) -> "_FakeResult":
        return self

    def fetchone(self) -> dict[str, Any] | None:
        return self._row


@dataclass
class _ExecuteCall:
    statement: Any
    params: dict[str, Any]


class _FakeConnection:
    def __init__(self, active_loan_row: dict[str, Any] | None):
        self._active_loan_row = active_loan_row
        self.calls: list[_ExecuteCall] = []

    def execute(self, statement: Any, params: dict[str, Any]):
        self.calls.append(_ExecuteCall(statement=statement, params=dict(params)))
        if statement is SELECT_RANDOM_ACTIVE_LOAN_SQL:
            return _FakeResult(self._active_loan_row)
        return _FakeResult(None)


class _SequenceRng:
    def __init__(self, *, randint_values: list[int], random_values: list[float] | None = None):
        self._randint_values = list(randint_values)
        self._random_values = list(random_values or [])

    def randint(self, _low: int, _high: int) -> int:
        if not self._randint_values:
            raise AssertionError("No randint values left in _SequenceRng")
        return self._randint_values.pop(0)

    def random(self) -> float:
        if not self._random_values:
            return 0.0
        return self._random_values.pop(0)

    def choice(self, seq):
        return seq[0]


def _find_call(calls: list[_ExecuteCall], statement: Any) -> _ExecuteCall:
    for call in calls:
        if call.statement is statement:
            return call
    raise AssertionError(f"statement not found: {statement}")


def _find_all_calls(calls: list[_ExecuteCall], statement: Any) -> list[_ExecuteCall]:
    return [call for call in calls if call.statement is statement]


def test_primary_event_set_remains_four_types() -> None:
    assert set(PRIMARY_EVENT_TYPES) == {
        "transaction",
        "loan",
        "loan_payment",
        "loan_status_history",
    }


def test_loan_event_creates_current_loan_and_history() -> None:
    conn = _FakeConnection(active_loan_row=None)
    rng = _SequenceRng(randint_values=[10_000])
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)

    summary = _emit_loan_event(conn, now=now, rng=rng)

    assert summary["primary_event"] == "loan"
    assert _find_call(conn.calls, INSERT_LOAN_SQL).params["status_code"] == "current"
    assert _find_call(conn.calls, INSERT_LOAN_SQL).params["days_past_due"] == 0
    assert _find_call(conn.calls, INSERT_LOAN_SQL).params["original_principal_balance"] == Decimal("10000")
    assert _find_call(conn.calls, INSERT_STATUS_SQL).params["status_code"] == "current"


def test_loan_payment_without_active_loan_creates_loan_then_payment() -> None:
    conn = _FakeConnection(active_loan_row=None)
    rng = _SequenceRng(randint_values=[10_000, 30], random_values=[0.1])
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)

    summary = _emit_loan_payment_event(conn, now=now, rng=rng)

    assert summary["primary_event"] == "loan_payment"
    assert summary["created_loan_first"] is True
    assert summary["paid_off"] is False
    assert _find_call(conn.calls, INSERT_LOAN_SQL)
    payment = _find_call(conn.calls, INSERT_PAYMENT_SQL)
    assert payment.params["amount"] == Decimal("3000.00")


def test_loan_payment_caps_to_remaining_and_marks_paid_off() -> None:
    conn = _FakeConnection(
        active_loan_row={
            "loan_id": "loan-1",
            "account_id": "acct-1",
            "status_code": "delinquent",
            "principal_balance": Decimal("100.00"),
            "original_principal_balance": Decimal("1000.00"),
            "days_past_due": 12,
        }
    )
    rng = _SequenceRng(randint_values=[50], random_values=[0.2])
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)

    summary = _emit_loan_payment_event(conn, now=now, rng=rng)

    assert summary["paid_off"] is True
    assert summary["status_code"] == "paid_off"
    assert _find_call(conn.calls, INSERT_PAYMENT_SQL).params["amount"] == Decimal("100.00")
    update = _find_call(conn.calls, UPDATE_LOAN_STATE_SQL)
    assert update.params["principal_balance"] == Decimal("0.00")
    assert update.params["status_code"] == "paid_off"
    assert update.params["days_past_due"] == 0
    status_calls = _find_all_calls(conn.calls, INSERT_STATUS_SQL)
    assert any(call.params["status_code"] == "paid_off" for call in status_calls)


def test_standalone_status_event_toggles_current_to_delinquent() -> None:
    conn = _FakeConnection(
        active_loan_row={
            "loan_id": "loan-2",
            "account_id": "acct-2",
            "status_code": "current",
            "principal_balance": Decimal("2200.00"),
            "original_principal_balance": Decimal("5000.00"),
            "days_past_due": 0,
        }
    )
    rng = _SequenceRng(randint_values=[22])
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)

    summary = _emit_loan_status_history_event(conn, now=now, rng=rng)

    assert summary["primary_event"] == "loan_status_history"
    assert summary["from_status"] == "current"
    assert summary["to_status"] == "delinquent"
    update = _find_call(conn.calls, UPDATE_LOAN_STATE_SQL)
    assert update.params["status_code"] == "delinquent"
    assert update.params["days_past_due"] == 22
    assert _find_call(conn.calls, INSERT_STATUS_SQL).params["status_code"] == "delinquent"


def test_status_event_without_active_loan_falls_back_to_loan_creation() -> None:
    conn = _FakeConnection(active_loan_row=None)
    rng = _SequenceRng(randint_values=[7_500])
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)

    summary = _emit_loan_status_history_event(conn, now=now, rng=rng)

    assert summary["primary_event"] == "loan_status_history_fallback_loan"
    assert _find_call(conn.calls, INSERT_LOAN_SQL).params["status_code"] == "current"
    assert _find_call(conn.calls, INSERT_STATUS_SQL).params["status_code"] == "current"


def test_interval_bounds_use_new_seconds_variables(monkeypatch) -> None:
    monkeypatch.setenv("OLTP_LOAD_GEN_INTERVAL_MS", "1")
    monkeypatch.delenv("OLTP_LOAD_GEN_INTERVAL_MIN_SECONDS", raising=False)
    monkeypatch.delenv("OLTP_LOAD_GEN_INTERVAL_MAX_SECONDS", raising=False)
    assert _read_interval_bounds_seconds() == (10, 60)

    monkeypatch.setenv("OLTP_LOAD_GEN_INTERVAL_MIN_SECONDS", "13")
    monkeypatch.setenv("OLTP_LOAD_GEN_INTERVAL_MAX_SECONDS", "17")
    assert _read_interval_bounds_seconds() == (13, 17)


def test_next_delay_seconds_is_inclusive_on_bounds() -> None:
    low_rng = _SequenceRng(randint_values=[10])
    high_rng = _SequenceRng(randint_values=[60])
    assert _next_delay_seconds(low_rng, min_seconds=10, max_seconds=60) == 10
    assert _next_delay_seconds(high_rng, min_seconds=10, max_seconds=60) == 60
