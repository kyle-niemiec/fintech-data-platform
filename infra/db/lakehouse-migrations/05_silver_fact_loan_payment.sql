-- silver.fact_loan_payment — append-only loan payment facts.
CREATE SCHEMA IF NOT EXISTS lakehouse.silver;

CREATE TABLE IF NOT EXISTS lakehouse.silver.fact_loan_payment (
    loan_id               VARCHAR NOT NULL,
    payment_amount        DECIMAL(18, 2),
    payment_due_date      DATE,
    payment_posted_at     DATE,
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
    location = 's3://fintech-lakehouse/silver/domain=loan_payment/'
);
