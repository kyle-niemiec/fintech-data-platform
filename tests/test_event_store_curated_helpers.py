"""Unit tests for append_silver_checkpoint / append_gold_checkpoint.

The helpers are thin INSERT wrappers. We verify the SQL statement shape
and the positional parameter ordering using a stub connection, the same
style as other pure-SQL helper coverage in this repo.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from libs.platform_events.event_store import (
    append_gold_checkpoint,
    append_silver_checkpoint,
)


@dataclass
class _StubCursor:
    executed: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)

    def execute(self, sql: str, params: tuple[Any, ...]) -> None:
        self.executed.append((sql, params))


@dataclass
class _StubConn:
    cursor_obj: _StubCursor = field(default_factory=_StubCursor)

    @contextmanager
    def cursor(self):
        yield self.cursor_obj


def _jsonb_value(wrapped: Any) -> Any:
    assert isinstance(wrapped, Jsonb)
    return wrapped.obj


def test_append_silver_checkpoint_inserts_into_silver_checkpoint():
    conn = _StubConn()
    run_id = uuid4()
    parent_run_id = uuid4()

    append_silver_checkpoint(
        conn,
        run_id=run_id,
        parent_run_id=parent_run_id,
        silver_domain="salesforce_opportunity",
        input_uris=["s3://fintech-lakehouse/bronze/source=salesforce/object=Opportunity/part-0.parquet"],
        output_table="lakehouse.silver.dim_opportunity",
        output_uris=["s3://fintech-lakehouse/silver/domain=salesforce_opportunity/part-0.parquet"],
        record_count=42,
        merge_inserted=10,
        merge_updated=5,
        merge_closed=2,
    )

    assert len(conn.cursor_obj.executed) == 1
    sql, params = conn.cursor_obj.executed[0]
    assert "INSERT INTO event_store.silver_checkpoint" in sql
    assert params[0] == str(run_id)
    assert params[1] == str(parent_run_id)
    assert params[2] == "salesforce_opportunity"
    assert _jsonb_value(params[3]) == [
        "s3://fintech-lakehouse/bronze/source=salesforce/object=Opportunity/part-0.parquet"
    ]
    assert params[4] == "lakehouse.silver.dim_opportunity"
    assert _jsonb_value(params[5]) == [
        "s3://fintech-lakehouse/silver/domain=salesforce_opportunity/part-0.parquet"
    ]
    assert params[6] == 42
    assert params[7] == 10
    assert params[8] == 5
    assert params[9] == 2


def test_append_silver_checkpoint_defaults_merge_counters_to_zero():
    conn = _StubConn()

    append_silver_checkpoint(
        conn,
        run_id=uuid4(),
        parent_run_id=uuid4(),
        silver_domain="salesforce_opportunity",
        input_uris=[],
        output_table="lakehouse.silver.dim_opportunity",
        output_uris=[],
        record_count=0,
    )

    _, params = conn.cursor_obj.executed[0]
    assert params[7] == 0  # merge_inserted
    assert params[8] == 0  # merge_updated
    assert params[9] == 0  # merge_closed


def test_append_gold_checkpoint_inserts_into_gold_checkpoint():
    conn = _StubConn()
    run_id = uuid4()
    parent_run_id = uuid4()

    append_gold_checkpoint(
        conn,
        run_id=run_id,
        parent_run_id=parent_run_id,
        metric="pipeline_conversion",
        input_uris=["lakehouse.silver.dim_opportunity"],
        output_table="lakehouse.gold.kpi_pipeline_conversion",
        output_uris=["s3://fintech-lakehouse/gold/metric=pipeline_conversion/part-0.parquet"],
        record_count=7,
    )

    assert len(conn.cursor_obj.executed) == 1
    sql, params = conn.cursor_obj.executed[0]
    assert "INSERT INTO event_store.gold_checkpoint" in sql
    assert params[0] == str(run_id)
    assert params[1] == str(parent_run_id)
    assert params[2] == "pipeline_conversion"
    assert _jsonb_value(params[3]) == ["lakehouse.silver.dim_opportunity"]
    assert params[4] == "lakehouse.gold.kpi_pipeline_conversion"
    assert _jsonb_value(params[5]) == [
        "s3://fintech-lakehouse/gold/metric=pipeline_conversion/part-0.parquet"
    ]
    assert params[6] == 7
