"""Unit coverage for the Excel run-preview parser.

Exercises the real pandas/openpyxl path: build a workbook in memory, then assert
the parser caps rows and produces JSON-safe scalars (dates → ISO strings, NaN →
None).
"""

from __future__ import annotations

import io

import pandas as pd

from services.run_preview import parse_xlsx_preview


def _workbook_bytes(frame: pd.DataFrame, sheet_name: str) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name=sheet_name, index=False)
    return buffer.getvalue()


def test_parse_xlsx_preview_caps_rows_and_is_json_safe():
    frame = pd.DataFrame(
        {
            "employee_id": [f"E{i}" for i in range(12)],
            "pay_period_end": pd.to_datetime(["2026-01-15"] * 12),
            "net_amount": [100.0 if i != 0 else None for i in range(12)],
        }
    )
    sheet_name, columns, rows = parse_xlsx_preview(
        _workbook_bytes(frame, "payroll"), max_rows=10
    )

    assert sheet_name == "payroll"
    assert columns == ["employee_id", "pay_period_end", "net_amount"]
    assert len(rows) == 10  # capped at max_rows, not all 12

    # Date cell is serialised to an ISO string, not a Timestamp.
    assert isinstance(rows[0][1], str)
    assert rows[0][1].startswith("2026-01-15")
    # Missing numeric (NaN) becomes JSON null.
    assert rows[0][2] is None
    assert rows[1][2] == 100.0


def test_parse_xlsx_preview_uses_first_sheet():
    frame = pd.DataFrame({"advisor_id": ["A1"], "adjustment_amount": [12.5]})
    sheet_name, columns, rows = parse_xlsx_preview(
        _workbook_bytes(frame, "commission_adjustments")
    )
    assert sheet_name == "commission_adjustments"
    assert columns == ["advisor_id", "adjustment_amount"]
    assert rows == [["A1", 12.5]]
