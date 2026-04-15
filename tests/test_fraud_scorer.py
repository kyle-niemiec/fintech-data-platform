"""Unit tests for fraud scorer rules."""

from __future__ import annotations

import base64
from decimal import Decimal

from workers.fraud_worker.scorer import (
    INSTRUMENT_RISK_AMOUNTS,
    PLATFORM_RISK_THRESHOLD,
    RISK_THRESHOLD_FLAG,
    score_transaction,
)


def _encode_scale2(amount: int) -> str:
    unscaled_cents = amount * 100
    return base64.b64encode(
        unscaled_cents.to_bytes(4, byteorder="big", signed=True)
    ).decode("ascii")


def test_all_instruments_have_threshold_amounts_in_expected_range() -> None:
    assert INSTRUMENT_RISK_AMOUNTS
    for amount in INSTRUMENT_RISK_AMOUNTS.values():
        assert Decimal("1000") <= amount <= Decimal("30000")


def test_each_instrument_crosses_platform_threshold_at_calibrated_amount() -> None:
    for instrument, amount in INSTRUMENT_RISK_AMOUNTS.items():
        result = score_transaction({"instrument": instrument, "amount": str(amount)})
        assert result.risk_score == PLATFORM_RISK_THRESHOLD
        assert RISK_THRESHOLD_FLAG in result.risk_flags


def test_each_instrument_is_below_threshold_just_under_calibrated_amount() -> None:
    for instrument, amount in INSTRUMENT_RISK_AMOUNTS.items():
        result = score_transaction({"instrument": instrument, "amount": str(amount - 1)})
        assert RISK_THRESHOLD_FLAG not in result.risk_flags


def test_aapl_continuous_score_is_between_zero_and_threshold_midway() -> None:
    result = score_transaction({"instrument": "AAPL", "amount": "5000"})
    # With r_t=0.7 and X=10000 -> r_f=4285.714..., midpoint score is ~0.5385.
    assert result.risk_score == Decimal("0.5385")
    assert result.risk_flags == []


def test_base64_kafka_connect_decimal_is_scored() -> None:
    # 12,000 > AAPL calibrated threshold (10,000), so this must be flagged.
    result = score_transaction({"instrument": "AAPL", "amount": _encode_scale2(12000)})
    assert result.risk_score >= PLATFORM_RISK_THRESHOLD
    assert RISK_THRESHOLD_FLAG in result.risk_flags


def test_missing_fields_return_zero() -> None:
    result = score_transaction({})
    assert result.risk_flags == []
    assert result.risk_score == Decimal("0")
