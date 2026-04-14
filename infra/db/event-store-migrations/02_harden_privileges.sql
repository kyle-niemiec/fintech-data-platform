REVOKE ALL ON SCHEMA event_store FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA event_store FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA event_store FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA event_store FROM PUBLIC;

GRANT USAGE ON SCHEMA event_store TO event_store_appender, event_store_reader;

REVOKE ALL ON ALL TABLES IN SCHEMA event_store FROM event_store_appender;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA event_store TO event_store_appender;

-- pipeline_run is the only table whose rows transition state after insert
-- (status + completed_at set by close_run). event_log and alert_event stay
-- strictly append-only.
GRANT UPDATE (status, completed_at) ON event_store.pipeline_run TO event_store_appender;

REVOKE ALL ON ALL TABLES IN SCHEMA event_store FROM event_store_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA event_store TO event_store_reader;

ALTER DEFAULT PRIVILEGES IN SCHEMA event_store REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA event_store REVOKE ALL ON TABLES FROM event_store_appender;
ALTER DEFAULT PRIVILEGES IN SCHEMA event_store REVOKE ALL ON TABLES FROM event_store_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA event_store GRANT SELECT, INSERT ON TABLES TO event_store_appender;
ALTER DEFAULT PRIVILEGES IN SCHEMA event_store GRANT SELECT ON TABLES TO event_store_reader;
