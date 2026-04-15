-- Salesforce incremental-pull cursor checkpoint. One row per bronze flush,
-- recording the (SystemModstamp, Id) watermark advanced-to for that SObject
-- and the Kafka offset range of the raw.ready.v1 message(s) that produced it.
CREATE TABLE IF NOT EXISTS event_store.sf_cursor_checkpoint (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES event_store.pipeline_run (run_id),
    sobject TEXT NOT NULL CHECK (length(trim(sobject)) > 0),
    cursor_ts TIMESTAMPTZ NOT NULL,
    cursor_id TEXT NOT NULL,
    kafka_partition INT NOT NULL,
    offset_start BIGINT NOT NULL,
    offset_end BIGINT NOT NULL,
    record_count INT NOT NULL CHECK (record_count >= 0),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT sf_cursor_checkpoint_offsets_ck CHECK (offset_end >= offset_start)
);

CREATE INDEX IF NOT EXISTS sf_cursor_checkpoint_sobject_recorded_at_idx
    ON event_store.sf_cursor_checkpoint (sobject, recorded_at DESC);

CREATE INDEX IF NOT EXISTS sf_cursor_checkpoint_run_id_idx
    ON event_store.sf_cursor_checkpoint (run_id);

GRANT SELECT, INSERT ON TABLE event_store.sf_cursor_checkpoint TO event_store_appender;
GRANT SELECT ON TABLE event_store.sf_cursor_checkpoint TO event_store_reader;
