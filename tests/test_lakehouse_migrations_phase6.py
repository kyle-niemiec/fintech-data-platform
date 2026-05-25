"""Ensure follow-on lakehouse migrations exist."""

from __future__ import annotations

from pathlib import Path


MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[1]
    / "infra"
    / "db"
    / "lakehouse-migrations"
)


def test_phase6_follow_on_migrations_exist() -> None:
    expected = {
        "03_silver_dim_account.sql",
        "04_silver_dim_loan.sql",
        "05_silver_fact_loan_payment.sql",
        "06_silver_loan_status_history.sql",
        "07_silver_fact_commission_adjustment.sql",
        "08_gold_kpi_portfolio_health.sql",
        "09_gold_kpi_payment_performance.sql",
        "10_gold_kpi_commission_economics.sql",
    }
    filenames = {p.name for p in MIGRATIONS_DIR.glob("*.sql")}
    assert expected.issubset(filenames)
