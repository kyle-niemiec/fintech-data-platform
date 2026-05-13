-- gold.kpi_commission_economics — daily commission adjustment KPI.
CREATE SCHEMA IF NOT EXISTS lakehouse.gold;

CREATE TABLE IF NOT EXISTS lakehouse.gold.kpi_commission_economics (
    snapshot_date            DATE NOT NULL,
    adjustment_reason        VARCHAR NOT NULL,
    adjustment_count         BIGINT NOT NULL,
    total_adjustment_amount  DECIMAL(18, 2) NOT NULL,
    curated_run_id           VARCHAR NOT NULL,
    computed_at              TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    year                     INTEGER NOT NULL,
    month                    INTEGER NOT NULL,
    day                      INTEGER NOT NULL
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['year', 'month', 'day'],
    location = 's3://fintech-lakehouse/gold/metric=commission_economics/'
);
