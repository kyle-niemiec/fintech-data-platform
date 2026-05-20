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
- Internal load generator is the only writer into the OLTP. Each cycle emits one primary event type (`transaction`, `loan`, `loan_payment`, or `loan_status_history`) with required same-cycle side effects, and sleeps for a randomized 10-60s interval before the next cycle.
- Loan lifecycle statuses used by the generator are `current` (active, on schedule), `delinquent` (active, past due), and `paid_off` (closed). `loan_status_history` is append-only and captures lifecycle transitions; `loan.status_code` remains the current-state snapshot.

### Partition Keys and Run Boundary

- Raw and assessed topics: key is `<source_table>:<business_key>` so all events for a transaction colocate on a single partition.
- Run boundary:
  - Fraud worker: one `pipeline_run` per consumed raw event, `trigger_event_ref = <topic>:<partition>:<offset>`.
  - CDC bronze writer: one `pipeline_run` per flushed batch, per source table.

### Rule Versioning

- `fraud_rule_version` is a static model label (`demo_continuous_risk`) in this demo, persisted on every `trading.risk_flag` row and assessed envelope payload for traceability only (not version governance).
- Continuous risk model (bounded in `[0, 1)`) per instrument:
  - Risk score function: `r(x) = -r_f/(x+r_f) + 1`
  - Factor calibration at platform threshold `r_t=0.7`: `r_f(X) = X*(1-r_t)/r_t`
  - A row is flagged when `r(x) >= r_t`.
- Instrument calibration (`X` is dollar amount at which risk crosses `0.7`):

| Instrument | `X` (USD) | `r_f` |
| --- | ---: | ---: |
| `AAPL` | 10000 | 4285.714 |
| `MSFT` | 14000 | 6000.000 |
| `GOOG` | 30000 | 12857.143 |
| `AMZN` | 22000 | 9428.571 |
| `TSLA` | 8000 | 3428.571 |
| `JPM` | 5000 | 2142.857 |
| `BAC` | 3000 | 1285.714 |
| `NVDA` | 1000 | 428.571 |

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

### Curated Promotion Pipeline (Salesforce Opportunity slice)

The Phase 6 vertical slice implements the Salesforce Opportunity curated path end-to-end. The same listener/transform DAG-pair pattern will be reused for every curated sub-path; this section documents what actually runs today.

- Transform engine: Trino coordinator with the Iceberg connector, iceberg-rest REST catalog (JDBC-backed by the platform Postgres), SSE-KMS enforced on every S3 write.
- Listener + transform split:
  - `silver_curated_listener` (`@continuous`): `AwaitMessageTriggerFunctionSensor` on `ingest.salesforce.bronze.ready.v1`; fans out `TriggerDagRunOperator` per envelope.
  - `silver_curated_promotion` (`schedule=None`, `max_active_runs>1`): one run per bronze event.
  - `gold_curated_listener` (`@continuous`): same pattern on `pipeline.silver.completed.v1`.
  - `gold_curated_aggregation` (`schedule=None`, `max_active_runs>1`): one run per silver envelope.
- Silver transform (`lakehouse.silver.dim_opportunity`):
  1. Open a `curated_promotion` run with `parent_run_id = bronze.run_id`.
  2. Read the bronze parquet referenced by the envelope, tokenize AccountId via `masking.tokenize(scope='salesforce_account_id')`, and write a staging parquet under `s3://.../warehouse/_staging/<curated_run_id>/` with SSE-KMS headers.
  3. Execute SCD2 `MERGE INTO lakehouse.silver.dim_opportunity` via Trino, matched by `opportunity_id` on `is_current=true`, closing the current row on any source-faithful business-attribute change and inserting a new current version.
  4. In a single event-store transaction: `append_silver_checkpoint` (with merge stats), `append_event` for `pipeline.silver.completed.v1`, `close_run(status='completed')`. The Kafka produce happens before the transaction so persistence is authoritative.
