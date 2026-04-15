-- CDC bronze checkpoint: one row per bronze flush, recording the LSN and
-- Kafka offset range covered by the Parquet object(s) produced.
CREATE TABLE IF NOT EXISTS event_store.cdc_checkpoint (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES event_store.pipeline_run (run_id),
    source_table TEXT NOT NULL,
    lsn_start TEXT,
    lsn_end TEXT,
    kafka_partition INT NOT NULL,
    offset_start BIGINT NOT NULL,
    offset_end BIGINT NOT NULL,
    record_count INT NOT NULL CHECK (record_count >= 0),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT cdc_checkpoint_offsets_ck CHECK (offset_end >= offset_start)
);

CREATE INDEX IF NOT EXISTS cdc_checkpoint_source_table_recorded_at_idx
    ON event_store.cdc_checkpoint (source_table, recorded_at DESC);

CREATE INDEX IF NOT EXISTS cdc_checkpoint_run_id_idx
    ON event_store.cdc_checkpoint (run_id);

GRANT SELECT, INSERT ON TABLE event_store.cdc_checkpoint TO event_store_appender;
GRANT SELECT ON TABLE event_store.cdc_checkpoint TO event_store_reader;
