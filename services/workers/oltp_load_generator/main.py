"""
Synthetic OLTP event generator for the CDC demo pipeline.

Each cycle emits one primary event type (`transaction`, `loan`,
`loan_payment`, or `loan_status_history`) plus required same-cycle side
effects to keep loan lifecycle data consistent.
"""

from __future__ import annotations

import logging
import os
import random
import signal
import sys
import time
from datetime import date
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

logger = logging.getLogger("oltp_load_generator")

INSTRUMENTS = ["AAPL", "MSFT", "GOOG", "AMZN", "TSLA", "JPM", "BAC", "NVDA"]
ACTIVE_LOAN_STATUSES = ("current", "delinquent")
PRIMARY_EVENT_TYPES = ("transaction", "loan", "loan_payment", "loan_status_history")
MIN_PAYMENT_RATIO_PERCENT = 20
MAX_PAYMENT_RATIO_PERCENT = 50

# TECH-DEBT: SQL statements need to be consolidated outside of Python code
INSERT_TRANSACTION_SQL = text(
    """
    INSERT INTO trading.transaction
        (transaction_id, account_id, instrument, amount, executed_at)
    VALUES (:transaction_id, :account_id, :instrument, :amount, :executed_at)
    """
)

INSERT_LOAN_SQL = text(
    """
    INSERT INTO trading.loan
        (
            loan_id,
            account_id,
            status_code,
            principal_balance,
            original_principal_balance,
            days_past_due,
            updated_at
        )
    VALUES (
        :loan_id,
        :account_id,
        :status_code,
        :principal_balance,
        :original_principal_balance,
        :days_past_due,
        :updated_at
    )
    """
)

INSERT_PAYMENT_SQL = text(
    """
    INSERT INTO trading.loan_payment
        (payment_id, loan_id, amount, due_date, posted_at, currency, updated_at)
    VALUES (:payment_id, :loan_id, :amount, :due_date, :posted_at, :currency, :updated_at)
    """
)

INSERT_STATUS_SQL = text(
    """
    INSERT INTO trading.loan_status_history
        (status_event_id, loan_id, status_code, status_at, updated_at)
    VALUES (:status_event_id, :loan_id, :status_code, :status_at, :updated_at)
    """
)

SELECT_RANDOM_ACTIVE_LOAN_SQL = text(
    """
    SELECT
        loan_id,
        account_id,
        status_code,
        principal_balance,
        original_principal_balance,
        days_past_due
    FROM trading.loan
    WHERE status_code = ANY(:active_statuses)
    ORDER BY random()
    LIMIT 1
    """
)

UPDATE_LOAN_STATE_SQL = text(
    """
    UPDATE trading.loan
    SET
        status_code = :status_code,
        principal_balance = :principal_balance,
        days_past_due = :days_past_due,
        updated_at = :updated_at
    WHERE loan_id = :loan_id
    """
)


def _connect():
    """
    Build a connection to the OLTP database using credentials from environment variables.

    TECH-DEBT: Reused code for building platform services should be consolidated using factories.
    """
    url = URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["OLTP_APP_USER"],
        password=os.environ["OLTP_APP_PASSWORD"],
        host=os.environ["OLTP_DB_HOST"],
        port=int(os.environ["OLTP_DB_PORT"]),
        database=os.environ["OLTP_DB"],
    )

    engine = create_engine(url)
    return engine, engine.connect()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _read_interval_bounds_seconds() -> tuple[int, int]:
    min_seconds = int(os.environ.get("OLTP_LOAD_GEN_INTERVAL_MIN_SECONDS", "30"))
    max_seconds = int(os.environ.get("OLTP_LOAD_GEN_INTERVAL_MAX_SECONDS", "60"))

    if min_seconds < 1:
        raise ValueError("OLTP_LOAD_GEN_INTERVAL_MIN_SECONDS must be >= 1")

    if max_seconds < min_seconds:
        raise ValueError("OLTP_LOAD_GEN_INTERVAL_MAX_SECONDS must be >= min seconds")

    return min_seconds, max_seconds


def _sleep_with_shutdown(shutdown: dict[str, bool], *, seconds: int) -> None:
    remaining = float(seconds)

    while remaining > 0 and not shutdown["stop"]:
        nap = min(1.0, remaining)
        time.sleep(nap)
        remaining -= nap


def _pick_primary_event(rng: random.Random) -> str:
    return rng.choice(PRIMARY_EVENT_TYPES)


