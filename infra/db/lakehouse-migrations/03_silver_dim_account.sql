-- silver.dim_account — SCD2 Salesforce Account dimension keyed by account_id_token.
CREATE SCHEMA IF NOT EXISTS lakehouse.silver;

CREATE TABLE IF NOT EXISTS lakehouse.silver.dim_account (
    account_id_token      VARCHAR NOT NULL,
    name                  VARCHAR,
    industry              VARCHAR,
    annual_revenue        DECIMAL(18, 2),
    number_of_employees   INTEGER,
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
    location = 's3://fintech-lakehouse/silver/domain=salesforce_account/'
);
