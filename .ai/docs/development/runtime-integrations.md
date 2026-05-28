# Runtime Integrations State

## Shared DAG Runtime Services
- DAG runtime helpers are centralized in `services/pipeline/dag_runtime.py`.
- Shared helper coverage includes:
  - UTC timestamp creation
  - SQLAlchemy-backed event-store connection setup via `meridian.libs.event_store.open_event_store_conn`
  - MinIO client creation via `meridian.libs.minio_store.build_minio_client`
  - Redpanda producer creation
- Airflow 3.x runtime topology uses `api-server` plus a standalone `dag-processor` service; orchestrator compose health checks now target `/api/v2/monitor/health`.
- Airflow 3.x scheduler/worker task SDK is pinned to `AIRFLOW__CORE__EXECUTION_API_SERVER_URL=http://airflow_api_server:8080/execution/` so task-start API calls do not default to `localhost` inside non-API containers.
- Airflow 3.x API-auth JWT signing is pinned via shared `AIRFLOW__API_AUTH__JWT_SECRET` so scheduler/triggerer/worker execution tokens validate consistently across containers.
- Airflow API UI redirect host is controlled by `AIRFLOW__API__BASE_URL`, which is set to `${AIRFLOW_PUBLIC_BASE_URL:-http://localhost:8080}` to keep browser redirects on the local host instead of Docker-internal DNS names.
- Airflow 3.x trigger import resolution requires the DAG bundle path on interpreter `sys.path`; orchestrator image sets `PYTHONPATH=/opt/airflow:/opt/airflow/dags:${PYTHONPATH}` so deferrable triggers can import module paths like `silver_curated.listener.apply_bronze_event`.

## Shared Worker Runtime Services
- Worker runtime helpers are centralized in `services/libs/service_runtime/runtime.py`.
- Shared helper coverage includes:
  - Kafka consumer config construction (including SASL env mapping)
  - Redpanda producer creation
- Event-store engine/connection lifecycle helpers are centralized in `services/libs/event_store/runtime.py`.
- Event-store engine defaults now enable SQLAlchemy stale-connection safeguards (`pool_pre_ping=True`, bounded `pool_recycle`) for worker resilience across Postgres restarts.
- Event-writing worker entrypoints now uniformly inject `open_event_store_conn` instead of holding long-lived event-store connections (`excel_scanner`, `excel_bronze_writer`, `salesforce_bronze_writer`, `cdc_bronze_writer`, `fraud_worker`).
- MinIO client construction helpers are centralized in `services/libs/minio_store/minio_client.py`.

## Dev Compose Pathing Note
- `infra/compose/dev/pgadmin.yaml` binds `servers.json` with long syntax and `bind.create_host_path: false` so missing path resolution fails fast instead of creating a directory.
- In multi-file compose usage, relative bind paths must stay relative to the first `-f` compose file.
- Compose build definitions no longer set `build.network: host`; default build networking is used so hosted `make infra-up` does not require Buildx `network.host` insecure entitlements.
- Dev-only host-network build behavior is restored via `infra/compose/dev/build-network-host.yaml`, which reapplies `build.network: host` for build-heavy services when using `make infra-up-dev`.

## Shared Worker Storage Adapter
- Worker MinIO object store behavior is centralized in `services/libs/minio_store/minio_object_store.py`.
- Shared adapter coverage includes:
  - `s3://` URI parsing
  - URI-based read/write helpers
  - object stat metadata normalization

## Pipeline Adoption
- Shared runtime helpers are applied in:
  - `services/pipeline/excel_validation/common.py`
  - `services/pipeline/salesforce_pull/common.py`

## Curated Trino Bootstrap
- Curated lakehouse schema/table DDL is bootstrap-managed in `infra/db/lakehouse-migrations/`.
- `infra/compose/curated-pipeline.yaml` runs one-shot `trino_curated_init` to apply ordered migrations through Trino CLI after `fintech_trino` becomes healthy.
- `make infra-curated-pipeline` readiness requires: `iceberg_rest` healthy, `trino` healthy, and `trino_curated_init` exit code `0`.
- Lakehouse migrations include follow-on Phase 6 entities/metrics (`03_...` through `10_...`) for `dim_account`, `dim_loan`, loan facts/history, commission adjustments, and portfolio/payment/commission KPI outputs.

## Curated Transform SQL Packaging
- Curated transform SQL is task-scoped and embedded in the task modules that execute it:
  - `services/pipeline/gold_curated/tasks/run_aggregation_sql.py`
  - `services/pipeline/silver_curated/tasks/merge_into_silver.py`
- The former `services/pipeline/sql/` directory is removed from the runtime image and repository.

