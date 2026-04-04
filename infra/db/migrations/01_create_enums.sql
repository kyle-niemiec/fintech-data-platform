-- Import the pgCrypto extension to create UUIDs
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Ingestion source types
CREATE TYPE ingestion_source AS ENUM (
  'excel_upload',
  'salesforce_crm',
  'transaction_cdc'
);

-- Ingestion lifecycle states
CREATE TYPE ingestion_status AS ENUM (
  'pending',
  'running',
  'completed',
  'failed',
  'cancelled'
);

-- Artifact storage stages
CREATE TYPE artifact_stage AS ENUM (
  'landing',
  'raw',
  'bronze',
  'silver',
  'gold',
  'quarantine'
);

-- Artifact data formats
CREATE TYPE artifact_format AS ENUM (
  'csv',
  'json',
  'parquet',
  'xlsx'
);
