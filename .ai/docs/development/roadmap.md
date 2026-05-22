# Roadmap Progress Tracker

Last audited against repository state: **May 20, 2026**.

Legend:
- `[x]` complete
- `[ ]` not complete or still in progress

## Phase 1 - Event-Driven Foundation

- [x] Redpanda is the canonical broker (compose service on internal network).
- [x] Dedicated event-store database runs as an isolated Postgres instance.
- [x] Internal Docker network boundaries enforced (`platform_internal` is `internal: true`; data-plane services publish no host ports).
- [x] MinIO bucket notifications are wired to Redpanda.
- [x] Redpanda topic ACLs and service identities are defined in Terraform `identity`.
- [x] Partitioning standards are enforced in active writers/jobs (topic keys, event-store monthly partition automation via pg_partman/pg_cron, object-path partition templates).

## Phase 2 - Encryption and Append-Only Roles

- [x] MinIO SSE-KMS is enforced via KES + Vault Transit.
- [x] Encrypted writes are enforced on `bronze/*`, `silver/*`, `gold/*`, and `quarantine/*`.
- [x] `landing/*` and `raw/*` remain writable without mandatory KMS headers.
- [x] Append-focused event-store runtime role permissions are defined in Terraform `bootstrap` (`event_append_runtime` -> `event_store_appender`).
- [x] Query runtime remains read-only (`event_query_runtime` -> `event_store_reader`).
- [x] Rotation runbook guidance exists for Vault transit keys, MinIO users, and event-store runtime logins.

## Phase 3 - Excel Pipeline

- [x] ClamAV scanner worker consumes `ingest.excel.uploaded.v1` and enforces size/type/malware gates.
- [x] Trigger worker consumes `ingest.excel.scanned.pass.v1` and creates idempotent Airflow DAG runs (`dag_run_id=excel_validation__<run_id>`).
- [x] Airflow `excel_validation` DAG performs schema validation and emits:
  - [x] `ingest.excel.raw.ready.v1` on pass (`pipeline_run` remains `running`)
  - [x] `ingest.excel.quarantined.v1` on fail (`pipeline_run` closes `quarantined`)
- [x] Bronze writer consumes `ingest.excel.raw.ready.v1`, writes Parquet to bronze with SSE-KMS headers, emits `ingest.excel.bronze.ready.v1`, and closes run `completed` (or `failed` with alert on error).
- [x] Excel scanner and bronze writer now use fresh event-store connections per persistence phase and keep Kafka offsets uncommitted for replay when event-store finalization/persistence fails.
- [x] Terraform identity provisions dedicated Redpanda principals for scanner, airflow trigger, and bronze writer with least-privilege topic/group ACLs.
- [x] Terraform bootstrap provisions dedicated MinIO validation principal (`landing/raw/quarantine` scope) used by the Airflow validation DAG.

## Phase 4 - CDC and Fraud Pipeline

- [x] Dedicated OLTP Postgres (`wal_level=logical`) with `trading.transaction` and `trading.risk_flag` schema, per-role credentials (`oltp_app`, `cdc_replicator`, `oltp_ui_reader`), and a `cdc_pub` publication.
- [x] Synthetic load generator emits one primary OLTP event type per cycle (`transaction`, `loan`, `loan_payment`, or `loan_status_history`) with required same-cycle side effects, randomized 30-60s cadence, and fraud-shaped transaction mixes for continuous scoring visibility.
- [x] Debezium Server streams WAL changes to Redpanda and collapses `trading.*` tables onto canonical `cdc.oltp.raw.v1`.
- [x] Fraud worker consumes raw CDC events, scores transactions with the demo continuous model, upserts `trading.risk_flag` idempotently via `(raw_topic, raw_partition, raw_offset)`, and emits `cdc.oltp.assessed.v1`.
- [x] CDC bronze writer batches assessed events, writes zero-transformation Parquet to `bronze/source=cdc/...` with SSE-KMS, emits `cdc.oltp.bronze.ready.v1`, and records a `cdc_checkpoint` row per flush.
- [x] Event-store DDL adds `event_store.cdc_checkpoint`; `append_cdc_checkpoint` helper is part of `event_store.PgEventStore`.
- [x] Root UI runs view is generalized across pipelines with a multi-select pipeline pill filter and a Recent Transactions tab backed by `oltp_ui_reader`.
- [x] `fraud_worker` persists an internal `cdc.oltp.assessed.started.v1` event_log row in the same transaction as `open_run`, satisfying deferred `pipeline_run`/`event_log` commit invariants.
- [x] `fraud_worker` event-store writes now use fresh connection-factory sessions per persistence phase; handler failures continue to leave Kafka offsets uncommitted for replay.
- [x] `cdc_bronze_writer` event-store prepare/finalize/failure-mark phases now use fresh connection-factory sessions instead of a long-lived connection.

## Phase 5 - Salesforce Pipeline

