"""Pure validation logic for Excel payloads.

The Airflow DAG calls these helpers. Keeping them outside `airflow/` lets
unit tests run without the Airflow runtime. A schema contract is a small
JSON file declaring required columns and their expected pandas dtypes;
contracts live under platform/libs/platform_events/excel_schemas/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Optional

import pandas as pd


@dataclass(frozen=True)
class SchemaContract:
    contract_id: str
    sheet_name: Optional[str]
    required_columns: tuple[str, ...]
    column_types: dict[str, str]
    disallow_null_columns: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SchemaContract":
        return cls(
            contract_id=raw["contract_id"],
            sheet_name=raw.get("sheet_name"),
            required_columns=tuple(raw["required_columns"]),
            column_types=dict(raw.get("column_types", {})),
            disallow_null_columns=tuple(raw.get("disallow_null_columns", [])),
        )


@dataclass(frozen=True)
class ValidationError:
    kind: str
    column: Optional[str]
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "column": self.column, "detail": self.detail}


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    row_count: int
    errors: tuple[ValidationError, ...] = field(default_factory=tuple)

    def errors_as_list(self) -> list[dict[str, Any]]:
        return [e.as_dict() for e in self.errors]


def load_contract(path: Path) -> SchemaContract:
    return SchemaContract.from_dict(json.loads(path.read_text(encoding="utf-8")))


def load_workbook(source: BinaryIO | bytes, *, sheet_name: Optional[str] = None) -> pd.DataFrame:
    """Read an xlsx into a DataFrame. Accepts a byte stream or raw bytes."""
    if isinstance(source, (bytes, bytearray)):
        import io

        source = io.BytesIO(source)
    return pd.read_excel(source, sheet_name=sheet_name or 0, engine="openpyxl")


def validate_dataframe(df: pd.DataFrame, contract: SchemaContract) -> ValidationResult:
    errors: list[ValidationError] = []

    for col in contract.required_columns:
        if col not in df.columns:
            errors.append(
                ValidationError(kind="missing_column", column=col, detail="column absent")
            )

    for col, expected_dtype in contract.column_types.items():
        if col not in df.columns:
            continue
        actual = str(df[col].dtype)
        if not _dtype_matches(actual, expected_dtype):
            errors.append(
                ValidationError(
                    kind="type_mismatch",
                    column=col,
                    detail=f"expected={expected_dtype} actual={actual}",
                )
            )

    for col in contract.disallow_null_columns:
        if col not in df.columns:
            continue
        null_count = int(df[col].isna().sum())
        if null_count > 0:
            errors.append(
                ValidationError(
                    kind="null_values",
                    column=col,
                    detail=f"{null_count} rows with null in required column",
                )
            )

    return ValidationResult(passed=not errors, row_count=int(len(df)), errors=tuple(errors))


_STRING_DTYPES = {"object", "str", "string", "string[python]", "string[pyarrow]"}
_INT_DTYPES = {"int8", "int16", "int32", "int64", "Int8", "Int16", "Int32", "Int64"}
_FLOAT_DTYPES = {"float16", "float32", "float64"}


def _dtype_matches(actual: str, expected: str) -> bool:
    """Dtype compare tuned for the round-trip through Excel.

    Excel has no distinction between int and float, so whole-number floats
    may read back as int; we accept either for numeric contracts. Pandas
    also reports object-string columns as `str` on newer versions. Datetime
    precision (`ns` vs `us`) varies with the backend and should not gate
    validation.
    """
    if expected == "string":
        return actual in _STRING_DTYPES
    if expected == "float64":
        return actual in _FLOAT_DTYPES or actual in _INT_DTYPES
    if expected.startswith("datetime64"):
        return actual.startswith("datetime64")
    return actual == expected


__all__ = [
    "SchemaContract",
    "ValidationError",
    "ValidationResult",
    "load_contract",
    "load_workbook",
    "validate_dataframe",
]
