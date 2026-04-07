-- Least-privilege role templates for control plane and pipeline services.
-- Roles are NOLOGIN templates. Bind LOGIN users per environment (see comments at bottom).

-- Lock down default public schema access
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- Idempotent role creation
DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'db_migrator') THEN
        CREATE ROLE db_migrator NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'control_plane_writer') THEN
        CREATE ROLE control_plane_writer NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'control_plane_reader') THEN
        CREATE ROLE control_plane_reader NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ingestion_writer') THEN
        CREATE ROLE ingestion_writer NOLOGIN;
    END IF;
END;
$$;

-- Schema visibility
GRANT USAGE ON SCHEMA public TO db_migrator, control_plane_writer, control_plane_reader, ingestion_writer;

-- Migration/admin role: DDL + full data access
GRANT CREATE ON SCHEMA public TO db_migrator;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO db_migrator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO db_migrator;

-- Control-plane writer: FastAPI API runtime
-- Writes ingestion_run only. artifact and lineage_record are written exclusively
-- by pipeline services (ingestion_writer). Read access on all three for API responses.
GRANT SELECT, INSERT ON TABLE public.ingestion_run TO control_plane_writer;
GRANT UPDATE (status, completed_at) ON TABLE public.ingestion_run TO control_plane_writer;
GRANT SELECT ON TABLE public.artifact TO control_plane_writer;
GRANT SELECT ON TABLE public.lineage_record TO control_plane_writer;

-- Control-plane reader: audit/ops role for platform health inspection
-- Used by the ops UI and auditors to inspect run metadata, artifact records, and lineage.
-- This is NOT a data consumer role -- data scientists and executives query via Trino.
GRANT SELECT ON TABLE public.ingestion_run TO control_plane_reader;
GRANT SELECT ON TABLE public.artifact TO control_plane_reader;
GRANT SELECT ON TABLE public.lineage_record TO control_plane_reader;

-- Ingestion writer: pipeline services (Airflow, CDC, CRM)
-- Full write path across all three control-plane tables.
GRANT SELECT, INSERT ON TABLE public.ingestion_run TO ingestion_writer;
GRANT UPDATE (status, completed_at) ON TABLE public.ingestion_run TO ingestion_writer;
GRANT SELECT, INSERT ON TABLE public.artifact TO ingestion_writer;
GRANT SELECT, INSERT ON TABLE public.lineage_record TO ingestion_writer;

-- Enum type usage (scoped to roles that actually write those types)
GRANT USAGE ON TYPE ingestion_source TO control_plane_writer, ingestion_writer;
GRANT USAGE ON TYPE ingestion_status TO control_plane_writer, ingestion_writer;
GRANT USAGE ON TYPE artifact_stage TO ingestion_writer;
GRANT USAGE ON TYPE artifact_format TO ingestion_writer;

-- Default privileges: FOR ROLE db_migrator ensures future tables created by migrations
-- automatically inherit these grants without requiring manual re-grants per migration.
ALTER DEFAULT PRIVILEGES FOR ROLE db_migrator IN SCHEMA public
    GRANT SELECT ON TABLES TO control_plane_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE db_migrator IN SCHEMA public
    GRANT SELECT ON TABLES TO control_plane_writer;
ALTER DEFAULT PRIVILEGES FOR ROLE db_migrator IN SCHEMA public
    GRANT SELECT, INSERT ON TABLES TO ingestion_writer;

-- Login user bindings (run manually with secret-managed passwords per environment):
--
-- CREATE ROLE api_runtime LOGIN PASSWORD '<rotate_me>';
-- GRANT control_plane_writer TO api_runtime;
--
-- CREATE ROLE audit_runtime LOGIN PASSWORD '<rotate_me>';
-- GRANT control_plane_reader TO audit_runtime;
--
-- CREATE ROLE airflow_runtime LOGIN PASSWORD '<rotate_me>';
-- GRANT ingestion_writer TO airflow_runtime;
