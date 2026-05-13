from __future__ import annotations

from typing import Any

from curated_sql_helpers import sql_string_literal
from dag_runtime import now_utc
from gold_curated.common import _trino_cursor


def _build_sql(*, metric: str, curated_run_id: str, computed_at_iso: str, snapshot_date: str) -> str:
    """
    This function constructs the appropriate SQL query for the specified gold metric.
    Each supported metric has a corresponding SQL template that aggregates data
    from the relevant silver tables and inserts the results into the appropriate
    gold table. If an unsupported metric is specified, the function raises a
    ValueError to indicate the issue.
    """
    # Maybe return the "pipeline_conversion" SQL template
    if metric == "pipeline_conversion":
        return \
f"""
INSERT INTO lakehouse.gold.kpi_pipeline_conversion
SELECT
    CAST({sql_string_literal(snapshot_date)} AS DATE)                                       AS snapshot_date,
    stage_name,
    COUNT(*)                                                           AS opportunity_count,
    COUNT_IF(is_won)                                                   AS won_count,
    COUNT_IF(is_closed AND NOT is_won)                                 AS lost_count,
    COUNT_IF(NOT is_closed)                                            AS open_count,
    SUM(COALESCE(amount, CAST(0 AS DECIMAL(18, 2))))                   AS total_amount,
    SUM(IF(is_won, COALESCE(amount, CAST(0 AS DECIMAL(18, 2))),
                   CAST(0 AS DECIMAL(18, 2))))                         AS won_amount,
    CAST(COUNT_IF(is_won) AS DOUBLE) / NULLIF(COUNT_IF(is_closed), 0)  AS conversion_rate,
    CAST({sql_string_literal(curated_run_id)} AS VARCHAR)               AS curated_run_id,
    CAST(from_iso8601_timestamp({sql_string_literal(computed_at_iso)}) AS TIMESTAMP(6) WITH TIME ZONE) AS computed_at,
    year(CAST({sql_string_literal(snapshot_date)} AS DATE))             AS year,
    month(CAST({sql_string_literal(snapshot_date)} AS DATE))            AS month,
    day(CAST({sql_string_literal(snapshot_date)} AS DATE))              AS day
FROM lakehouse.silver.dim_opportunity
WHERE is_current = true
GROUP BY stage_name
"""

    # Maybe return the "portfolio_health" SQL template
    if metric == "portfolio_health":
        return \
f"""
INSERT INTO lakehouse.gold.kpi_portfolio_health
SELECT
    CAST({sql_string_literal(snapshot_date)} AS DATE)   AS snapshot_date,
    status_code,
    COUNT(*)                                            AS loan_count,
    SUM(COALESCE(
        principal_balance,
        CAST(0 AS DECIMAL(18, 2))
    ))                                                  AS total_principal_balance,
    COUNT_IF(COALESCE(days_past_due, 0) > 0)            AS delinquent_loan_count,
    AVG(COALESCE(CAST(days_past_due AS DOUBLE), 0))     AS avg_days_past_due,
    CAST(
        {sql_string_literal(curated_run_id)}
        AS VARCHAR
    )                                                   AS curated_run_id,
    CAST(
        from_iso8601_timestamp({sql_string_literal(computed_at_iso)})
        AS TIMESTAMP(6) WITH TIME ZONE
    )                                                   AS computed_at,
    year(CAST(
        {sql_string_literal(snapshot_date)}
        AS DATE
    ))                                                  AS year,
    month(CAST(
        {sql_string_literal(snapshot_date)}
        AS DATE
    ))                                                  AS month,
    day(CAST(
        {sql_string_literal(snapshot_date)}
        AS DATE
    ))                                                  AS day
FROM lakehouse.silver.dim_loan
WHERE is_current = true
GROUP BY status_code
"""

    # Maybe return the "payment_performance" SQL template
    if metric == "payment_performance":
        return \
