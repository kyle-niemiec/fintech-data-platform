# Data Model

This document defines the target-state model for an event-driven fintech pipeline.

## Modeling Principles

- Keep ingestion history immutable and replayable.
- Persist source-faithful records in bronze before business transformation.
- Treat event metadata as first-class data.
- Use append-only semantics for audit/event storage.
- Isolate PII in controlled layers and restrict downstream exposure.

## Global Metadata Contract

All source and transformation records must carry:

| Field | Type | Purpose |
| --- | --- | --- |
| `run_id` | UUID | Correlates all events/artifacts in one execution chain |
| `event_id` | UUID | Dedupe and immutable event identity |
| `trace_id` | UUID | Cross-service trace correlation |
| `source_system` | TEXT | `excel`, `oltp_cdc`, `salesforce` |
| `occurred_at` | TIMESTAMPTZ | Source/system event time |
| `ingested_at` | TIMESTAMPTZ | Processing ingestion time |
| `schema_version` | TEXT | Event/payload contract version |
| `payload_hash` | TEXT | Integrity check for payload immutability |

## Event Store Database (Exclusive Audit Store)

The event store is separate from UI query-service persistence and source OLTP systems.

## Event-Store Partitioning Plan

- `event_store.event_log` is partitioned by `occurred_at` monthly ranges.
- `event_store.alert_event` is partitioned by `occurred_at` monthly ranges.
- Each `event_log` partition must include:
  - unique index on `(topic, partition, offset)`
  - index on `(run_id, occurred_at)`
  - index on `(trace_id, occurred_at)`
  - index on `(event_type, occurred_at)`
- Partition naming convention uses `event_log_YYYY_MM` and `alert_event_YYYY_MM`.

### `event_store.pipeline_run`

| Column | Type | Notes |
| --- | --- | --- |
| `run_id` | UUID PK | Pipeline run identity |
| `source_type` | TEXT | `excel`, `cdc`, `salesforce` |
| `trigger_type` | TEXT | `bucket_event`, `schedule`, `manual`, `replay` |
| `status` | TEXT | `pending`, `running`, `completed`, `failed`, `quarantined` |
| `started_at` | TIMESTAMPTZ | Run start |
| `completed_at` | TIMESTAMPTZ | Run end |
| `initiator` | TEXT | Service or user identity |

### `event_store.event_log`

| Column | Type | Notes |
| --- | --- | --- |
| `event_id` | UUID PK | Immutable event identity |
| `run_id` | UUID FK | Links to pipeline_run |
| `event_type` | TEXT | Topic event name |
| `topic` | TEXT | Kafka topic |
| `partition` | INT | Kafka partition |
| `offset` | BIGINT | Kafka offset |
| `occurred_at` | TIMESTAMPTZ | Event production time |
| `payload` | JSONB | Full event payload |
| `payload_hash` | TEXT | SHA256 hash |
| `schema_version` | TEXT | Contract version |

### `event_store.file_ingress`

| Column | Type | Notes |
| --- | --- | --- |
| `file_ingress_id` | UUID PK | File ingress record |
| `run_id` | UUID FK | Correlated run |
| `source_file_name` | TEXT | Original file name |
| `landing_uri` | TEXT | Landing object path |
| `raw_uri` | TEXT | Raw output path |
| `quarantine_uri` | TEXT | Quarantine path if failed |
| `bronze_uri` | TEXT | Bronze parquet path |
| `scan_status` | TEXT | `pass` or `fail` |
| `validation_status` | TEXT | `pass` or `fail` |
| `errors` | JSONB | Structured validation failures |

### `event_store.cdc_checkpoint`

| Column | Type | Notes |
| --- | --- | --- |
| `checkpoint_id` | UUID PK | Checkpoint row |
| `run_id` | UUID FK | Correlated run |
| `source_table` | TEXT | CDC table |
| `lsn_start` | TEXT | Initial LSN |
| `lsn_end` | TEXT | Final LSN |
| `kafka_partition` | INT | Partition consumed |
| `offset_start` | BIGINT | Start offset |
| `offset_end` | BIGINT | End offset |
| `record_count` | BIGINT | Processed records |