- Gold transform (`lakehouse.gold.kpi_pipeline_conversion`):
  1. Open a `curated_promotion` run with `parent_run_id = silver.run_id`.
  2. Execute the aggregation INSERT from `lakehouse.silver.dim_opportunity` where `is_current=true`, grouped by `stage_name`, with counts (won/lost/open), $ totals, and closed-rate conversion per (snapshot_date, stage_name).
  3. In a single event-store transaction: `append_gold_checkpoint` (metric=`pipeline_conversion`), `append_event` for `pipeline.gold.completed.v1`, `close_run(status='completed')`.
- Failure paths: on any Airflow task failure the DAG-level `on_failure_callback` emits `pipeline.{silver,gold}.failed.v1` and closes the curated run `failed`.
- Masking: `masking` provides deterministic HMAC-SHA256 primitives (`tokenize`, `mask_email`, `hash_pii`, `redact`) with salt sourced from `PLATFORM_MASKING_SALT`. Determinism is load-bearing - re-runs must produce the same silver natural keys for the MERGE to behave as SCD2.
- Identity: Trino and iceberg-rest both use the existing `MINIO_TRINO_WRITE` S3 identity scoped to `silver/*` and `gold/*` with KMS enforcement. DAG Kafka access uses the existing `rp_orchestrator_service` Redpanda principal, extended with READ on `pipeline.silver.completed.v1` and the two curated consumer groups (`airflow-curated-silver-v1`, `airflow-curated-gold-v1`).

### Curated Promotion Pipeline (Phase 6 follow-on completion)

Phase 6 follow-on implementation keeps the same run contract (`pipeline_name=curated_promotion`) and stage topics while expanding routing/config:

- `silver_curated_listener` subscribes to:
  - `ingest.salesforce.bronze.ready.v1`
  - `cdc.oltp.bronze.ready.v1`
  - `ingest.excel.bronze.ready.v1`
- Bronze envelope routing resolves to silver domains:
  - Salesforce `Opportunity` -> `salesforce_opportunity` -> `lakehouse.silver.dim_opportunity` (SCD2)
  - Salesforce `Account` -> `salesforce_account` -> `lakehouse.silver.dim_account` (SCD2)
  - CDC `trading.loan` -> `loan` -> `lakehouse.silver.dim_loan` (SCD2)
  - CDC `trading.loan_payment` -> `loan_payment` -> `lakehouse.silver.fact_loan_payment` (append)
  - CDC `trading.loan_status_history` -> `loan_status_history` -> `lakehouse.silver.loan_status_history` (append)
  - Excel `commission_adjustment_v1` -> `commission_adjustment` -> `lakehouse.silver.fact_commission_adjustment` (append)
- `gold_curated_aggregation` metric routing:
  - `salesforce_opportunity` -> `pipeline_conversion` -> `lakehouse.gold.kpi_pipeline_conversion`
  - `loan` -> `portfolio_health` -> `lakehouse.gold.kpi_portfolio_health`
  - `loan_payment` -> `payment_performance` -> `lakehouse.gold.kpi_payment_performance`
  - `commission_adjustment` -> `commission_economics` -> `lakehouse.gold.kpi_commission_economics`

KPI formula definitions used by the Phase 6 follow-on:
- `portfolio_health`: grouped by `status_code` over current `dim_loan` rows with `loan_count`, `total_principal_balance`, `delinquent_loan_count` (`days_past_due > 0`), and `avg_days_past_due`.
- `payment_performance`: daily aggregate over `fact_loan_payment` with `payment_count`, `total_payment_amount`, `on_time_payment_count` (`payment_posted_at <= payment_due_date`), and `late_payment_count` (`payment_posted_at > payment_due_date`).
- `commission_economics`: grouped by `adjustment_reason` over `fact_commission_adjustment` with `adjustment_count` and `total_adjustment_amount`.
