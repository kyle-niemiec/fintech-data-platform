"""Unit tests for PgEventStore checkpoint helpers.

The helpers are thin INSERT wrappers. We verify the SQL statement shape
and the named parameter mapping using a stub connection, the same
style as other pure-SQL helper coverage in this repo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from libs.platform_events.event_store import PgEventStore


@dataclass
class _StubResult:
    def fetchone(self):
        return None


@dataclass
class _StubConn:
    executed: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def execute(self, statement: Any, params: dict[str, Any]) -> _StubResult:
        self.executed.append((str(statement), dict(params)))
        return _StubResult()


def _jsonb_value(wrapped: Any) -> Any:
    assert isinstance(wrapped, Jsonb)
    return wrapped.obj


def test_append_silver_checkpoint_inserts_into_silver_checkpoint():
    conn = _StubConn()
    run_id = uuid4()
    parent_run_id = uuid4()

    PgEventStore.append_silver_checkpoint(
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

    assert len(conn.executed) == 1
    sql, params = conn.executed[0]
    assert "INSERT INTO event_store.silver_checkpoint" in sql
    assert params["run_id"] == str(run_id)
    assert params["parent_run_id"] == str(parent_run_id)
    assert params["silver_domain"] == "salesforce_opportunity"
    assert _jsonb_value(params["input_uris"]) == [
        "s3://fintech-lakehouse/bronze/source=salesforce/object=Opportunity/part-0.parquet"
    ]
    assert params["output_table"] == "lakehouse.silver.dim_opportunity"
    assert _jsonb_value(params["output_uris"]) == [
        "s3://fintech-lakehouse/silver/domain=salesforce_opportunity/part-0.parquet"
    ]
    assert params["record_count"] == 42
    assert params["merge_inserted"] == 10
    assert params["merge_updated"] == 5
    assert params["merge_closed"] == 2


def test_append_silver_checkpoint_defaults_merge_counters_to_zero():
    conn = _StubConn()

    PgEventStore.append_silver_checkpoint(
        conn,
        run_id=uuid4(),
        parent_run_id=uuid4(),
        silver_domain="salesforce_opportunity",
        input_uris=[],
        output_table="lakehouse.silver.dim_opportunity",
        output_uris=[],
        record_count=0,
    )

    _, params = conn.executed[0]
    assert params["merge_inserted"] == 0
    assert params["merge_updated"] == 0
    assert params["merge_closed"] == 0


def test_append_gold_checkpoint_inserts_into_gold_checkpoint():
    conn = _StubConn()
    run_id = uuid4()
    parent_run_id = uuid4()

    PgEventStore.append_gold_checkpoint(
        conn,
        run_id=run_id,
        parent_run_id=parent_run_id,
        metric="pipeline_conversion",
        input_uris=["lakehouse.silver.dim_opportunity"],
        output_table="lakehouse.gold.kpi_pipeline_conversion",
        output_uris=["s3://fintech-lakehouse/gold/metric=pipeline_conversion/part-0.parquet"],
        record_count=7,
    )

    assert len(conn.executed) == 1
    sql, params = conn.executed[0]
    assert "INSERT INTO event_store.gold_checkpoint" in sql
    assert params["run_id"] == str(run_id)
    assert params["parent_run_id"] == str(parent_run_id)
    assert params["metric"] == "pipeline_conversion"
    assert _jsonb_value(params["input_uris"]) == ["lakehouse.silver.dim_opportunity"]
    assert params["output_table"] == "lakehouse.gold.kpi_pipeline_conversion"
    assert _jsonb_value(params["output_uris"]) == [
        "s3://fintech-lakehouse/gold/metric=pipeline_conversion/part-0.parquet"
    ]
    assert params["record_count"] == 7
