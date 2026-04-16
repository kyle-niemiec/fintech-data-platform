-- Curated-layer checkpoints. One row per silver/gold DAG flush, recording
-- the upstream run it consumed, the output Iceberg table + URIs written,
-- and the record counts that went through. Enables replay/backfill by
-- letting curated workers resume from the last known-good parent_run_id.
CREATE TABLE IF NOT EXISTS event_store.silver_checkpoint (
    checkpoint_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES event_store.pipeline_run (run_id),
    parent_run_id   UUID NOT NULL REFERENCES event_store.pipeline_run (run_id),
    silver_domain   TEXT NOT NULL CHECK (length(trim(silver_domain)) > 0),
    input_uris      JSONB NOT NULL,
    output_table    TEXT NOT NULL CHECK (length(trim(output_table)) > 0),
    output_uris     JSONB NOT NULL DEFAULT '[]'::jsonb,
    record_count    INT NOT NULL CHECK (record_count >= 0),
    merge_inserted  INT NOT NULL DEFAULT 0 CHECK (merge_inserted >= 0),
    merge_updated   INT NOT NULL DEFAULT 0 CHECK (merge_updated >= 0),
    merge_closed    INT NOT NULL DEFAULT 0 CHECK (merge_closed >= 0),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT silver_checkpoint_parent_distinct_ck CHECK (parent_run_id <> run_id)
);

CREATE INDEX IF NOT EXISTS silver_checkpoint_domain_recorded_at_idx
    ON event_store.silver_checkpoint (silver_domain, recorded_at DESC);

CREATE INDEX IF NOT EXISTS silver_checkpoint_parent_run_id_idx
    ON event_store.silver_checkpoint (parent_run_id);

CREATE INDEX IF NOT EXISTS silver_checkpoint_run_id_idx
    ON event_store.silver_checkpoint (run_id);

GRANT SELECT, INSERT ON TABLE event_store.silver_checkpoint TO event_store_appender;
GRANT SELECT ON TABLE event_store.silver_checkpoint TO event_store_reader;


CREATE TABLE IF NOT EXISTS event_store.gold_checkpoint (
    checkpoint_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id          UUID NOT NULL REFERENCES event_store.pipeline_run (run_id),
    parent_run_id   UUID NOT NULL REFERENCES event_store.pipeline_run (run_id),
    metric          TEXT NOT NULL CHECK (length(trim(metric)) > 0),
    input_uris      JSONB NOT NULL,
    output_table    TEXT NOT NULL CHECK (length(trim(output_table)) > 0),
    output_uris     JSONB NOT NULL DEFAULT '[]'::jsonb,
    record_count    INT NOT NULL CHECK (record_count >= 0),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT gold_checkpoint_parent_distinct_ck CHECK (parent_run_id <> run_id)
);

CREATE INDEX IF NOT EXISTS gold_checkpoint_metric_recorded_at_idx
    ON event_store.gold_checkpoint (metric, recorded_at DESC);

CREATE INDEX IF NOT EXISTS gold_checkpoint_parent_run_id_idx
    ON event_store.gold_checkpoint (parent_run_id);

CREATE INDEX IF NOT EXISTS gold_checkpoint_run_id_idx
    ON event_store.gold_checkpoint (run_id);

GRANT SELECT, INSERT ON TABLE event_store.gold_checkpoint TO event_store_appender;
GRANT SELECT ON TABLE event_store.gold_checkpoint TO event_store_reader;