def _next_delay_seconds(rng: random.Random, *, min_seconds: int, max_seconds: int) -> int:
    return int(rng.randint(min_seconds, max_seconds))


def _append_status_history(
    connection: Any,
    *,
    loan_id: str,
    status_code: str,
    status_at: datetime,
) -> None:
    connection.execute(
        INSERT_STATUS_SQL,
        {
            "status_event_id": str(uuid4()),
            "loan_id": loan_id,
            "status_code": status_code,
            "status_at": status_at,
            "updated_at": status_at,
        },
    )


def _emit_transaction_event(
    connection: Any,
    *,
    now: datetime,
    fraud_fraction: float,
    rng: random.Random,
) -> dict[str, Any]:
    transaction_id = str(uuid4())
    account_id = str(uuid4())

    if rng.random() < fraud_fraction:
        instrument = "AAPL"
        amount = Decimal(rng.randint(10_001, 50_000))
    else:
        instrument = rng.choice(INSTRUMENTS)
        amount = Decimal(rng.randint(100, 9_999))

    connection.execute(
        INSERT_TRANSACTION_SQL,
        {
            "transaction_id": transaction_id,
            "account_id": account_id,
            "instrument": instrument,
            "amount": amount,
            "executed_at": now,
        },
    )

    return {
        "primary_event": "transaction",
        "transaction_id": transaction_id,
        "instrument": instrument,
        "amount": str(amount),
    }


def _create_current_loan(
    connection: Any,
    *,
    now: datetime,
    rng: random.Random,
) -> dict[str, Any]:
    loan_id = str(uuid4())
    account_id = str(uuid4())
    principal = Decimal(rng.randint(2_000, 75_000))

    connection.execute(
        INSERT_LOAN_SQL,
        {
            "loan_id": loan_id,
            "account_id": account_id,
            "status_code": "current",
            "principal_balance": principal,
            "original_principal_balance": principal,
            "days_past_due": 0,
            "updated_at": now,
        },
    )
    _append_status_history(connection, loan_id=loan_id, status_code="current", status_at=now)

    return {
        "loan_id": loan_id,
        "account_id": account_id,
        "status_code": "current",
        "principal_balance": principal,
        "original_principal_balance": principal,
        "days_past_due": 0,
    }


def _fetch_random_active_loan(connection: Any) -> dict[str, Any] | None:
    row = connection.execute(
        SELECT_RANDOM_ACTIVE_LOAN_SQL,
        {"active_statuses": list(ACTIVE_LOAN_STATUSES)},
    ).mappings().fetchone()

    return dict(row) if row is not None else None


def _emit_loan_event(
    connection: Any,
    *,
    now: datetime,
    rng: random.Random,
) -> dict[str, Any]:
    loan = _create_current_loan(connection, now=now, rng=rng)
    return {
        "primary_event": "loan",
        "loan_id": loan["loan_id"],
        "status_code": loan["status_code"],
        "principal_balance": str(loan["principal_balance"]),
    }


def _emit_loan_payment_event(
    connection: Any,
    *,
    now: datetime,
    rng: random.Random,
) -> dict[str, Any]:
    loan = _fetch_random_active_loan(connection)
    created_loan = False

    if loan is None:
        loan = _create_current_loan(connection, now=now, rng=rng)
        created_loan = True

    ratio_percent = rng.randint(MIN_PAYMENT_RATIO_PERCENT, MAX_PAYMENT_RATIO_PERCENT)
    original_balance = Decimal(loan["original_principal_balance"])
    remaining_balance = Decimal(loan["principal_balance"])
    desired_payment = (
        original_balance * Decimal(ratio_percent) / Decimal(100)
    ).quantize(Decimal("0.01"))
    payment_amount = desired_payment if desired_payment <= remaining_balance else remaining_balance

    due_date = now.date()
    posted_at: date | None = due_date if rng.random() < 0.85 else None
    payment_id = str(uuid4())

    connection.execute(
        INSERT_PAYMENT_SQL,
        {
            "payment_id": payment_id,
            "loan_id": loan["loan_id"],
            "amount": payment_amount,
            "due_date": due_date,
            "posted_at": posted_at,
            "currency": "USD",
            "updated_at": now,
        },
    )

    new_balance = (remaining_balance - payment_amount).quantize(Decimal("0.01"))
    status_code = str(loan["status_code"])
    days_past_due = int(loan["days_past_due"])
    paid_off = False

    if new_balance <= Decimal("0.00"):
        new_balance = Decimal("0.00")
        status_code = "paid_off"
        days_past_due = 0
        paid_off = True

    connection.execute(
        UPDATE_LOAN_STATE_SQL,
        {
            "loan_id": loan["loan_id"],
            "status_code": status_code,
            "principal_balance": new_balance,
            "days_past_due": days_past_due,
            "updated_at": now,
        },
    )

    if paid_off:
        _append_status_history(connection, loan_id=loan["loan_id"], status_code="paid_off", status_at=now)

    return {
        "primary_event": "loan_payment",
        "loan_id": loan["loan_id"],
        "payment_id": payment_id,
        "payment_amount": str(payment_amount),
        "remaining_principal_balance": str(new_balance),
        "status_code": status_code,
        "created_loan_first": created_loan,
        "paid_off": paid_off,
    }


