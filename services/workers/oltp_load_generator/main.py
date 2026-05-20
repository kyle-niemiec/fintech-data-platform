"""Synthetic OLTP transaction generator.

Runs continuously in the demo stack so CDC/fraud/bronze have fresh data to
chew on. The UI is read-only, so this is the only path that populates
`trading.transaction`. A configurable fraction of emits are high-value AAPL
trades so the fraud rule fires on a predictable cadence.
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
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

logger = logging.getLogger("oltp_load_generator")

INSTRUMENTS = ["AAPL", "MSFT", "GOOG", "AMZN", "TSLA", "JPM", "BAC", "NVDA"]
LOAN_STATUSES = ["current", "delinquent", "charged_off", "paid_off"]

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
        (loan_id, account_id, status_code, principal_balance, days_past_due, updated_at)
    VALUES (:loan_id, :account_id, :status_code, :principal_balance, :days_past_due, :updated_at)
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


def _generate_row(
    fraud_fraction: float,
) -> tuple[
    tuple[str, str, str, Decimal, datetime],
    tuple[str, str, str, Decimal, int, datetime],
    tuple[str, str, Decimal, date, date | None, str, datetime],
    tuple[str, str, str, datetime, datetime],
]:
    """
    Generate a synthetic transaction, loan, payment, and status update. A fraction of transactions are
    fraudulent (high-value AAPL trades) based on the `fraud_fraction` parameter.
    """
    transaction_id = str(uuid4())
    account_id = str(uuid4())
    loan_id = str(uuid4())

    # Maybe emit a fraudulent transaction with high-value AAPL trade to trigger the fraud rule
    if random.random() < fraud_fraction:
        instrument = "AAPL"
        amount = Decimal(random.randint(10_001, 50_000))
    else:
        instrument = random.choice(INSTRUMENTS)
        amount = Decimal(random.randint(100, 9_999))

    # Randomly assign a loan status, balance, and due date
    status_code = random.choice(LOAN_STATUSES)
    principal_balance = Decimal(random.randint(2_000, 75_000))
    days_past_due = 0 if status_code == "current" else random.randint(1, 90)

    today = datetime.now(timezone.utc).date()
    due_date = today
    posted_at = due_date if random.random() < 0.85 else None
    payment_amount = Decimal(random.randint(100, 2_500))

    now = datetime.now(timezone.utc)

    # Return a tuple of rows to insert into transaction, loan, payment, and status tables
    return (
        (transaction_id, account_id, instrument, amount, now),
        (loan_id, account_id, status_code, principal_balance, days_past_due, now),
        (str(uuid4()), loan_id, payment_amount, due_date, posted_at, "USD", now),
        (str(uuid4()), loan_id, status_code, now, now),
    )


def run() -> None:
    """
    Main loop for the OLTP load generator. Continuously generates synthetic
    transactions, loans, payments, and status updates and inserts them into the
    OLTP database at a configurable interval. A fraction of transactions are
    fraudulent (high-value AAPL trades) based on the `OLTP_LOAD_GEN_FRAUD_FRACTION`
    environment variable.
    """
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    interval_s = int(os.environ.get("OLTP_LOAD_GEN_INTERVAL_MS", "60000")) / 1000.0
    fraud_fraction = float(os.environ.get("OLTP_LOAD_GEN_FRAUD_FRACTION", "0.1"))

    shutdown = {"stop": False}

    def _handle_signal(signum, _frame) -> None:  # type: ignore[no-untyped-def]
        logger.info("signal %s received, shutting down", signum)
        shutdown["stop"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    conn = _connect()

    try:
        engine, connection = conn

        # Continuously generate and insert rows until shutdown signal is received.
        # Sleep in small increments between inserts.
        while not shutdown["stop"]:
            txn, loan, payment, status = _generate_row(fraud_fraction)

            with connection.begin():
                # Insert the transaction
                connection.execute(
                    INSERT_TRANSACTION_SQL,
                    {
                        "transaction_id": txn[0],
                        "account_id": txn[1],
                        "instrument": txn[2],
                        "amount": txn[3],
                        "executed_at": txn[4],
                    },
                )

                # Insert the loan
                connection.execute(
                    INSERT_LOAN_SQL,
                    {
                        "loan_id": loan[0],
                        "account_id": loan[1],
                        "status_code": loan[2],
                        "principal_balance": loan[3],
                        "days_past_due": loan[4],
                        "updated_at": loan[5],
                    },
                )

                # Insert the payment
                connection.execute(
                    INSERT_PAYMENT_SQL,
                    {
                        "payment_id": payment[0],
                        "loan_id": payment[1],
                        "amount": payment[2],
                        "due_date": payment[3],
                        "posted_at": payment[4],
                        "currency": payment[5],
                        "updated_at": payment[6],
                    },
                )

                # Insert the status
                connection.execute(
                    INSERT_STATUS_SQL,
                    {
                        "status_event_id": status[0],
                        "loan_id": status[1],
                        "status_code": status[2],
                        "status_at": status[3],
                        "updated_at": status[4],
                    },
                )

            # Log the transaction
            logger.info(
                "oltp_insert transaction_id=%s loan_id=%s instrument=%s amount=%s status=%s",
                txn[0], loan[0], txn[2], txn[3], loan[2],
            )

            # Sleep in small intervals for a delay between inserts, checking for shutdown signal
            remaining = interval_s

            while remaining > 0 and not shutdown["stop"]:
                nap = min(1.0, remaining)
                time.sleep(nap)
                remaining -= nap
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
