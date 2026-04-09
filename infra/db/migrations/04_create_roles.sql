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

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'data_analyst') THEN
        CREATE ROLE data_analyst NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'data_executive') THEN
        CREATE ROLE data_executive NOLOGIN;
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
-- Full write path for all three control-plane tables.
-- Artifact and lineage records can be registered directly via the API (Phase 3+)
-- as well as by pipeline services using ingestion_writer.
GRANT SELECT, INSERT ON TABLE public.ingestion_run TO control_plane_writer;
GRANT UPDATE (status, completed_at) ON TABLE public.ingestion_run TO control_plane_writer;
GRANT SELECT, INSERT ON TABLE public.artifact TO control_plane_writer;
GRANT SELECT, INSERT ON TABLE public.lineage_record TO control_plane_writer;

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
GRANT USAGE ON TYPE artifact_stage TO control_plane_writer, ingestion_writer;
GRANT USAGE ON TYPE artifact_format TO control_plane_writer, ingestion_writer;