## Curated Shared SQL Helpers
- Curated task SQL-literal helpers are centralized in `services/pipeline/curated_sql_helpers.py`.
- Gold and silver task modules reuse these shared helpers instead of duplicating local literal-escaping logic.
- Silver merge SQL date fields now normalize both plain-date and timestamp-shaped strings through a shared `_date_expr(...)` helper to avoid Trino `INVALID_CAST_ARGUMENT` failures on values like `YYYY-MM-DDTHH:MM:SS`.

## Source Contract Expansion
- CDC source contracts now include curated-driving entities from OLTP logical replication tables:
  - `trading.loan`
  - `trading.loan_payment`
  - `trading.loan_status_history`
- OLTP load generation now emits one primary event type per cycle with required same-cycle side effects and randomized 120-180s delay bounds (`OLTP_LOAD_GEN_INTERVAL_MIN_SECONDS`..`OLTP_LOAD_GEN_INTERVAL_MAX_SECONDS`).
- Excel scan-pass payload carries `schema_contract_id`; `commission_adjustment_v1` is available as a validated schema contract for curated commission paths.

## Query-Plane Demo Triggers and Identity Resolution
- The `ui-api` service hosts UI demo triggers under `/ui/demo/*`, separate from its read-only query endpoints. They write to source ingress only, each via a dedicated least-privilege identity, so the read/query path stays read-only.
- `POST /ui/demo/upload` (`services/workers/ui-api/routes/demo_upload.py`) generates a workbook via `services/demo_xlsx.py` and uploads to the landing bucket with the MinIO ingest identity; `valid=false` uses `generate_invalid_payroll_xlsx` (drops the required `net_amount` column) so the file clears scanning but is quarantined by validation.
- `POST /ui/demo/oltp/transaction` (`services/workers/ui-api/routes/demo_oltp.py` + `services/cdc_demo.py`) inserts one `trading.transaction` row through a new least-privilege `oltp_demo_writer` role (USAGE on `trading` + INSERT on `trading.transaction` only; created in `infra/db/oltp-migrations/03_create_roles.sh`, wired via `OLTP_DEMO_WRITER_*`). `high_risk=true` mirrors the fraud worker shape (AAPL > $10k).
- Excel demo uploader identities are resolved at runtime from Keycloak `finance`-role users (`services/workers/ui-api/services/keycloak_users.py`) using the `meridian-demo-service` confidential client (client-credentials grant + Admin role-users lookup, short-lived cache, stdlib `urllib`). The static `DEMO_FINANCE_USERS` env list is removed; Keycloak-unavailable returns `503` with no fallback.
- Terraform identity authorizes the `demo_service` service account for the Admin role-users lookup (`infra/terraform/identity/keycloak.tf`): the `GET /roles/{role}/users` endpoint requires **both** `realm-management` `view-users` and `view-realm` (Keycloak 26 — `view-users` alone returns 403). Because the client has `full_scope_allowed = false`, both roles are assigned to the service account **and** added to the client scope (`keycloak_generic_client_role_mapper`), or the token strips them.
- The uploader→scanner attribution contract is a single canonical object-metadata key `uploader-principal` (`UPLOADER_PRINCIPAL_METADATA_KEY` in `excel_scanner/scanner.py`); the MinIO S3 event `principalId` is treated as the ingress access-key actor, not the business uploader.

