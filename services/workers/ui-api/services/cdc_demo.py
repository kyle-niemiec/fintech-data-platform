"""Generate and insert a single synthetic OLTP transaction for the CDC demo.

A UI action inserts exactly one `trading.transaction` row (never a loan,
payment, or status event). Debezium captures the insert and the CDC fraud
pipeline scores it. The `high_risk` flag mirrors the fraud shape used by the
background load generator (`oltp_load_generator._emit_transaction_event`) and
the fraud worker rule (instrument == "AAPL" and amount > $10k), so a high-risk
insert deterministically produces a high-severity alert and a risk flag.

Writes go through a dedicated least-privilege `oltp_demo_writer` identity that
can only INSERT into `trading.transaction`; the query plane's read-only role is
never used for writes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import text

# Mirrors oltp_load_generator INSTRUMENTS and the fraud shape, kept in sync with
# the fraud worker rule: instrument == "AAPL" and amount > 10_000 scores high.
INSTRUMENTS = ("AAPL", "MSFT", "GOOG", "AMZN", "TSLA", "JPM", "BAC", "NVDA")
HIGH_RISK_INSTRUMENT = "AAPL"
HIGH_RISK_MIN_AMOUNT = 10_001
HIGH_RISK_MAX_AMOUNT = 50_000
NORMAL_MIN_AMOUNT = 100
NORMAL_MAX_AMOUNT = 9_999

# Provenance value written to trading.transaction.origin for UI-triggered rows.
# Read straight from OLTP by the query plane (transactions list + CDC preview);
# the load generator/app writer leave origin NULL.
MANUAL_ORIGIN = "manual_demo"

INSERT_TRANSACTION_SQL = text(
    """
    INSERT INTO trading.transaction
        (transaction_id, account_id, instrument, amount, executed_at, origin)
    VALUES (:transaction_id, :account_id, :instrument, :amount, :executed_at, :origin)
    """
)


@dataclass(frozen=True)
class DemoTransaction:
    transaction_id: str
    account_id: str
    instrument: str
    amount: Decimal
    executed_at: datetime
    high_risk: bool


def build_demo_transaction(
    *,
    high_risk: bool,
    rng: random.Random | None = None,
    now: datetime | None = None,
) -> DemoTransaction:
    """Build a single transaction spec; high_risk yields the fraud shape."""
    rng = rng or random.Random()
    now = now or datetime.now(timezone.utc)

    if high_risk:
        instrument = HIGH_RISK_INSTRUMENT
        amount = Decimal(rng.randint(HIGH_RISK_MIN_AMOUNT, HIGH_RISK_MAX_AMOUNT))
    else:
        instrument = rng.choice(INSTRUMENTS)
        amount = Decimal(rng.randint(NORMAL_MIN_AMOUNT, NORMAL_MAX_AMOUNT))

    return DemoTransaction(
        transaction_id=str(uuid4()),
        account_id=str(uuid4()),
        instrument=instrument,
        amount=amount,
        executed_at=now,
        high_risk=high_risk,
    )


def insert_demo_transaction(connection: Any, txn: DemoTransaction) -> None:
    """Insert the transaction row using an open (transactional) connection."""
    connection.execute(
        INSERT_TRANSACTION_SQL,
        {
            "transaction_id": txn.transaction_id,
            "account_id": txn.account_id,
            "instrument": txn.instrument,
            "amount": txn.amount,
            "executed_at": txn.executed_at,
            "origin": MANUAL_ORIGIN,
        },
    )


def create_demo_transaction(
    engine: Any,
    *,
    high_risk: bool,
    rng: random.Random | None = None,
    now: datetime | None = None,
) -> DemoTransaction:
    """Build and persist one demo transaction within a single DB transaction."""
    txn = build_demo_transaction(high_risk=high_risk, rng=rng, now=now)
    with engine.begin() as connection:
        insert_demo_transaction(connection, txn)
    return txn
