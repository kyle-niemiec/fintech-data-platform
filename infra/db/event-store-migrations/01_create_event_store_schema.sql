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
    kafka_offset BIGINT NOT NULL,
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

CREATE SCHEMA IF NOT EXISTS partman;

DO
$$
DECLARE
    partman_schema TEXT;
BEGIN
    SELECT n.nspname
    INTO partman_schema
    FROM pg_extension e
    JOIN pg_namespace n ON n.oid = e.extnamespace
    WHERE e.extname = 'pg_partman';

    IF partman_schema IS NULL THEN
        EXECUTE 'CREATE EXTENSION pg_partman SCHEMA partman';
    ELSIF partman_schema <> 'partman' THEN
        EXECUTE 'ALTER EXTENSION pg_partman SET SCHEMA partman';
    END IF;
END;
$$;

CREATE EXTENSION IF NOT EXISTS pg_cron;

CREATE TABLE IF NOT EXISTS event_store.event_log_template (
    LIKE event_store.event_log INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);

CREATE TABLE IF NOT EXISTS event_store.alert_event_template (
    LIKE event_store.alert_event INCLUDING DEFAULTS INCLUDING CONSTRAINTS
);

CREATE UNIQUE INDEX IF NOT EXISTS event_log_template_topic_partition_kafka_offset_uq
    ON event_store.event_log_template (topic, partition, kafka_offset);

CREATE INDEX IF NOT EXISTS event_log_template_run_id_occurred_at_idx
    ON event_store.event_log_template (run_id, occurred_at);

CREATE INDEX IF NOT EXISTS event_log_template_trace_id_occurred_at_idx
    ON event_store.event_log_template (trace_id, occurred_at);

CREATE INDEX IF NOT EXISTS event_log_template_event_type_occurred_at_idx
    ON event_store.event_log_template (event_type, occurred_at);

CREATE INDEX IF NOT EXISTS alert_event_template_run_id_occurred_at_idx
    ON event_store.alert_event_template (run_id, occurred_at);

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM partman.part_config
        WHERE parent_table = 'event_store.event_log'
    ) THEN
        PERFORM partman.create_parent(
            p_parent_table := 'event_store.event_log',
            p_control := 'occurred_at',
            p_interval := '1 month',
            p_premake := 2,
            p_template_table := 'event_store.event_log_template'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM partman.part_config
        WHERE parent_table = 'event_store.alert_event'
    ) THEN
        PERFORM partman.create_parent(
            p_parent_table := 'event_store.alert_event',
            p_control := 'occurred_at',
            p_interval := '1 month',
            p_premake := 2,
            p_template_table := 'event_store.alert_event_template'
        );
    END IF;
END;
$$;

UPDATE partman.part_config
SET premake = 2,
    infinite_time_partitions = TRUE,
    automatic_maintenance = 'on'
WHERE parent_table IN ('event_store.event_log', 'event_store.alert_event');

CREATE OR REPLACE FUNCTION event_store.run_partman_maintenance()
RETURNS VOID
LANGUAGE plpgsql
AS
$$
BEGIN
    PERFORM partman.run_maintenance(
        p_parent_table := 'event_store.event_log',
        p_analyze := FALSE,
        p_jobmon := FALSE
    );
    PERFORM partman.run_maintenance(
        p_parent_table := 'event_store.alert_event',
        p_analyze := FALSE,
        p_jobmon := FALSE
    );
END;
$$;

SELECT event_store.run_partman_maintenance();

DO
$$
DECLARE
    existing_job_id BIGINT;
BEGIN
    FOR existing_job_id IN
        SELECT jobid
        FROM cron.job
        WHERE database = current_database()
          AND command = 'SELECT event_store.run_partman_maintenance();'
    LOOP
        PERFORM cron.unschedule(existing_job_id);
    END LOOP;

    PERFORM cron.schedule('5 * * * *', 'SELECT event_store.run_partman_maintenance();');
END;
$$;

GRANT USAGE ON SCHEMA event_store TO event_store_appender, event_store_reader;

GRANT SELECT, INSERT ON TABLE event_store.pipeline_run TO event_store_appender;
GRANT SELECT, INSERT ON TABLE event_store.event_log TO event_store_appender;
GRANT SELECT, INSERT ON TABLE event_store.alert_event TO event_store_appender;
GRANT SELECT ON ALL TABLES IN SCHEMA event_store TO event_store_reader;
