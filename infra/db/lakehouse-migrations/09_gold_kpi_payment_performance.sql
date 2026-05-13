-- gold.kpi_payment_performance — daily payment timeliness KPI.
CREATE SCHEMA IF NOT EXISTS lakehouse.gold;

CREATE TABLE IF NOT EXISTS lakehouse.gold.kpi_payment_performance (
    snapshot_date           DATE NOT NULL,
    payment_count           BIGINT NOT NULL,
    total_payment_amount    DECIMAL(18, 2) NOT NULL,
    on_time_payment_count   BIGINT NOT NULL,
    late_payment_count      BIGINT NOT NULL,
    curated_run_id          VARCHAR NOT NULL,
    computed_at             TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    year                    INTEGER NOT NULL,
    month                   INTEGER NOT NULL,
    day                     INTEGER NOT NULL
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['year', 'month', 'day'],
    location = 's3://fintech-lakehouse/gold/metric=payment_performance/'
);