f"""
INSERT INTO lakehouse.gold.kpi_payment_performance
SELECT
    CAST({sql_string_literal(snapshot_date)} AS DATE) AS snapshot_date,
    COUNT(*) AS payment_count,
    SUM(COALESCE(payment_amount, CAST(0 AS DECIMAL(18, 2)))) AS total_payment_amount,
    COUNT_IF(payment_posted_at IS NOT NULL AND payment_posted_at <= payment_due_date) AS on_time_payment_count,
    COUNT_IF(payment_posted_at IS NOT NULL AND payment_posted_at > payment_due_date) AS late_payment_count,
    CAST({sql_string_literal(curated_run_id)} AS VARCHAR) AS curated_run_id,
    CAST(from_iso8601_timestamp({sql_string_literal(computed_at_iso)}) AS TIMESTAMP(6) WITH TIME ZONE) AS computed_at,
    year(CAST({sql_string_literal(snapshot_date)} AS DATE)) AS year,
    month(CAST({sql_string_literal(snapshot_date)} AS DATE)) AS month,
    day(CAST({sql_string_literal(snapshot_date)} AS DATE)) AS day
FROM lakehouse.silver.fact_loan_payment
WHERE payment_due_date IS NOT NULL
"""

    # Maybe return the "commission_economics" SQL template
    if metric == "commission_economics":
        return f"""
INSERT INTO lakehouse.gold.kpi_commission_economics
SELECT
    CAST({sql_string_literal(snapshot_date)} AS DATE) AS snapshot_date,
    adjustment_reason,
    COUNT(*) AS adjustment_count,
    SUM(COALESCE(adjustment_amount, CAST(0 AS DECIMAL(18, 2)))) AS total_adjustment_amount,
    CAST({sql_string_literal(curated_run_id)} AS VARCHAR) AS curated_run_id,
    CAST(from_iso8601_timestamp({sql_string_literal(computed_at_iso)}) AS TIMESTAMP(6) WITH TIME ZONE) AS computed_at,
    year(CAST({sql_string_literal(snapshot_date)} AS DATE)) AS year,
    month(CAST({sql_string_literal(snapshot_date)} AS DATE)) AS month,
    day(CAST({sql_string_literal(snapshot_date)} AS DATE)) AS day
FROM lakehouse.silver.fact_commission_adjustment
GROUP BY adjustment_reason
"""

    # If no supported metric is matched, raise an error to indicate the issue.
    raise ValueError(f"unsupported gold metric {metric!r}")


def run_aggregation_sql(state: dict[str, Any]) -> dict[str, Any]:
    """
    This task executes the aggregation SQL for the specified gold metric and records metadata about the run.
    """
    computed_at = now_utc()
    snapshot_date = computed_at.date().isoformat()
    computed_at_iso = computed_at.isoformat()
    metric = state["gold_metric"]
    output_table = state["gold_table"]

    aggregation_sql = _build_sql(
        metric=metric,
        curated_run_id=state["curated_run_id"],
        computed_at_iso=computed_at_iso,
        snapshot_date=snapshot_date,
    )

    record_count = 0
    conn, cur = _trino_cursor()

    # Execute the aggregation SQL to populate the gold table with the aggregated results for the specified metric.
    try:
        cur.execute(aggregation_sql.strip().rstrip(";"))
        cur.fetchall()
        count_cur = conn.cursor()

        try:
            count_cur.execute(
                f"SELECT COUNT(*) FROM {output_table} "
                f"WHERE curated_run_id = '{state['curated_run_id']}'"
            )
            row = count_cur.fetchone()
            record_count = int(row[0]) if row else 0
        finally:
            count_cur.close()
    finally:
        cur.close()
        conn.close()

    # Return metadata about the aggregation run for use in downstream tasks.
    return {
        **state,
        "snapshot_date": snapshot_date,
        "computed_at": computed_at_iso,
        "record_count": record_count,
    }
