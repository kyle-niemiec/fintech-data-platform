"""Generate a valid payroll .xlsx in-memory for demo uploads.

Output conforms to the payroll_v1 schema contract:
    platform/libs/platform_events/excel_schemas/payroll_v1.json
"""

from __future__ import annotations

import io
import random
from datetime import datetime, timedelta, timezone

import pandas as pd

SHEET_NAME = "payroll"
CURRENCIES = ("USD", "EUR", "GBP")


def _random_period_end(rng: random.Random, now: datetime) -> datetime:
    days_back = rng.randint(0, 180)
    d = (now - timedelta(days=days_back)).date()
    return datetime(d.year, d.month, d.day)


def build_payroll_frame(rows: int, seed: int | None = None) -> pd.DataFrame:
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
    """Return (xlsx_bytes, row_count). Caller clamps `rows`."""
    frame = build_payroll_frame(rows, seed=seed)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name=SHEET_NAME, index=False)
    return buffer.getvalue(), len(frame)