## Query-Plane Read Endpoints and UI Refresh
- The list read endpoints (`GET /ui/runs`, `/ui/oltp/transactions/recent`, `/ui/alerts`) return a paginated `Page[T]` envelope (`items`, `total`, `limit`, `offset`) with server-side `limit`/`offset`; `total` comes from a `count(*) OVER()` window so the UI can render page controls in one request. Default page size is 25 (options 25/50/100).
- `GET /ui/runs` also accepts a `backfill` filter (`true`/`false`) whose SQL mirrors the row-level `is_backfill` derivation (`strpos(trigger_event_ref, 'backfill_') > 0 OR trigger_type = 'backfill'`), so filtering composes correctly with pagination.
- `GET /ui/runs`, `/ui/oltp/transactions/recent`, and `/ui/alerts` accept `sort` + `dir` for **server-side** ordering over the full result set (so sort composes with pagination). `ORDER BY` is built only from per-endpoint whitelist maps in `ui_query.py` (`RUNS_SORT`/`RECENT_TX_SORT`/`ALERTS_SORT` via `_order_by`) — `sort`/`dir` never reach SQL as raw text; an unknown `sort` falls back to the endpoint default. Each clause appends a fixed recency tiebreaker for non-default columns and always ends with a unique key (`run_id`/`transaction_id`/`alert_id`) for stable paging. Notable keys: runs `duration` orders by `coalesce(completed_at, now()) - started_at`; transactions `risk_score` is `NULLS LAST`; alerts `severity` uses a `CASE` rank (high→medium→low) rather than alphabetical. The non-paginated Metrics consumer-lag table sorts client-side within each (default-collapsed) group.
- The frontend polls all live surfaces on a single 3-second cadence, including the Metrics page (`useConsumerLag`, `usePipelineAnalytics`). Paginated and metrics hooks keep previous data across refetches to avoid blank flicker; relative timestamps advance via a shared 1-second ticker (`lib/useNow.ts`) so they update even when a poll returns unchanged data.
- `GET /ui/metrics/consumer-lag` reads consumer-group lag over the **Kafka protocol** (`services/workers/ui-api/services/consumer_lag.py`: committed offsets via `AdminClient.list_consumer_group_offsets` + per-partition high watermarks via a `Consumer`), matching `make consumer-lag` (`rpk group describe`). It does **not** use the Redpanda Admin HTTP API, which does not serve consumer-group offsets (the old `/v1/groups` call 404'd). ui-api gained a `confluent-kafka` dependency and `REDPANDA_BOOTSTRAP_SERVERS` (PLAINTEXT locally; optional SASL via `REDPANDA_UI_SERVICE_*`). A missing group is skipped; only an unreachable broker returns 503.
- The Transactions page marks a row high-risk from server data (`risk_flags` populated by the fraud worker), not a threshold duplicated on the client.
- `GET /ui/oltp/transactions/recent` attaches the scoring CDC `run_id` to each row by mapping the latest `trading.risk_flag.event_id` to `event_store.event_log.run_id` (exact PK lookup against the separate event-store DB; skipped entirely when a page has no scored rows, so unscored transactions return `run_id = null` and the UI leaves them non-clickable). It also returns `trading.transaction.origin` (added by `infra/db/oltp-migrations/05_add_transaction_origin.sql`; `'manual_demo'` for UI-inserted rows via `services/cdc_demo.py`, else `NULL`), which the UI renders as a non-red "Manual" flag distinct from the red risk flags. `origin` is read straight from OLTP and never traverses CDC.

## Query-Plane Run Preview
- `GET /ui/runs/{run_id}/preview` is a read-only per-run preview gated by `RunDetail.preview_kind` (`'cdc_transaction' | 'excel' | null`, computed in `ui_query.get_run`): `cdc_transaction` for CDC runs whose event payload has `source_table = 'trading.transaction'`, `excel` for `excel_ingestion` runs not in `quarantined`/`scan_failed`, else `null`. The frontend uses `preview_kind` to decide tab visibility without fetching preview data, and lazy-loads the endpoint only while the Preview tab is open.
- The endpoint re-derives the same gate and returns **404** for ineligible runs (loan/payment CDC, quarantined Excel, Salesforce, curated), so preview bytes never leave the server. CDC-transaction runs return the scored transaction's OLTP details (resolved from the run's assessed-event `transaction_id`); Excel runs return the first 10 rows of the raw uploaded `.xlsx` — URI resolved from the run's event `input_uris`/`output_uris`, read from MinIO via `services/minio_upload.read_object`, parsed by `services/run_preview.parse_xlsx_preview` (pandas/openpyxl, JSON-safe cells).

## CDC Fraud Scoring Threshold
- `PLATFORM_RISK_THRESHOLD` (`services/workers/fraud_worker/scorer.py`) is `0.9`. It both gates the `risk_threshold_exceeded` flag and calibrates the continuous score so a transaction at an instrument's calibrated amount scores exactly the threshold.

## UI Header Runtime Integrations
- The environment identifier in the header (`apps/ui/src/components/layout/TopNav.tsx`) reads `import.meta.env.VITE_APP_ENV` and falls back to `"local"`. Build-arg plumbing mirrors `VITE_RELEASE_TAG`: Dockerfile `ARG/ENV VITE_APP_ENV` → compose `args.VITE_APP_ENV` → `generate_env.sh APP_ENV` → `env_templating.EnvTemplateRenderer.app_env`. Release-tag deploys set `APP_ENV=prod` in `infra/ops/ec2_deploy_release.sh`; local dev compose leaves it empty so the badge renders `env · local`.
- The header's GitHub repo block (`apps/ui/src/components/layout/GitHubRepoBlock.tsx`) fetches `https://api.github.com/repos/kyle-niemiec/fintech-data-platform` once on mount (anonymous, 60/hr/IP rate limit) to render stars and forks. The repo slug is hardcoded; failed/loading states fall back to em-dashes so header layout does not reflow.
