-- Gold KPI aggregation: pipeline_conversion.
--
-- Parameters interpolated by the DAG before execution:
--   :curated_run_id   UUID of this curated_promotion run (gold)
--   :computed_at      Timestamp of aggregation (UTC)
--   :snapshot_date    Business date the snapshot represents (UTC date)
--
-- Semantics:
--   * Aggregate current silver.dim_opportunity rows (is_current = true) grouped
--     by stage_name.
--   * Compute counts (won/lost/open), $ totals, and closed-rate conversion.
--   * Append as a new snapshot_date slice; the gold table is partitioned by
--     year/month/day of snapshot_date so repeated runs within the same day
--     land in the same partition. Downstream consumers treat latest row per
--     (snapshot_date, stage_name) as authoritative.
INSERT INTO lakehouse.gold.kpi_pipeline_conversion
SELECT
    CAST(:snapshot_date AS DATE)                                       AS snapshot_date,
    stage_name,
    COUNT(*)                                                           AS opportunity_count,
    COUNT_IF(is_won)                                                   AS won_count,
    COUNT_IF(is_closed AND NOT is_won)                                 AS lost_count,
    COUNT_IF(NOT is_closed)                                            AS open_count,
    SUM(COALESCE(amount, CAST(0 AS DECIMAL(18, 2))))                   AS total_amount,
    SUM(IF(is_won, COALESCE(amount, CAST(0 AS DECIMAL(18, 2))),
                   CAST(0 AS DECIMAL(18, 2))))                         AS won_amount,
    CAST(COUNT_IF(is_won) AS DOUBLE) / NULLIF(COUNT_IF(is_closed), 0)  AS conversion_rate,
    CAST(:curated_run_id AS VARCHAR)                                   AS curated_run_id,
    CAST(:computed_at AS TIMESTAMP(6) WITH TIME ZONE)                  AS computed_at,
    year(CAST(:snapshot_date AS DATE))                                 AS year,
    month(CAST(:snapshot_date AS DATE))                                AS month,
    day(CAST(:snapshot_date AS DATE))                                  AS day
FROM lakehouse.silver.dim_opportunity
WHERE is_current = true
GROUP BY stage_name;
