"""Fraud scoring rules.

Pure-function rule engine; no IO, no Kafka, no DB. Handler layer drives
row extraction from the Debezium envelope and persistence of the result.

Rule evolution policy: bump `RULES_VERSION` whenever semantics change. The
persisted `fraud_rule_version` on each `risk_flag` row makes historical
assessments reproducible.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


RULES_VERSION = "rules-v1"

HIGH_VALUE_AAPL_THRESHOLD = Decimal("10000")
HIGH_VALUE_AAPL_INSTRUMENT = "AAPL"
HIGH_VALUE_AAPL_SCORE = Decimal("0.9")
HIGH_VALUE_AAPL_FLAG = "high_value_aapl"
TRANSACTION_AMOUNT_SCALE = 2


@dataclass(frozen=True)
class RiskAssessment:
    risk_score: Decimal
    risk_flags: list[str]
    fraud_rule_version: str


def score_transaction(row: dict[str, Any]) -> RiskAssessment:
    """Score a transaction row extracted from Debezium `after`.

    Unrecognized rows score 0 with no flags; we still emit an assessed event
    so the bronze stream sees every transaction.
    """
    instrument = row.get("instrument")
    amount_raw = row.get("amount")

    if instrument is None or amount_raw is None:
        return RiskAssessment(Decimal("0"), [], RULES_VERSION)

    try:
        amount = _parse_amount(amount_raw)
    except (ArithmeticError, ValueError):
        return RiskAssessment(Decimal("0"), [], RULES_VERSION)

    flags: list[str] = []
    score = Decimal("0")

    if instrument == HIGH_VALUE_AAPL_INSTRUMENT and amount > HIGH_VALUE_AAPL_THRESHOLD:
        flags.append(HIGH_VALUE_AAPL_FLAG)
        if HIGH_VALUE_AAPL_SCORE > score:
            score = HIGH_VALUE_AAPL_SCORE

    return RiskAssessment(score, flags, RULES_VERSION)


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
