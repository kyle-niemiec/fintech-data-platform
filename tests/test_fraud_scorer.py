"""Unit tests for fraud scorer rules."""

from __future__ import annotations

import base64
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


def test_high_value_aapl_flags_when_amount_is_kafka_connect_decimal_base64() -> None:
    # Debezium emits NUMERIC as base64 bytes when schema is included.
    unscaled_cents = 10001 * 100
    raw_amount = base64.b64encode(
        unscaled_cents.to_bytes(4, byteorder="big", signed=True)
    ).decode("ascii")
    result = score_transaction({"instrument": "AAPL", "amount": raw_amount})
    assert HIGH_VALUE_AAPL_FLAG in result.risk_flags
    assert result.risk_score == HIGH_VALUE_AAPL_SCORE
