-- silver.loan_status_history — append-only loan status timeline.
CREATE SCHEMA IF NOT EXISTS lakehouse.silver;

CREATE TABLE IF NOT EXISTS lakehouse.silver.loan_status_history (
    loan_id               VARCHAR NOT NULL,
    status_code           VARCHAR NOT NULL,
    status_at             TIMESTAMP(6) WITH TIME ZONE NOT NULL,
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
    location = 's3://fintech-lakehouse/silver/domain=loan_status_history/'
);
