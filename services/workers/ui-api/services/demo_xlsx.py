"""
Generate a valid payroll .xlsx in-memory for demo uploads.

Output conforms to the payroll_v1 schema contract:
    services/libs/event_schemas/payroll_v1.json
"""

from __future__ import annotations

import io
import random
from datetime import datetime, timedelta, timezone

import pandas as pd

SHEET_NAME = "payroll"
CURRENCIES = ("USD", "EUR", "GBP")


def _random_period_end(rng: random.Random, now: datetime) -> datetime:
    """
    Return a random date within the last 180 days.
    """
    days_back = rng.randint(0, 180)
    d = (now - timedelta(days=days_back)).date()
    return datetime(d.year, d.month, d.day)


def build_payroll_frame(rows: int, seed: int | None = None) -> pd.DataFrame:
    """
    Build a DataFrame with synthetic payroll data.
    """
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)

    employee_ids = [f"E{rng.randint(10_000, 99_999)}" for _ in range(rows)]
    pay_period_end = [_random_period_end(rng, now) for _ in range(rows)]
    gross = [round(rng.uniform(2500.0, 18000.0), 2) for _ in range(rows)]
    net = [round(g * rng.uniform(0.62, 0.82), 2) for g in gross]
    currency = [rng.choice(CURRENCIES) for _ in range(rows)]

    return pd.DataFrame(
        {
            "employee_id": employee_ids,
            "pay_period_end": pd.to_datetime(pay_period_end),
            "gross_amount": gross,
            "net_amount": net,
            "currency": currency,
        }
    )


def generate_payroll_xlsx(rows: int, seed: int | None = None) -> tuple[bytes, int]:
    """
    Return (xlsx_bytes, row_count). Caller clamps `rows`.
    """
    frame = build_payroll_frame(rows, seed=seed)
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name=SHEET_NAME, index=False)

    return buffer.getvalue(), len(frame)


def build_invalid_payroll_frame(rows: int, seed: int | None = None) -> pd.DataFrame:
    """
    Build a payroll frame that is a structurally valid workbook (so it clears the
    virus/MIME scan) but violates the payroll_v1 schema contract by dropping the
    required `net_amount` column. The validation DAG quarantines it, exercising
    the failure path end-to-end for demos.
    """
    return build_payroll_frame(rows, seed=seed).drop(columns=["net_amount"])


def generate_invalid_payroll_xlsx(rows: int, seed: int | None = None) -> tuple[bytes, int]:
    """
    Return (xlsx_bytes, row_count) for a schema-violating payroll workbook.
    """
    frame = build_invalid_payroll_frame(rows, seed=seed)
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name=SHEET_NAME, index=False)

    return buffer.getvalue(), len(frame)


COMMISSION_SHEET_NAME = "commission_adjustments"


def build_commission_adjustment_frame(rows: int, seed: int | None = None) -> pd.DataFrame:
    """
    Build a DataFrame with synthetic commission adjustment data.
    """
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    advisor_ids = [f"A{rng.randint(10_000, 99_999)}" for _ in range(rows)]
    adjustment_date = [_random_period_end(rng, now) for _ in range(rows)]
    adjustment_amount = [round(rng.uniform(-900.0, 2400.0), 2) for _ in range(rows)]
    reasons = [rng.choice(("retro_credit", "chargeback", "manual_override")) for _ in range(rows)]
    currency = [rng.choice(CURRENCIES) for _ in range(rows)]

    return pd.DataFrame(
        {
            "advisor_id": advisor_ids,
            "adjustment_date": pd.to_datetime(adjustment_date),
            "adjustment_amount": adjustment_amount,
            "adjustment_reason": reasons,
            "currency": currency,
        }
    )


def generate_commission_adjustment_xlsx(rows: int, seed: int | None = None) -> tuple[bytes, int]:
    """
    Return (xlsx_bytes, row_count) for a commission adjustment sheet.
    """
    frame = build_commission_adjustment_frame(rows, seed=seed)
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name=COMMISSION_SHEET_NAME, index=False)

    return buffer.getvalue(), len(frame)
