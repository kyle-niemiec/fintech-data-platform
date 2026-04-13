# Source Pipelines

This document defines source-ingress behavior outside the API boundary.

All source pipelines are event-driven and write audit events to the dedicated event store.

## Shared Requirements

- Source ingress must be independent from FastAPI availability.
- Every stage transition must emit a versioned event.
- Failure paths must write explicit quarantine or error events.
- Run traceability must include source ID, run ID, artifact URI, and event lineage.
- Event-first rule: source/schedule trigger event is produced before `pipeline_run` creation.
- Artifact payload standard: all artifact-bearing events use `input_uris[]` and `output_uris[]`.

## Excel Ingestion Pipeline

### Trigger and Ownership

- Trigger: MinIO object-created event on `landing/finance/` prefix.
- Source actor: finance uploader identity with prefix-scoped write permissions.
- Demo mode: the internal Excel generator selects a random actor from Keycloak users assigned to the `finance` role.
- IaC owners: MinIO bucket notifications (Terraform + Compose wiring), topic ACLs (Terraform), scanner and validator services (Compose).

### Processing Flow

1. Upload lands in `landing/`.
2. MinIO emits `ingest.excel.uploaded.v1` (this trigger event initiates the run).
3. Scan worker performs:
   - ClamAV malware scan.
   - Extension/content-type check.
   - File-size guardrail check.
4. Scan verdict event emitted:
   - pass: `ingest.excel.scanned.pass.v1`
   - fail: `ingest.excel.scanned.fail.v1`
5. Airflow validation DAG consumes pass events, performs schema validation.
6. Validation outcome:
   - fail -> original file copied to `quarantine/` + `ingest.excel.quarantined.v1`
   - pass -> raw canonical payload written to `raw/` + `ingest.excel.raw.ready.v1`
7. Airflow conversion task writes Parquet to `bronze/` and emits `ingest.excel.bronze.ready.v1`.

### Audit Requirements

- File name persists as `<original_name>__<run_id>.<ext>`.
- Event store links run ID, uploaded object URI, quarantine/raw URI, bronze URI.
- Validation failure reasons are persisted as structured error payloads.

## CDC + Fraud Pipeline

### Trigger and Ownership

- Trigger: Debezium change event from OLTP transaction tables.
- Internal load generator: synthetic customer/transaction writes every 5-10 minutes to keep CDC active in demo mode.
- IaC owners: Debezium connector config, Kafka topic ACLs, and fraud worker runtime.

### Processing Flow

1. Debezium publishes raw event to `cdc.oltp.raw.v1` (this trigger event initiates the run).
2. Fraud worker consumes raw event and applies rule scoring.
3. Worker writes risk outcome to OLTP flag table and emits `cdc.oltp.assessed.v1`.
4. Bronze writer consumes assessed events and writes source-faithful Parquet to `bronze/cdc/`.
5. Writer emits `cdc.oltp.bronze.ready.v1` for downstream curated processing.

### Legal Defensibility Rules

- Bronze payload must preserve Debezium and Kafka metadata.
- LSN and source commit ordering fields are mandatory.
- No business transformation before bronze write.
- Replay from topic offsets must reconstruct identical bronze records.

## Salesforce Pipeline

### Trigger and Ownership

- Trigger modes:
   - Scheduled incremental pull (Airflow schedule).
- IaC owners: Airflow DAG and connection secrets, mock Salesforce service, event-store schema, and topic ACLs.

Salesforce pulls are internal-only. FastAPI/UI does not initiate pull execution.

### Processing Flow

1. Pull start event emitted: `ingest.sf.pull.started.v1` with cursor window (this trigger event initiates the run).
2. Airflow executes incremental query using last successful cursor.
3. Raw API response envelope persisted to `raw/salesforce/`.
4. Pull result event emitted:
   - success: `ingest.sf.pull.succeeded.v1`
   - failure: `ingest.sf.pull.failed.v1`
5. Successful pulls are transformed to Parquet and written to bronze.
6. Bronze completion event emitted: `ingest.sf.bronze.ready.v1`.

### Audit Requirements

- Persist pull cursor, request timestamp, response checksum, and artifact URI.
- Link each pull attempt to a stable run ID and retried-attempt chain.
- Retries must append events; no in-place overwrite of history.

## Curated Promotion Pipeline (Common)

1. Any `*.bronze.ready.v1` event routes to Airflow curated DAG chain and initiates a curated run.
2. Curated run uses `pipeline_class=curated`, `pipeline_name=curated_promotion`, and stores upstream ingestion `run_id` in `parent_run_id`.
3. Silver DAG performs normalization, dedupe, and masking.
4. Gold DAG performs KPI aggregation and business rollups.
5. Each stage emits `pipeline.stage.completed.v1` or `pipeline.stage.failed.v1`.
6. UI feed reads stage events from event-store read models.

Curated runs are separate from ingestion runs; they may reference the upstream ingestion run for lineage but are orchestrated independently.
