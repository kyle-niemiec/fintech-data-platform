from __future__ import annotations

from typing import Any

from curated_sql_helpers import sql_string_literal
from dag_runtime import now_utc
from gold_curated.common import GOLD_TABLE, _trino_cursor

AGGREGATION_SQL = """
INSERT INTO lakehouse.gold.kpi_pipeline_conversion
SELECT
    CAST({snapshot_date} AS DATE)                                       AS snapshot_date,
    stage_name,
    COUNT(*)                                                           AS opportunity_count,
    COUNT_IF(is_won)                                                   AS won_count,
    COUNT_IF(is_closed AND NOT is_won)                                 AS lost_count,
    COUNT_IF(NOT is_closed)                                            AS open_count,
    SUM(COALESCE(amount, CAST(0 AS DECIMAL(18, 2))))                   AS total_amount,
    SUM(IF(is_won, COALESCE(amount, CAST(0 AS DECIMAL(18, 2))),
                   CAST(0 AS DECIMAL(18, 2))))                         AS won_amount,
    CAST(COUNT_IF(is_won) AS DOUBLE) / NULLIF(COUNT_IF(is_closed), 0)  AS conversion_rate,
    CAST({curated_run_id} AS VARCHAR)                                   AS curated_run_id,
    CAST(from_iso8601_timestamp({computed_at}) AS TIMESTAMP(6) WITH TIME ZONE) AS computed_at,
    year(CAST({snapshot_date} AS DATE))                                 AS year,
    month(CAST({snapshot_date} AS DATE))                                AS month,
    day(CAST({snapshot_date} AS DATE))                                  AS day
FROM lakehouse.silver.dim_opportunity
WHERE is_current = true
GROUP BY stage_name
"""


def _build_aggregation_sql(*, curated_run_id: str, computed_at_iso: str, snapshot_date: str) -> str:
    return AGGREGATION_SQL.format(
        curated_run_id=sql_string_literal(curated_run_id),
        computed_at=sql_string_literal(computed_at_iso),
        snapshot_date=sql_string_literal(snapshot_date),
    ).strip()


def run_aggregation_sql(state: dict[str, Any]) -> dict[str, Any]:
    computed_at = now_utc()
    snapshot_date = computed_at.date().isoformat()
    computed_at_iso = computed_at.isoformat()

    aggregation_sql = _build_aggregation_sql(
        curated_run_id=state["curated_run_id"],
        computed_at_iso=computed_at_iso,
        snapshot_date=snapshot_date,
    )

    record_count = 0
    conn, cur = _trino_cursor()

    try:
        cur.execute(aggregation_sql)
        cur.fetchall()
        count_cur = conn.cursor()

        try:
            count_cur.execute(
                f"SELECT COUNT(*) FROM {GOLD_TABLE} "
                f"WHERE curated_run_id = '{state['curated_run_id']}'"
            )
            row = count_cur.fetchone()
            record_count = int(row[0]) if row else 0
        finally:
            count_cur.close()
    finally:
        cur.close()
        conn.close()

    return {
        **state,
        "snapshot_date": snapshot_date,
        "computed_at": computed_at_iso,
        "record_count": record_count,
    }
