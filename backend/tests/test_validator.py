"""Unit coverage for the Excel schema validator."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
import pytest

from libs.excel_validation import (
    SchemaContract,
    ValidationError,
    ValidationResult,
    load_contract,
    load_workbook,
    validate_dataframe,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PAYROLL_CONTRACT_PATH = (
    REPO_ROOT / "backend" / "libs" / "platform_events" / "excel_schemas" / "payroll_v1.json"
)


def _contract() -> SchemaContract:
    return load_contract(PAYROLL_CONTRACT_PATH)


def _valid_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "employee_id": ["E1", "E2"],
            "pay_period_end": pd.to_datetime(["2026-04-13", "2026-04-13"]),
            "gross_amount": [5000.0, 6250.0],
            "net_amount": [3750.0, 4600.0],
            "currency": ["USD", "USD"],
        }
    )


def test_payroll_contract_loads():
    contract = _contract()
    assert contract.contract_id == "payroll_v1"
    assert "employee_id" in contract.required_columns
    assert contract.column_types["gross_amount"] == "float64"


def test_valid_frame_passes():
    result = validate_dataframe(_valid_frame(), _contract())
    assert result.passed is True
    assert result.row_count == 2
    assert result.errors == ()


def test_missing_column_reported():
    df = _valid_frame().drop(columns=["currency"])
    result = validate_dataframe(df, _contract())
    assert not result.passed
    kinds = {e.kind for e in result.errors}
    assert "missing_column" in kinds
    assert any(e.column == "currency" for e in result.errors)


def test_type_mismatch_reported():
    df = _valid_frame()
    # Cast to a type that should never satisfy a float contract
    df["gross_amount"] = df["gross_amount"].astype(str)
    result = validate_dataframe(df, _contract())
    assert not result.passed
    assert any(e.kind == "type_mismatch" and e.column == "gross_amount" for e in result.errors)


def test_null_in_required_column_reported():
    df = _valid_frame()
    df.loc[0, "employee_id"] = None
    result = validate_dataframe(df, _contract())
    assert not result.passed
    null_errors = [e for e in result.errors if e.kind == "null_values"]
    assert null_errors
    assert null_errors[0].column == "employee_id"


def test_multiple_errors_accumulate():
    df = _valid_frame().drop(columns=["currency"])
    df["gross_amount"] = df["gross_amount"].astype(str)
    result = validate_dataframe(df, _contract())
    assert len(result.errors) >= 2
    kinds = {e.kind for e in result.errors}
    assert {"missing_column", "type_mismatch"}.issubset(kinds)


def test_load_workbook_roundtrip(tmp_path):
    df = _valid_frame()
    p = tmp_path / "valid.xlsx"
    with pd.ExcelWriter(p, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="payroll", index=False)

    loaded = load_workbook(p.read_bytes(), sheet_name="payroll")
    result = validate_dataframe(loaded, _contract())
    assert result.passed, result.errors_as_list()
    assert result.row_count == len(df)


def test_errors_as_list_shape():
    df = _valid_frame().drop(columns=["currency"])
    result = validate_dataframe(df, _contract())
    errors_list = result.errors_as_list()
    assert errors_list
    for e in errors_list:
        assert set(e.keys()) == {"kind", "column", "detail"}
