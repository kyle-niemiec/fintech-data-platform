"""
Load and validate SQL resources for the event-store runtime API.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
import re
from typing import Mapping

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

SQL_PACKAGE = "libs.platform_events.sql.event_store"
BIND_PARAM_PATTERN = re.compile(r"(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)")

# Mapping of statement names to their corresponding SQL file names within the package.
#
# Declare new SQL statements here and ensure that the corresponding SQL files are
# present in the package directory.
EVENT_STORE_SQL_FILES: dict[str, str] = {
    "open_run_insert": "open_run_insert.sql",
    "open_run_select_existing": "open_run_select_existing.sql",
    "append_event": "append_event.sql",
    "close_run": "close_run.sql",
    "raise_alert": "raise_alert.sql",
    "append_cdc_checkpoint": "append_cdc_checkpoint.sql",
    "append_sf_cursor_checkpoint": "append_sf_cursor_checkpoint.sql",
    "latest_sf_cursor": "latest_sf_cursor.sql",
    "append_silver_checkpoint": "append_silver_checkpoint.sql",
    "append_gold_checkpoint": "append_gold_checkpoint.sql",
}


@dataclass(frozen=True)
class SqlStatement:
    raw_sql: str
    text_clause: TextClause
    bind_names: frozenset[str]


def _extract_bind_names(sql_text: str) -> frozenset[str]:
    """
    Extract bind parameter names from the given SQL text using a regular expression.
    """
    return frozenset(BIND_PARAM_PATTERN.findall(sql_text))


def _load_statement(*, package: str, file_name: str) -> SqlStatement:
    """
    Load a SQL statement from the specified package and file name, validating that
    the file exists and is not empty. Extract bind parameter names and return a
    SqlStatement object containing the raw SQL, a SQLAlchemy TextClause, and the set
    of bind parameter names.
    """
    path = resources.files(package).joinpath(file_name)

    try:
        raw_sql = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(f"event-store SQL file not found: {package}/{file_name}") from exc

    normalized_sql = raw_sql.strip()

    if not normalized_sql:
        raise RuntimeError(f"event-store SQL file is empty: {package}/{file_name}")

    return SqlStatement(
        raw_sql=normalized_sql,
        text_clause=text(normalized_sql),
        bind_names=_extract_bind_names(normalized_sql),
    )


def load_event_store_statements(
    *,
    package: str = SQL_PACKAGE,
    sql_files: Mapping[str, str] = EVENT_STORE_SQL_FILES,
) -> dict[str, SqlStatement]:
    """
    Load all SQL statements defined in the `sql_files` mapping from the specified
    package, returning a dictionary mapping statement names to their corresponding
    SqlStatement objects.
    """
    statements: dict[str, SqlStatement] = {}

    for name, file_name in sql_files.items():
        statements[name] = _load_statement(package=package, file_name=file_name)

    return statements
