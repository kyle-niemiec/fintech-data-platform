"""Unit coverage for the demo payroll xlsx generator."""

from __future__ import annotations

from pathlib import Path

from app.services.demo_xlsx import SHEET_NAME, generate_payroll_xlsx
from meridian.libs.excel_validation import load_contract, load_workbook, validate_dataframe

REPO_ROOT = Path(__file__).resolve().parents[1]
PAYROLL_CONTRACT_PATH = (
    REPO_ROOT / "services" / "libs" / "event_schemas" / "payroll_v1.json"
)


def test_generated_xlsx_passes_payroll_contract():
    xlsx_bytes, rows = generate_payroll_xlsx(25, seed=42)
    assert rows == 25
    assert xlsx_bytes.startswith(b"PK")

    frame = load_workbook(xlsx_bytes, sheet_name=SHEET_NAME)
    result = validate_dataframe(frame, load_contract(PAYROLL_CONTRACT_PATH))
    assert result.passed, result.errors_as_list()
    assert result.row_count == 25


def test_generated_xlsx_boundary_row_counts():
    for n in (1, 500):
        xlsx_bytes, rows = generate_payroll_xlsx(n, seed=1)
        assert rows == n
        frame = load_workbook(xlsx_bytes, sheet_name=SHEET_NAME)
        result = validate_dataframe(frame, load_contract(PAYROLL_CONTRACT_PATH))
        assert result.passed, result.errors_as_list()
