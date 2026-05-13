-- gold.kpi_portfolio_health — daily loan-health KPI by status.
CREATE SCHEMA IF NOT EXISTS lakehouse.gold;

CREATE TABLE IF NOT EXISTS lakehouse.gold.kpi_portfolio_health (
    snapshot_date            DATE NOT NULL,
    status_code              VARCHAR NOT NULL,
    loan_count               BIGINT NOT NULL,
    total_principal_balance  DECIMAL(18, 2) NOT NULL,
    delinquent_loan_count    BIGINT NOT NULL,
    avg_days_past_due        DOUBLE,
    curated_run_id           VARCHAR NOT NULL,
    computed_at              TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    year                     INTEGER NOT NULL,
    month                    INTEGER NOT NULL,
    day                      INTEGER NOT NULL
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['year', 'month', 'day'],
    location = 's3://fintech-lakehouse/gold/metric=portfolio_health/'
);
