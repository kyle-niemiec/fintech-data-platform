-- silver.dim_loan — SCD2 loan dimension from CDC loan table.
CREATE SCHEMA IF NOT EXISTS lakehouse.silver;

CREATE TABLE IF NOT EXISTS lakehouse.silver.dim_loan (
    loan_id               VARCHAR NOT NULL,
    account_id            VARCHAR,
    status_code           VARCHAR,
    principal_balance     DECIMAL(18, 2),
    days_past_due         INTEGER,
    valid_from            TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    valid_to              TIMESTAMP(6) WITH TIME ZONE,
    is_current            BOOLEAN NOT NULL,
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
    location = 's3://fintech-lakehouse/silver/domain=loan/'
);
