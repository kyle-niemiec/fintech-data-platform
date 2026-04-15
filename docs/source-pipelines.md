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

- Trigger: MinIO object-created event on `landing/source=excel/` prefix.
- Source actor: finance uploader identity with prefix-scoped write permissions.
- Demo mode: the internal Excel generator selects a random actor from Keycloak users assigned to the `finance` role.
- IaC owners: MinIO bucket notifications (Terraform + Compose wiring), topic ACLs (Terraform), scanner/trigger/bronze-writer services (Compose), Airflow DAG runtime (Compose + DAG code).

### Processing Flow

1. Upload lands in partitioned landing path (`landing/source=excel/year=YYYY/month=MM/day=DD/run_id=<run_id>/...`).
2. MinIO emits `ingest.excel.uploaded.v1` (this trigger event initiates the run).
3. Scan worker performs:
   - ClamAV malware scan.
   - Extension/content-type check.
   - File-size guardrail check.
4. Scan verdict event emitted:
   - pass: `ingest.excel.scanned.pass.v1`
   - fail: `ingest.excel.scanned.fail.v1`
5. `excel_validation_trigger` worker consumes `ingest.excel.scanned.pass.v1` and creates an idempotent `excel_validation` DAG run (`dag_run_id=excel_validation__<run_id>`).
6. Airflow validation DAG performs schema validation.
7. Validation outcome:
   - fail -> original file copied to `quarantine/` + `ingest.excel.quarantined.v1`
   - pass -> raw canonical payload written to `raw/` + `ingest.excel.raw.ready.v1`
8. `excel_bronze_writer` worker consumes `ingest.excel.raw.ready.v1`, converts to Parquet, writes to `bronze/` with SSE-KMS headers, and emits `ingest.excel.bronze.ready.v1`.

### Audit Requirements

- File name persists as `<original_name>__<run_id>.<ext>`.
- Event store links run ID and stage artifact URIs through `input_uris[]` / `output_uris[]`.
- Validation failure reasons are persisted as structured error payloads.

## CDC + Fraud Pipeline

### Topology

- Source of truth: dedicated OLTP Postgres (`wal_level=logical`) with `trading.transaction` and `trading.risk_flag`.
- Debezium Server (single container, `pgoutput` plugin) writes directly to Redpanda. A `ByLogicalTableRouter` SMT collapses per-table topics onto one canonical contract topic (`cdc.oltp.raw.v1`); Debezium offsets live on a named volume.
- Fraud worker (`group.id=fraud-worker-v1`, 12-partition topic) consumes raw events, scores with pure functional rules, and emits `cdc.oltp.assessed.v1`.
- CDC bronze writer batches assessed events, writes zero-transformation Parquet to `bronze/source=cdc/table=<table>/year=YYYY/month=MM/day=DD/hour=HH/run_id=<run_id>/...`, and emits `cdc.oltp.bronze.ready.v1`.
- Internal load generator (container, 60s default cadence) is the only writer into the OLTP; a tunable fraction of inserts are high-value AAPL to fire the fraud rule.

### Partition Keys and Run Boundary

- Raw and assessed topics: key is `<source_table>:<business_key>` so all events for a transaction colocate on a single partition.
- Run boundary:
  - Fraud worker: one `pipeline_run` per consumed raw event, `trigger_event_ref = <topic>:<partition>:<offset>`.
  - CDC bronze writer: one `pipeline_run` per flushed batch, per source table.

### Rule Versioning

- `fraud_rule_version` (currently `rules-v1`: `high_value_aapl` when instrument == AAPL and amount > 10000, score 0.9) is persisted on every `trading.risk_flag` row and on the assessed envelope payload so historical assessments are reproducible even as rules evolve.

### Idempotency and At-Least-Once

- `trading.risk_flag` carries `raw_topic`, `raw_partition`, `raw_offset` with a unique constraint. Kafka redeliveries no-op at the OLTP upsert; the assessed event is still re-emitted, and the event-store dedupes on `(topic, partition, kafka_offset, occurred_at)`.
- Fraud worker ordering: OLTP upsert -> produce assessed -> event-store append -> Kafka commit. Any failure before the commit causes replay; all three writes are idempotent.
- CDC bronze writer uses per-batch `run_id` in the object path, so replays produce new files without overwriting. Silver-stage dedup by `(source_table, transaction_id, lsn)` is a later-phase concern.

### Legal Defensibility Rules

- Bronze Parquet columns include `op`, `source_lsn`, `source_ts_ms`, `kafka_topic`, `kafka_partition`, `kafka_offset`, `event_id`, `fraud_rule_version`, `risk_score`, `risk_flags`, plus the full assessed payload JSON verbatim.
- No business transformation before bronze write; batches are sorted by LSN, then Kafka offset.
- `event_store.cdc_checkpoint` records first/last LSN, Kafka offset range, and record count per flush to prove coverage.
- Replay from topic offsets reconstructs identical bronze records with new run IDs; prior runs remain untouched.

### Failure Modes

- Debezium downtime: replication slot `cdc_slot` retains WAL; offsets volume preserves progress; operations runbook monitors `pg_replication_slots`.
- Produce failure after OLTP upsert: run is marked `failed` with `cdc_assessed_produce_failed` alert; replay re-emits.
- Checkpoint failure after Parquet write: alert raised; object remains and is replay-superseded.

## Salesforce Pipeline

### Trigger and Ownership

- Trigger modes:
   - Scheduled incremental pull (Airflow schedule).
- IaC owners: Airflow DAG and connection secrets, mock Salesforce service, event-store schema, and topic ACLs.

Salesforce pulls are internal-only. FastAPI/UI does not initiate pull execution.

### Processing Flow

1. Pull start event emitted: `ingest.sf.pull.started.v1` with cursor window (this trigger event initiates the run).
2. Airflow executes incremental query using last successful cursor.
3. Raw API response envelope persisted to partitioned raw path (`raw/source=salesforce/object=<object>/year=YYYY/month=MM/day=DD/run_id=<run_id>/...`).
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
5. Silver and gold stages emit versioned completion/failure topics (`pipeline.silver.*.v1`, `pipeline.gold.*.v1`).
6. UI feed reads stage events from event-store read models.

Curated runs are separate from ingestion runs; they may reference the upstream ingestion run for lineage but are orchestrated independently.
