"""Unit coverage for the CDC demo transaction generator.

Covers the fraud-shape contract (high-risk vs normal) and that the insert path
binds every transaction column. No live OLTP database is required: the builder
is pure and the insert is exercised with a fake connection/engine.
"""

from __future__ import annotations

import random

from services.cdc_demo import (
    HIGH_RISK_INSTRUMENT,
    HIGH_RISK_MAX_AMOUNT,
    HIGH_RISK_MIN_AMOUNT,
    INSTRUMENTS,
    NORMAL_MAX_AMOUNT,
    NORMAL_MIN_AMOUNT,
    build_demo_transaction,
    create_demo_transaction,
    insert_demo_transaction,
)


def test_high_risk_matches_fraud_shape():
    for seed in range(25):
        txn = build_demo_transaction(high_risk=True, rng=random.Random(seed))
        assert txn.instrument == HIGH_RISK_INSTRUMENT
        assert HIGH_RISK_MIN_AMOUNT <= int(txn.amount) <= HIGH_RISK_MAX_AMOUNT
        assert int(txn.amount) > 10_000  # trips the fraud worker AAPL>$10k rule
        assert txn.high_risk is True


def test_normal_stays_below_fraud_threshold():
    for seed in range(25):
        txn = build_demo_transaction(high_risk=False, rng=random.Random(seed))
        assert txn.instrument in INSTRUMENTS
        assert NORMAL_MIN_AMOUNT <= int(txn.amount) <= NORMAL_MAX_AMOUNT
        assert int(txn.amount) < 10_000
        assert txn.high_risk is False


def test_ids_are_unique_uuids():
    a = build_demo_transaction(high_risk=False, rng=random.Random(1))
    b = build_demo_transaction(high_risk=False, rng=random.Random(2))
    assert a.transaction_id != b.transaction_id
    assert a.account_id != a.transaction_id


class _FakeConn:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def execute(self, stmt, params):
        self.calls.append((str(stmt), params))


class _FakeEngine:
    def __init__(self, conn):
        self._conn = conn

    def begin(self):
        conn = self._conn

        class _Ctx:
            def __enter__(self_inner):
                return conn

            def __exit__(self_inner, *exc):
                return False

        return _Ctx()


def test_insert_binds_every_transaction_column():
    conn = _FakeConn()
    txn = build_demo_transaction(high_risk=True, rng=random.Random(5))
    insert_demo_transaction(conn, txn)
    sql, params = conn.calls[0]
    assert "INSERT INTO trading.transaction" in sql
    assert set(params) == {
        "transaction_id",
        "account_id",
        "instrument",
        "amount",
        "executed_at",
    }
    assert params["instrument"] == txn.instrument
    assert params["amount"] == txn.amount


def test_create_demo_transaction_inserts_once_within_begin():
    conn = _FakeConn()
    txn = create_demo_transaction(_FakeEngine(conn), high_risk=False, rng=random.Random(3))
    assert len(conn.calls) == 1
    assert conn.calls[0][1]["transaction_id"] == txn.transaction_id
