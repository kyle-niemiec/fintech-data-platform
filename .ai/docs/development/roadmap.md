# Roadmap Progress Tracker

Last audited against repository state: **May 25, 2026**.

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
- [x] Read-only UI refinements: server-side pagination (`Page[T]` envelope, 25/50/100 page sizes) on Runs/Transactions/Alerts; Runs `backfill` filter + filter-aware empty-state guidance; 3-second polling unified across all live surfaces including Metrics; nav relabel/reorder (Runs → Transactions → Excel Upload → Backfill → Alerts → Metrics). CDC tuning: fraud risk threshold raised to `0.9`; load-gen cadence widened to 120-180s.
- [x] Further read-only UI refinements: Transactions rows link to the scoring CDC run (`run_id` resolved via `risk_flag.event_id` → `event_log` and attached to `/ui/oltp/transactions/recent`; unscored rows stay non-clickable); UI-inserted transactions carry a `trading.transaction.origin = 'manual_demo'` provenance marker rendered as a non-red "Manual" flag; per-run **Preview** tab (`GET /ui/runs/{id}/preview`, gated by `RunDetail.preview_kind`) shows the scored transaction for CDC-transaction runs or the first 10 rows of the uploaded `.xlsx` for non-quarantined Excel runs, with the gate enforced server-side so preview data is never served for ineligible runs; Metrics consumer-group lag is collapsible per group.
- [x] Table sorting + onboarding context: Runs/Transactions/Alerts sort **server-side** via `sort`/`dir` params (whitelisted `ORDER BY` builders with fixed tiebreakers; pagination follows the full-set order); the Metrics consumer-lag table sorts **client-side** within each group and is now **collapsed by default**. A reusable Meridian-branded `BusinessStory` callout explains the business purpose of each surface, rendered at the bottom of all six nav pages plus Run Detail.
- [x] Overview home page: the root path `/` now serves a `HomePage` that introduces the project goals (FINRA/SOC 2, event-driven, bronze/silver/gold, auditability), Meridian and its departments, the three pipelines, and a linked site map; the runs explorer moved to `/runs`. TopNav gains an "Overview" link and a home-linked brand mark; internal "back to runs" links repointed to `/runs`.

## Phase 9 - Portfolio Hardening

- [ ] End-to-end scenario fixtures (success, schema fail, fraud fail, replay).
- [ ] Architecture diagrams and evidence pack for interview walkthroughs.
- [ ] Local-to-cloud portability notes while preserving local-first stack.

## Phase 10 - Free-First CI/CD and Hosted Demo Operations

- [x] PR workflow lane (`.github/workflows/pr-ci.yml`) runs Python unit tests
  excluding `tests/integration`, plus UI `typecheck` and UI build.
- [x] Nightly workflow lane (`.github/workflows/integration-nightly.yml`) runs a
  deterministic full integration stack bring-up/test/teardown path.
- [x] Release workflow lane (`.github/workflows/release-tag-deploy.yml`) is
  semantic-tag triggered, validates semver, enforces `main` ancestry, reruns the
  integration gate, then deploys.
- [x] Release deploy and rollback automation is implemented via:
  - `infra/ops/ssm_release_deploy.sh`
  - `infra/ops/ec2_deploy_release.sh`
  - `infra/ops/generate_env.sh`
- [x] Hosted release state is persisted in SSM parameters:
  - `/meridian/demo/current_tag`
  - `/meridian/demo/last_good_tag`
- [x] Production demo exposure is simplified:
  - `ui` publishes `443:80` directly in base compose.
  - `ui` nginx proxies `/ui/*` to internal `api:8000`.
  - dev-only local browser ergonomics are isolated in `infra/compose/dev/demo-ui-access.yaml`.
- [x] UI release metadata support is implemented with optional
  `VITE_RELEASE_TAG`; footer displays `Version vX.Y.Z` only when present.
- [x] Operations/planning docs are updated to capture CI lanes, SSM-only deploy
  flow, rollback policy, ingress policy, and deploy-only env rotation.
- [x] Integration/deploy gate hardening is applied: Redpanda image references
  aligned to Docker Hub, optional Docker Hub auth step added to gate workflows,
  Terraform runner UID/GID mapping moved to host-derived values, `infra-up`
  default sequence is fail-fast, and integration test execution now collects
  deterministic error diagnostics and uses dual-network container attachment.
- [x] AWS account provisioning (EC2/IAM/OIDC trust/SG/DNS) remains manual in v1
  and is not automated by Terraform in this phase.
- [x] Repository rename alignment is in place for deploy auth boundaries:
  local `origin` points to `kyle-niemiec/meridian-fintech-demo` and the AWS
  OIDC deploy role trust-policy `sub` is scoped to the same repo.

## Phase 11 - Same-Domain Demo Launcher (Scale-to-Zero)

- [x] CloudFormation launcher stack template added at
  `infra/cloudformation/demo-launcher.yaml` with:
  - [x] CloudFront distribution for `meridian.codeflower.io`.
  - [x] Origin failover group (EC2 origin -> S3 launcher bucket) with
    `500/502/503/504` failover criteria.
  - [x] Public control Lambda Function URL (`POST /start`, `GET /status`).
  - [x] Function URL CORS `AllowMethods` is CloudFormation-valid for `AWS::Lambda::Url` (no explicit `OPTIONS` enum entry).
  - [x] Stop Lambda + EventBridge Scheduler invoke role.
  - [x] Optional Route53 alias creation when hosted zone id is provided.
- [x] Launcher control implementation exists in repo:
  - [x] Control Lambda starts stopped EC2 instances and creates one-time
    auto-stop schedules.
  - [x] Repeated `POST /start` while instance is not `stopped` does not extend
    the stop window.
  - [x] Status endpoint returns instance state, stop schedule timestamp, and
    app readiness.
- [x] Static launcher landing assets exist and are parameterized at deploy time
  with Function URL + demo host.
- [x] Release workflow integrates launcher stage between integration gate and
  EC2 deploy:
  - [x] detects launcher-related changes against previous semver tag.
  - [x] forces apply when launcher stack is missing.
  - [x] skips launcher apply when unchanged and stack already exists.
- [x] Deterministic helper script
  `infra/ops/deploy_demo_launcher_stack.sh` packages/deploys the stack and syncs
  launcher static assets.
- [x] Planning operations/roadmap docs updated for Phase 11 architecture and
  runbook contracts.
- [x] AWS account resources and release variables required by launcher remain
  manual provisioning and environment wiring in v1.
- [ ] Live AWS launcher prerequisites are still pending manual operator
  execution (ACM cert for `meridian.codeflower.io` in `us-east-1`, initial
  launcher stack apply, and hosted-domain DNS cutover to CloudFront).
