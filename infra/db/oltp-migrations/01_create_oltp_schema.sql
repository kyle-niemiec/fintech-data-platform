CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS trading;

CREATE TABLE IF NOT EXISTS trading.transaction (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL,
    instrument TEXT NOT NULL,
    amount NUMERIC(18, 2) NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS transaction_executed_at_idx
    ON trading.transaction (executed_at DESC);

CREATE TABLE IF NOT EXISTS trading.risk_flag (
    risk_flag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES trading.transaction (transaction_id),
    event_id UUID NOT NULL,
    fraud_rule_version TEXT NOT NULL,
    risk_score NUMERIC(5, 4) NOT NULL,
    risk_flags JSONB NOT NULL,
    raw_topic TEXT NOT NULL,
    raw_partition INT NOT NULL,
    raw_offset BIGINT NOT NULL,
    flagged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT risk_flag_raw_coords_uq UNIQUE (raw_topic, raw_partition, raw_offset)
);

CREATE INDEX IF NOT EXISTS risk_flag_transaction_id_idx
    ON trading.risk_flag (transaction_id);

-- trading.transaction is REPLICA IDENTITY DEFAULT (primary key suffices for
-- Debezium's pgoutput. risk_flag is included in the publication for completeness
-- but fraud-worker updates use INSERT ... ON CONFLICT DO NOTHING for idempotency.
