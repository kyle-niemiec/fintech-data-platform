# Development Roadmap

This roadmap is ordered around event-driven delivery, not API-first delivery.

Terraform work is split into two phases applied via the in-network `terraform_runner` container:
- `bootstrap` - storage and database resources (Postgres roles/databases, MinIO buckets, bucket policies, encryption configuration).
- `identity` - Keycloak realm/clients, Redpanda topic ACLs, and service identities.

## Phase 1 - Event-Driven Foundation

Completed:
- Redpanda is the canonical broker (compose service on internal network).
- Dedicated event-store database runs as an isolated Postgres instance.
- Internal Docker network boundaries enforced (`platform_internal` is `internal: true`; data-plane services publish no host ports).
- Wire MinIO bucket notifications to Redpanda.
- Define Redpanda topic ACLs and service identities in the Terraform `identity` phase.
- Enforce partitioning standards in active writers/jobs (topic keys, event-store monthly partition automation via pg_partman/pg_cron, object-path partition templates).

## Phase 2 - Encryption and Append-Only Roles

Network isolation is already in place via Phase 1, so this phase focuses on data-at-rest and database authorization controls.

- Enforce MinIO SSE-KMS via KES + Vault Transit.
- Enforce encrypted writes on `bronze/*`, `silver/*`, `gold/*`, and `quarantine/*`.
- Keep `landing/*` and `raw/*` writable without mandatory KMS headers in this phase.
- Define append-only database runtime role permissions for the event-store DB in Terraform `bootstrap` (`event_append_runtime` -> `event_store_appender`).
- Keep query runtime read-only (`event_query_runtime` -> `event_store_reader`).
- Add key/credential rotation runbook guidance for Vault transit keys, MinIO users, and event-store runtime logins.

## Phase 3 - Excel Pipeline

Completed:
- ClamAV scanner worker consumes `ingest.excel.uploaded.v1` and enforces size/type/malware gates.
- Dedicated trigger worker consumes `ingest.excel.scanned.pass.v1` and creates idempotent Airflow DAG runs (`dag_run_id=excel_validation__<run_id>`).
- Airflow `excel_validation` DAG performs schema validation and emits:
  - `ingest.excel.raw.ready.v1` on pass (`pipeline_run` remains `running`)
  - `ingest.excel.quarantined.v1` on fail (`pipeline_run` closes `quarantined`)
- Dedicated bronze writer consumes `ingest.excel.raw.ready.v1`, writes Parquet to bronze with SSE-KMS headers, emits `ingest.excel.bronze.ready.v1`, and closes run `completed` (or `failed` with alert on error).
- Terraform identity provisions dedicated Redpanda principals for scanner, airflow trigger, and bronze writer with least-privilege topic/group ACLs.
- Terraform bootstrap provisions dedicated MinIO validation principal (`landing/raw/quarantine` scope) used by the Airflow validation DAG.

## Phase 4 - CDC and Fraud Pipeline

Completed:
- Dedicated OLTP Postgres (`wal_level=logical`) with `trading.transaction` and `trading.risk_flag` schema, per-role credentials (`oltp_app`, `cdc_replicator`, `oltp_ui_reader`), and a `cdc_pub` publication.
- Synthetic load generator seeds transactions on a configurable cadence with varied instrument/amount mixes so continuous scoring behavior is observable in every run.
- Debezium Server (single container, `pgoutput`) streams WAL changes to Redpanda with a `ByLogicalTableRouter` SMT collapsing all `trading.*` tables onto the canonical `cdc.oltp.raw.v1` topic.
- Fraud worker consumes raw CDC events, scores transactions with the demo continuous model (`r(x) = -r_f/(x+r_f)+1`, `r_f(X)=X*(1-r_t)/r_t`, `r_t=0.7`), upserts `trading.risk_flag` idempotently via `(raw_topic, raw_partition, raw_offset)`, and emits `cdc.oltp.assessed.v1`.
- CDC bronze writer batches assessed events, writes zero-transformation Parquet to `bronze/source=cdc/...` with SSE-KMS, emits `cdc.oltp.bronze.ready.v1`, and records a `cdc_checkpoint` row per flush (LSN range + Kafka offsets + record count).
- Event-store DDL adds `event_store.cdc_checkpoint`; `append_cdc_checkpoint` helper joins the existing `platform_events.event_store` API.
- Root UI runs view generalized across pipelines with a multi-select pipeline pill filter and a Recent Transactions tab backed by a least-privilege `oltp_ui_reader` role.

## Phase 5 - Salesforce Pipeline

- Add mock Salesforce service and incremental pull logic.
- Implement scheduled incremental pull DAG trigger.
- Persist pull cursor history and raw response artifacts.
- Emit bronze-ready events for CRM objects.

## Phase 6 - Curated Layer Orchestration

- Implement bronze-to-silver DAG with dedupe, masking, and SCD2 controls.
- Implement silver-to-gold DAG with KPI aggregation.
- Emit stage completion/failure events for all curated transitions.

## Phase 7 - Query Plane and UI

- Implement read-model builders from event-store and stage events.
- Reframe FastAPI as read-only UI query API.
- Implement UI run explorer, lineage trace, artifact explorer, and alert feed.
- Add UI-triggered demo-data generation via source-adapter services.

## Phase 8 - Replay and Observability Hardening

- Add replay tooling for topic offset and run-scoped backfills.
- Add DAG/event lag dashboards and failure analytics.
- Add deterministic recovery playbooks for each source pipeline.

## Phase 9 - Portfolio Hardening

- Add end-to-end scenario fixtures (success, schema fail, fraud fail, replay).
- Add architecture diagrams and evidence pack for interview walkthroughs.
- Add local-to-cloud portability notes while preserving local-first stack.