- [x] Mock Salesforce service and incremental pull logic are implemented.
- [x] Scheduled incremental pull DAG trigger is implemented.
- [x] Airflow ingestion DAG code is modularized into package + task-module layout (`excel_validation/`, `salesforce_pull/`) with stable DAG/task identifiers.
- [x] Pull cursor history and raw response artifacts are persisted.
- [x] Bronze-ready events for CRM objects are emitted.
- [x] `salesforce_incremental_pull.pull_sobject` now persists a `ingest.sf.pull.started.v1` event_log row in the same transaction as `open_run`, satisfying the deferred run/event_log commit invariant before `raw.ready` publish.
- [x] `salesforce_bronze_writer` now uses fresh event-store connection-factory sessions, and treats post-publish finalization failures as retryable (offset left uncommitted for replay).

## Phase 6 - Curated Layer Orchestration

- [x] Trino + Iceberg REST catalog are wired for curated transforms with SSE-KMS.
- [x] `lakehouse.silver.dim_opportunity` and `lakehouse.gold.kpi_pipeline_conversion` are implemented for the Salesforce Opportunity vertical slice.
- [x] Listener/transform DAG pair pattern is implemented for curated handoffs.
- [x] `silver_curated_promotion` consumes `ingest.salesforce.bronze.ready.v1`, opens curated runs with `parent_run_id`, stages/tokenizes, merges via Trino, records `event_store.silver_checkpoint`, emits `pipeline.silver.completed.v1`, and closes runs transactionally.
- [x] `gold_curated_aggregation` consumes `pipeline.silver.completed.v1`, opens curated runs with `parent_run_id`, inserts KPI rows via Trino, records `event_store.gold_checkpoint`, emits `pipeline.gold.completed.v1`, and closes runs transactionally.
- [x] Event-store has `silver_checkpoint`/`gold_checkpoint` tables and `append_silver_checkpoint`/`append_gold_checkpoint` helpers.
- [x] Event-store runtime SQL is externalized into package resources and executed through SQLAlchemy Core while preserving `PgEventStore` API behavior.
- [x] `masking` deterministic HMAC-SHA256 library is implemented and used by silver curation.
- [x] Redpanda curated consumer-group ACL extensions and Airflow connection seeding are implemented.
- [x] Follow-on silver entities: `dim_account`, `dim_loan`.
- [x] Follow-on facts: `fact_loan_payment`, `fact_commission_adjustment`, `loan_status_history`.
- [x] Remaining gold KPIs: `kpi_portfolio_health`, `kpi_payment_performance`, `kpi_commission_economics`.
- [x] Curated CDC path.
- [x] Curated Excel path.
- [x] Silver merge DATE normalization accepts both plain date strings and timestamp-shaped strings (for example `YYYY-MM-DDTHH:MM:SS`) without failing Trino casts.
- [x] Gold listener ignores unsupported silver-domain completions instead of triggering unmapped gold runs.
- [x] CDC bronze-ready handoff persists parent run visibility before Kafka publish and records explicit failed status/alerts when publish/finalize steps fail.
- [x] Airflow runtime upgraded to 3.2.1 architecture (`api-server` + standalone `dag-processor`), with FAB auth manager and API v2-trigger compatibility for `excel_validation_trigger`.

## Phase 7 - Query Plane and UI

- [x] Read-model builders from event-store and stage events. (The request-time event-store query layer in `ui-api` *is* the read-model layer per planning; hardened with a bounded/`run_id`-filterable `/ui/alerts` and `tests/test_ui_query.py`. No materialized builder, by design.)
- [x] FastAPI is reframed as a read-only UI query API.
- [x] UI run explorer, lineage trace, and artifact explorer are implemented.
- [x] UI alert feed is implemented end-to-end in the frontend (`AlertsPage`, `useAlerts`, `AlertsTable`/`SeverityBadge`, TopNav `/alerts` route, and a per-run Alerts tab on run detail). Backend `/ui/alerts` already existed; this closed the frontend gap.
- [x] UI-triggered demo-data generation exists for the Excel source path.
- [x] UI-triggered demo-data generation is expanded across source adapters: CDC transaction injection (normal + high-risk fraud shape) via `POST /ui/demo/oltp/transaction` using the least-privilege `oltp_demo_writer` role, and an Excel schema-fail path (`valid=false`) that exercises quarantine. Salesforce is intentionally excluded (scheduled-only per planning).
- [x] Excel demo uploader identity is resolved at runtime from Keycloak `finance`-role users via the `meridian-demo-service` client; the static `DEMO_FINANCE_USERS` list is removed (Keycloak-unavailable returns `503`, no static fallback).

## Phase 8 - Replay and Observability Hardening

- [x] Replay tooling for topic offset and run-scoped backfills. (Synthetic backfill UI + API for Excel and CDC; `make replay-group` / `make consumer-lag` for Redpanda offset replay.)
- [x] DAG/event lag dashboards and failure analytics. (Consumer lag API + Metrics UI page with consumer group lag table and 30-day pipeline analytics; `is_backfill` badge on Runs Explorer.)
- [x] Deterministic recovery playbooks for each source pipeline. (Added Detect→Diagnose→Recover→Verify playbooks for Excel, CDC+Fraud, Salesforce, and Curated Promotion in `operations.md`.)

## Phase 9 - Portfolio Hardening

- [ ] End-to-end scenario fixtures (success, schema fail, fraud fail, replay).
- [ ] Architecture diagrams and evidence pack for interview walkthroughs.
- [ ] Local-to-cloud portability notes while preserving local-first stack.