### `event_store.sf_pull`

| Column | Type | Notes |
| --- | --- | --- |
| `pull_id` | UUID PK | Pull attempt identity |
| `run_id` | UUID FK | Correlated run |
| `object_name` | TEXT | Salesforce object |
| `cursor_from` | TIMESTAMPTZ | Incremental lower bound |
| `cursor_to` | TIMESTAMPTZ | Incremental upper bound |
| `request_uri` | TEXT | API request metadata location |
| `response_uri` | TEXT | Raw response artifact |
| `response_checksum` | TEXT | Integrity checksum |
| `status` | TEXT | `succeeded` or `failed` |
| `retry_attempt` | INT | Retry index |

### `event_store.alert_event`

| Column | Type | Notes |
| --- | --- | --- |
| `alert_id` | UUID PK | Alert identity |
| `run_id` | UUID FK | Correlated run |
| `severity` | TEXT | `info`, `warning`, `critical` |
| `category` | TEXT | `scan`, `validation`, `fraud`, `orchestration` |
| `summary` | TEXT | UI feed text |
| `details` | JSONB | Structured details |
| `occurred_at` | TIMESTAMPTZ | Alert creation time |

## Bronze Layer Model

Bronze is source-faithful, append-only, and for restricted forensic/audit use.

### Bronze Rules

- Keep raw semantics from source payload.
- Include source ordering metadata (`lsn`, Kafka offsets, pull cursors).
- Do not apply business normalization here.
- Partition object paths by source + date + run ID for targeted replay and selective reads.

### Core Bronze Datasets

- `bronze.commission_adjustment_raw`
- `bronze.oltp_transaction_cdc_raw`
- `bronze.salesforce_account_raw`
- `bronze.salesforce_opportunity_raw`
- `bronze.salesforce_contact_raw`

Each bronze row includes global metadata fields and source-specific raw payload attributes.

## Silver Layer Model

Silver is cleaned and analytics-ready with controlled PII handling.

### Silver Transform Rules

- Deduplicate by natural keys + source ordering metadata.
- Apply data quality constraints and standardization.
- Separate sensitive entities into restricted PII schemas.
- Apply SCD Type 2 for dimensions that require historical attribute tracking.

### Representative Silver Entities

- `silver.dim_account`
- `silver.dim_opportunity`
- `silver.dim_loan`
- `silver.fact_loan_payment`
- `silver.fact_commission_adjustment`
- `silver.loan_status_history`

PII-heavy tables remain in restricted schema variants and are not exposed directly to general analyst roles.

## Gold Layer Model

Gold contains KPI-level aggregates with no direct PII.

### Representative Gold Outputs

- `gold.kpi_portfolio_health`
- `gold.kpi_payment_performance`
- `gold.kpi_pipeline_conversion`
- `gold.kpi_commission_economics`

## Immutability and Correction Policy

- Incorrect data is corrected by appending new events and derived records.
- Historical records are preserved for replay and audit.
- Backfills are traceable to replay run IDs and checkpoint ranges.

## Data Retention and Replay

- Event topics retain sufficient history for replay windows.
- Event store tracks offsets/checkpoints per consumer group.
- Bronze retains source-faithful records for forensic and compliance review.

## Object-Path Partitioning Plan

Canonical path dimensions:
- `source`
- `year/month/day` (and `hour` for CDC-heavy paths)
- `run_id`
- domain-specific dimensions (`table`, `object`, `domain`, `metric`)

Examples:
- `bronze/source=cdc/table=<table>/year=YYYY/month=MM/day=DD/hour=HH/run_id=<run_id>/...`
- `bronze/source=excel/year=YYYY/month=MM/day=DD/run_id=<run_id>/...`
- `silver/domain=<domain>/year=YYYY/month=MM/day=DD/run_id=<run_id>/...`
- `gold/metric=<metric>/year=YYYY/month=MM/day=DD/run_id=<run_id>/...`
