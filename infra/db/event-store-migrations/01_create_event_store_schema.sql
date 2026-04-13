CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'event_store_appender') THEN
        CREATE ROLE event_store_appender NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'event_store_reader') THEN
        CREATE ROLE event_store_reader NOLOGIN;
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS event_store;

CREATE TABLE IF NOT EXISTS event_store.pipeline_run (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_class TEXT NOT NULL CHECK (pipeline_class IN ('ingestion', 'curated')),
    pipeline_name TEXT NOT NULL CHECK (
        pipeline_name IN (
            'excel_ingestion',
            'cdc_ingestion',
            'salesforce_ingestion',
            'curated_promotion'
        )
    ),
    source_system TEXT NOT NULL CHECK (source_system IN ('excel', 'cdc', 'salesforce', 'curated')),
    trigger_type TEXT NOT NULL,
    trigger_event_ref TEXT NOT NULL CHECK (length(trim(trigger_event_ref)) > 0),
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    initiator TEXT NOT NULL,
    parent_run_id UUID REFERENCES event_store.pipeline_run (run_id),
    CONSTRAINT pipeline_run_parent_not_self_ck CHECK (parent_run_id IS NULL OR parent_run_id <> run_id),
    CONSTRAINT pipeline_run_domain_ck CHECK (
        (pipeline_class = 'ingestion' AND pipeline_name = 'excel_ingestion' AND source_system = 'excel' AND parent_run_id IS NULL)
        OR
        (pipeline_class = 'ingestion' AND pipeline_name = 'cdc_ingestion' AND source_system = 'cdc' AND parent_run_id IS NULL)
        OR
        (pipeline_class = 'ingestion' AND pipeline_name = 'salesforce_ingestion' AND source_system = 'salesforce' AND parent_run_id IS NULL)
        OR
        (pipeline_class = 'curated' AND pipeline_name = 'curated_promotion' AND source_system = 'curated' AND parent_run_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS pipeline_run_pipeline_name_trigger_event_ref_uq
    ON event_store.pipeline_run (pipeline_name, trigger_event_ref);

CREATE TABLE IF NOT EXISTS event_store.event_log (
    event_id UUID NOT NULL DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES event_store.pipeline_run (run_id),
    event_type TEXT NOT NULL,
    topic TEXT NOT NULL,
    partition INT NOT NULL,
    offset BIGINT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    trace_id UUID,
    payload JSONB NOT NULL,
    payload_hash TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    PRIMARY KEY (event_id, occurred_at)
) PARTITION BY RANGE (occurred_at);

CREATE TABLE IF NOT EXISTS event_store.alert_event (
    alert_id UUID NOT NULL DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES event_store.pipeline_run (run_id),
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    details JSONB NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (alert_id, occurred_at)
) PARTITION BY RANGE (occurred_at);

CREATE OR REPLACE FUNCTION event_store.assert_run_has_event()
RETURNS trigger
LANGUAGE plpgsql
AS
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM event_store.event_log el
        WHERE el.run_id = NEW.run_id
    ) THEN
        RAISE EXCEPTION 'pipeline_run % must include at least one event_log row before commit', NEW.run_id;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS pipeline_run_requires_event ON event_store.pipeline_run;

CREATE CONSTRAINT TRIGGER pipeline_run_requires_event
AFTER INSERT ON event_store.pipeline_run
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION event_store.assert_run_has_event();

CREATE TABLE IF NOT EXISTS event_store.event_log_2026_04
    PARTITION OF event_store.event_log
    FOR VALUES FROM ('2026-04-01 00:00:00+00') TO ('2026-05-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS event_store.alert_event_2026_04
    PARTITION OF event_store.alert_event
    FOR VALUES FROM ('2026-04-01 00:00:00+00') TO ('2026-05-01 00:00:00+00');

CREATE UNIQUE INDEX IF NOT EXISTS event_log_2026_04_topic_partition_offset_uq
    ON event_store.event_log_2026_04 (topic, partition, offset);

CREATE INDEX IF NOT EXISTS event_log_2026_04_run_id_occurred_at_idx
    ON event_store.event_log_2026_04 (run_id, occurred_at);

CREATE INDEX IF NOT EXISTS event_log_2026_04_trace_id_occurred_at_idx
    ON event_store.event_log_2026_04 (trace_id, occurred_at);

CREATE INDEX IF NOT EXISTS event_log_2026_04_event_type_occurred_at_idx
    ON event_store.event_log_2026_04 (event_type, occurred_at);

CREATE INDEX IF NOT EXISTS alert_event_2026_04_run_id_occurred_at_idx
    ON event_store.alert_event_2026_04 (run_id, occurred_at);

GRANT USAGE ON SCHEMA event_store TO event_store_appender, event_store_reader;

GRANT SELECT, INSERT ON TABLE event_store.pipeline_run TO event_store_appender;
GRANT SELECT, INSERT ON TABLE event_store.event_log TO event_store_appender;
GRANT SELECT, INSERT ON TABLE event_store.alert_event TO event_store_appender;
GRANT SELECT ON ALL TABLES IN SCHEMA event_store TO event_store_reader;
