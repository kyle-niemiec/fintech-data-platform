"""Shared SQL literal helpers for curated DAG tasks."""

from __future__ import annotations

from typing import Any

from airflow.exceptions import AirflowException


def sql_string_literal(value: Any) -> str:
    """Return a SQL string literal with single-quote escaping."""
    if value is None:
        return "NULL"

    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def sql_bool_literal(value: Any) -> str:
    """Return a SQL boolean literal (or NULL) from bool/string inputs."""
    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "t", "1", "yes", "y"}:
            return "TRUE"
        if normalized in {"false", "f", "0", "no", "n"}:
            return "FALSE"

    raise AirflowException(f"unsupported boolean value in masked row: {value!r}")
