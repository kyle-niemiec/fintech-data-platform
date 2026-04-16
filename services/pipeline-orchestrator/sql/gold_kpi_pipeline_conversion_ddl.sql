-- gold.kpi_pipeline_conversion — pipeline-health KPI keyed by snapshot_date
-- and stage_name. Aggregation is re-computed per gold run from the current
-- slice of silver.dim_opportunity; partitioning matches the lakehouse
-- contract (year/month/day from snapshot_date).
CREATE SCHEMA IF NOT EXISTS lakehouse.gold;

CREATE TABLE IF NOT EXISTS lakehouse.gold.kpi_pipeline_conversion (
    snapshot_date        DATE NOT NULL,
    stage_name           VARCHAR NOT NULL,
    opportunity_count    BIGINT NOT NULL,
    won_count            BIGINT NOT NULL,
    lost_count           BIGINT NOT NULL,
    open_count           BIGINT NOT NULL,
    total_amount         DECIMAL(18, 2) NOT NULL,
    won_amount           DECIMAL(18, 2) NOT NULL,
    conversion_rate      DOUBLE,
    curated_run_id       VARCHAR NOT NULL,
    computed_at          TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    year                 INTEGER NOT NULL,
    month                INTEGER NOT NULL,
    day                  INTEGER NOT NULL
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['year', 'month', 'day'],
    location = 's3://fintech-lakehouse/gold/metric=pipeline_conversion/'
);
