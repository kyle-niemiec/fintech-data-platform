-- silver.fact_commission_adjustment — append-only commission adjustments.
CREATE SCHEMA IF NOT EXISTS lakehouse.silver;

CREATE TABLE IF NOT EXISTS lakehouse.silver.fact_commission_adjustment (
    advisor_id            VARCHAR NOT NULL,
    adjustment_amount     DECIMAL(18, 2),
    adjustment_reason     VARCHAR,
    adjustment_date       DATE,
    currency              VARCHAR,
    source_run_id         VARCHAR NOT NULL,
    curated_run_id        VARCHAR NOT NULL,
    source_system_mod     TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    year                  INTEGER NOT NULL,
    month                 INTEGER NOT NULL,
    day                   INTEGER NOT NULL
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['year', 'month', 'day'],
    location = 's3://fintech-lakehouse/silver/domain=commission_adjustment/'
);
