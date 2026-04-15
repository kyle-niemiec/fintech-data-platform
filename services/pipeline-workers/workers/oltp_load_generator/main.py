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
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import psycopg

logger = logging.getLogger("oltp_load_generator")

INSTRUMENTS = ["AAPL", "MSFT", "GOOG", "AMZN", "TSLA", "JPM", "BAC", "NVDA"]


def _connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ["OLTP_DB_HOST"],
        port=int(os.environ["OLTP_DB_PORT"]),
        dbname=os.environ["OLTP_DB"],
        user=os.environ["OLTP_APP_USER"],
        password=os.environ["OLTP_APP_PASSWORD"],
        autocommit=True,
    )


def _generate_row(fraud_fraction: float) -> tuple[str, str, str, Decimal, datetime]:
    transaction_id = str(uuid4())
    account_id = str(uuid4())
    if random.random() < fraud_fraction:
        instrument = "AAPL"
        amount = Decimal(random.randint(10_001, 50_000))
    else:
        instrument = random.choice(INSTRUMENTS)
        amount = Decimal(random.randint(100, 9_999))
    return transaction_id, account_id, instrument, amount, datetime.now(timezone.utc)


def run() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    interval_s = int(os.environ.get("OLTP_LOAD_GEN_INTERVAL_MS", "60000")) / 1000.0
    fraud_fraction = float(os.environ.get("OLTP_LOAD_GEN_FRAUD_FRACTION", "0.25"))

    shutdown = {"stop": False}

    def _handle_signal(signum, _frame) -> None:  # type: ignore[no-untyped-def]
        logger.info("signal %s received, shutting down", signum)
        shutdown["stop"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    conn = _connect()
    try:
        while not shutdown["stop"]:
            txn = _generate_row(fraud_fraction)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO trading.transaction
                        (transaction_id, account_id, instrument, amount, executed_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    txn,
                )
            logger.info(
                "oltp_insert transaction_id=%s instrument=%s amount=%s",
                txn[0], txn[2], txn[3],
            )
            # Sleep in small slices so shutdown is responsive.
            remaining = interval_s
            while remaining > 0 and not shutdown["stop"]:
                nap = min(1.0, remaining)
                time.sleep(nap)
                remaining -= nap
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        run()
    except Exception:
        logger.exception("oltp_load_generator crashed")
        sys.exit(1)
