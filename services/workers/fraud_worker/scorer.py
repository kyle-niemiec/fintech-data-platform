"""Fraud scoring rules.

Pure-function rule engine; no IO, no Kafka, no DB. Handler layer drives
row extraction from the Debezium envelope and persistence of the result.

Scoring is intentionally versionless for demo simplicity.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


PLATFORM_RISK_THRESHOLD = Decimal("0.8")
RISK_SCORE_QUANT = Decimal("0.0001")
RISK_THRESHOLD_FLAG = "risk_threshold_exceeded"
RISK_THRESHOLD_EPSILON = Decimal("0.000000001")

# Per-instrument dollar amount at which the continuous risk score reaches
# PLATFORM_RISK_THRESHOLD.
INSTRUMENT_RISK_AMOUNTS: dict[str, Decimal] = {
    "AAPL": Decimal("10000"),
    "MSFT": Decimal("14000"),
    "GOOG": Decimal("30000"),
    "AMZN": Decimal("22000"),
    "TSLA": Decimal("8000"),
    "JPM": Decimal("5000"),
    "BAC": Decimal("3000"),
    "NVDA": Decimal("1000"),
}
TRANSACTION_AMOUNT_SCALE = 2


@dataclass(frozen=True)
class RiskAssessment:
    risk_score: Decimal
    risk_flags: list[str]


def score_transaction(row: dict[str, Any]) -> RiskAssessment:
    """Score a transaction row extracted from Debezium `after`.

    Unrecognized rows score 0 with no flags; we still emit an assessed event
    so the bronze stream sees every transaction.
    """
    instrument = row.get("instrument")
    amount_raw = row.get("amount")

    if instrument is None or amount_raw is None:
        return RiskAssessment(Decimal("0"), [])

    try:
        amount = _parse_amount(amount_raw)
    except (ArithmeticError, ValueError):
        return RiskAssessment(Decimal("0"), [])

    threshold_amount = INSTRUMENT_RISK_AMOUNTS.get(str(instrument))
    if threshold_amount is None:
        return RiskAssessment(Decimal("0"), [])

    risk_factor = _risk_factor_from_threshold_amount(threshold_amount)
    risk_score_raw = _bounded_risk_score_raw(amount, risk_factor)
    risk_score = risk_score_raw.quantize(RISK_SCORE_QUANT, rounding=ROUND_HALF_UP)
    flags: list[str] = []
    if risk_score_raw >= (PLATFORM_RISK_THRESHOLD - RISK_THRESHOLD_EPSILON):
        flags.append(RISK_THRESHOLD_FLAG)
        flags.append(f"{str(instrument).lower()}_risk_threshold_exceeded")

    return RiskAssessment(risk_score, flags)


def _parse_amount(raw: Any) -> Decimal:
    """Parse Postgres NUMERIC from CDC value.

    Debezium+Kafka Connect may encode NUMERIC as base64 bytes when schema is
    included (`org.apache.kafka.connect.data.Decimal`), e.g. `"A96M"` for
    450.68 with scale=2.
    """
    try:
        return Decimal(str(raw))
    except (ArithmeticError, ValueError):
        pass

    if isinstance(raw, bytes):
        unscaled = int.from_bytes(raw, byteorder="big", signed=True)
        return Decimal(unscaled) / (Decimal(10) ** TRANSACTION_AMOUNT_SCALE)

    if isinstance(raw, str):
        try:
            decoded = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("amount is neither decimal text nor valid base64 decimal bytes")
        unscaled = int.from_bytes(decoded, byteorder="big", signed=True)
        return Decimal(unscaled) / (Decimal(10) ** TRANSACTION_AMOUNT_SCALE)

    raise ValueError("unsupported amount type")


def _risk_factor_from_threshold_amount(threshold_amount: Decimal) -> Decimal:
    """r_f(X)=X*(1-r_t)/r_t."""
    if threshold_amount <= 0:
        raise ValueError("threshold amount must be > 0")
    return threshold_amount * (Decimal("1") - PLATFORM_RISK_THRESHOLD) / PLATFORM_RISK_THRESHOLD


def _bounded_risk_score_raw(amount: Decimal, risk_factor: Decimal) -> Decimal:
    """r(x)=-r_f/(x+r_f)+1."""
    if amount <= 0:
        return Decimal("0")
    return Decimal("1") - (risk_factor / (amount + risk_factor))