def _emit_loan_status_history_event(
    connection: Any,
    *,
    now: datetime,
    rng: random.Random,
) -> dict[str, Any]:
    loan = _fetch_random_active_loan(connection)

    if loan is None:
        fallback = _emit_loan_event(connection, now=now, rng=rng)
        fallback["primary_event"] = "loan_status_history_fallback_loan"
        return fallback

    previous_status = str(loan["status_code"])
    next_status = "delinquent" if previous_status == "current" else "current"
    days_past_due = rng.randint(1, 90) if next_status == "delinquent" else 0

    connection.execute(
        UPDATE_LOAN_STATE_SQL,
        {
            "loan_id": loan["loan_id"],
            "status_code": next_status,
            "principal_balance": Decimal(loan["principal_balance"]),
            "days_past_due": days_past_due,
            "updated_at": now,
        },
    )
    _append_status_history(connection, loan_id=loan["loan_id"], status_code=next_status, status_at=now)

    return {
        "primary_event": "loan_status_history",
        "loan_id": loan["loan_id"],
        "from_status": previous_status,
        "to_status": next_status,
        "days_past_due": days_past_due,
    }


def _emit_primary_event(
    connection: Any,
    *,
    now: datetime,
    fraud_fraction: float,
    rng: random.Random,
) -> dict[str, Any]:
    primary = _pick_primary_event(rng)

    if primary == "transaction":
        return _emit_transaction_event(connection, now=now, fraud_fraction=fraud_fraction, rng=rng)
    if primary == "loan":
        return _emit_loan_event(connection, now=now, rng=rng)
    if primary == "loan_payment":
        return _emit_loan_payment_event(connection, now=now, rng=rng)

    return _emit_loan_status_history_event(connection, now=now, rng=rng)


def run() -> None:
    """
    Continuously emit OLTP events for the CDC/fraud/bronze demo stack.
    """
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    min_interval_s, max_interval_s = _read_interval_bounds_seconds()
    fraud_fraction = float(os.environ.get("OLTP_LOAD_GEN_FRAUD_FRACTION", "0.05"))
    rng = random.Random()
    shutdown = {"stop": False}

    def _handle_signal(signum, _frame) -> None:  # type: ignore[no-untyped-def]
        logger.info("signal %s received, shutting down", signum)
        shutdown["stop"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    conn = _connect()

    try:
        engine, connection = conn

        while not shutdown["stop"]:
            with connection.begin():
                summary = _emit_primary_event(
                    connection,
                    now=_now_utc(),
                    fraud_fraction=fraud_fraction,
                    rng=rng,
                )

            logger.info(
                "oltp_event primary=%s transaction_id=%s loan_id=%s payment_id=%s status=%s amount=%s",
                summary.get("primary_event"),
                summary.get("transaction_id"),
                summary.get("loan_id"),
                summary.get("payment_id"),
                summary.get("status_code") or summary.get("to_status"),
                summary.get("amount") or summary.get("payment_amount"),
            )

            delay_s = _next_delay_seconds(
                rng,
                min_seconds=min_interval_s,
                max_seconds=max_interval_s,
            )
            _sleep_with_shutdown(shutdown, seconds=delay_s)
    finally:
        engine, connection = conn

        try:
            connection.close()
        finally:
            engine.dispose()


if __name__ == "__main__":
    try:
        run()
    except Exception:
        logger.exception("oltp_load_generator crashed")
        sys.exit(1)
