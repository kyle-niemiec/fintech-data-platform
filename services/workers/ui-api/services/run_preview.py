"""Parse the first rows of an uploaded .xlsx for the read-only run preview.

The route resolves and gates the raw object URI; this module only turns the
workbook bytes into JSON-safe columns/rows. Reuses pandas/openpyxl, already a
dependency for the demo upload generator (services/demo_xlsx.py).
"""

from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd

PREVIEW_ROW_LIMIT = 10


def _json_safe(value: Any) -> Any:
    """Coerce a pandas/numpy cell into a JSON-serialisable scalar."""
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "item"):  # numpy scalar
        try:
            return value.item()
        except (ValueError, TypeError):
            return str(value)
    return value


def parse_xlsx_preview(
    data: bytes, max_rows: int = PREVIEW_ROW_LIMIT
) -> tuple[str, list[str], list[list[Any]]]:
    """Return (sheet_name, columns, rows) for the first sheet's first `max_rows`."""
    workbook = pd.ExcelFile(io.BytesIO(data), engine="openpyxl")
    sheet_name = workbook.sheet_names[0]
    frame = workbook.parse(sheet_name=sheet_name, nrows=max_rows)
    columns = [str(c) for c in frame.columns]
    rows = [
        [_json_safe(cell) for cell in record]
        for record in frame.itertuples(index=False, name=None)
    ]
    return sheet_name, columns, rows
