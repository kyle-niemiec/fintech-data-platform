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
- MinIO client construction helpers are centralized in `services/libs/minio_store/minio_client.py`.

## Dev Compose Pathing Note
- `infra/compose/dev/pgadmin.yaml` binds `servers.json` with long syntax and `bind.create_host_path: false` so missing path resolution fails fast instead of creating a directory.
- In multi-file compose usage, relative bind paths must stay relative to the first `-f` compose file.

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
- OLTP load generation now emits one primary event type per cycle with required same-cycle side effects and randomized 30-60s delay bounds (`OLTP_LOAD_GEN_INTERVAL_MIN_SECONDS`..`OLTP_LOAD_GEN_INTERVAL_MAX_SECONDS`).
- Excel scan-pass payload carries `schema_contract_id`; `commission_adjustment_v1` is available as a validated schema contract for curated commission paths.
