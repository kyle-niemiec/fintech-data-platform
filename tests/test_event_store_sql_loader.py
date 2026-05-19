"""Unit tests for event-store SQL resource loading."""

from __future__ import annotations

import pytest

from libs.platform_events.event_store_sql import load_event_store_statements


def test_load_event_store_statements_returns_non_empty_queries() -> None:
    statements = load_event_store_statements()

    assert statements
    for statement in statements.values():
        assert statement.raw_sql
        assert statement.bind_names == frozenset(statement.text_clause._bindparams.keys())


def test_load_event_store_statements_raises_clear_error_for_missing_file() -> None:
    with pytest.raises(RuntimeError, match="event-store SQL file not found"):
        load_event_store_statements(sql_files={"missing": "does_not_exist.sql"})
