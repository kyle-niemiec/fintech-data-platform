-- silver.dim_opportunity — SCD2 Salesforce Opportunity dimension.
-- One row per (opportunity_id, valid_from) version. is_current=true marks the
-- live version; updates close the previous current row (valid_to set) and
-- insert a new current version. Partitioning follows the lakehouse partition
-- contract: year/month/day derived from the source SystemModstamp.
CREATE SCHEMA IF NOT EXISTS lakehouse.silver;

CREATE TABLE IF NOT EXISTS lakehouse.silver.dim_opportunity (
    opportunity_id       VARCHAR NOT NULL,
    account_id_token     VARCHAR,
    name                 VARCHAR,
    stage_name           VARCHAR,
    amount               DECIMAL(18, 2),
    close_date           DATE,
    is_won               BOOLEAN,
    is_closed            BOOLEAN,
    valid_from           TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    valid_to             TIMESTAMP(6) WITH TIME ZONE,
    is_current           BOOLEAN NOT NULL,
    source_run_id        VARCHAR NOT NULL,
    curated_run_id       VARCHAR NOT NULL,
    source_system_mod    TIMESTAMP(6) WITH TIME ZONE NOT NULL,
    year                 INTEGER NOT NULL,
    month                INTEGER NOT NULL,
    day                  INTEGER NOT NULL
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['year', 'month', 'day'],
    location = 's3://fintech-lakehouse/silver/domain=salesforce_opportunity/'
);
