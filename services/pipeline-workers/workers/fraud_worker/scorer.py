"""Fraud scoring rules.

Pure-function rule engine; no IO, no Kafka, no DB. Handler layer drives
row extraction from the Debezium envelope and persistence of the result.

Rule evolution policy: bump `RULES_VERSION` whenever semantics change. The
persisted `fraud_rule_version` on each `risk_flag` row makes historical
assessments reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


RULES_VERSION = "rules-v1"

HIGH_VALUE_AAPL_THRESHOLD = Decimal("10000")
HIGH_VALUE_AAPL_INSTRUMENT = "AAPL"
HIGH_VALUE_AAPL_SCORE = Decimal("0.9")
HIGH_VALUE_AAPL_FLAG = "high_value_aapl"


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
        amount = Decimal(str(amount_raw))
    except (ArithmeticError, ValueError):
        return RiskAssessment(Decimal("0"), [], RULES_VERSION)

    flags: list[str] = []
    score = Decimal("0")

    if instrument == HIGH_VALUE_AAPL_INSTRUMENT and amount > HIGH_VALUE_AAPL_THRESHOLD:
        flags.append(HIGH_VALUE_AAPL_FLAG)
        if HIGH_VALUE_AAPL_SCORE > score:
            score = HIGH_VALUE_AAPL_SCORE

    return RiskAssessment(score, flags, RULES_VERSION)
