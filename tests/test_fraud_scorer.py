"""Unit tests for fraud scorer rules."""

from __future__ import annotations

from decimal import Decimal

from workers.fraud_worker.scorer import (
    HIGH_VALUE_AAPL_FLAG,
    HIGH_VALUE_AAPL_SCORE,
    HIGH_VALUE_AAPL_THRESHOLD,
    RULES_VERSION,
    score_transaction,
)


def test_high_value_aapl_flags_above_threshold() -> None:
    result = score_transaction({"instrument": "AAPL", "amount": "10001.00"})
    assert HIGH_VALUE_AAPL_FLAG in result.risk_flags
    assert result.risk_score == HIGH_VALUE_AAPL_SCORE
    assert result.fraud_rule_version == RULES_VERSION


def test_high_value_aapl_threshold_is_strict() -> None:
    # Exactly threshold does NOT trip.
    result = score_transaction({"instrument": "AAPL", "amount": HIGH_VALUE_AAPL_THRESHOLD})
    assert result.risk_flags == []
    assert result.risk_score == Decimal("0")


def test_non_aapl_not_flagged() -> None:
    result = score_transaction({"instrument": "MSFT", "amount": "50000"})
    assert result.risk_flags == []
    assert result.risk_score == Decimal("0")


def test_small_aapl_not_flagged() -> None:
    result = score_transaction({"instrument": "AAPL", "amount": "500"})
    assert result.risk_flags == []


def test_missing_fields_return_zero() -> None:
    result = score_transaction({})
    assert result.risk_flags == []
    assert result.risk_score == Decimal("0")
    assert result.fraud_rule_version == RULES_VERSION
