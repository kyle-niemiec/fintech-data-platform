# Runtime Integrations State

## Shared DAG Runtime Services
- DAG runtime helpers are centralized in `services/pipeline-orchestrator/dags/dag_runtime.py`.
- Shared helper coverage includes:
  - UTC timestamp creation
  - SQLAlchemy-backed event-store connection setup via `meridian.libs.event_store.open_event_store_conn`
  - MinIO client creation via `meridian.libs.minio_store.build_minio_client`
  - Redpanda producer creation

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
  - `services/pipeline-orchestrator/dags/excel_validation/common.py`
  - `services/pipeline-orchestrator/dags/salesforce_pull/common.py`

## Curated Trino Bootstrap
- Curated lakehouse schema/table DDL is bootstrap-managed in `infra/db/lakehouse-migrations/`.
- `infra/compose/curated-pipeline.yaml` runs one-shot `trino_curated_init` to apply ordered migrations through Trino CLI after `fintech_trino` becomes healthy.
- `make infra-curated-pipeline` readiness requires: `iceberg_rest` healthy, `trino` healthy, and `trino_curated_init` exit code `0`.
- Lakehouse migrations include follow-on Phase 6 entities/metrics (`03_...` through `10_...`) for `dim_account`, `dim_loan`, loan facts/history, commission adjustments, and portfolio/payment/commission KPI outputs.

## Curated Transform SQL Packaging
- Curated transform SQL is task-scoped and embedded in the task modules that execute it:
  - `services/pipeline-orchestrator/dags/gold_curated/tasks/run_aggregation_sql.py`
  - `services/pipeline-orchestrator/dags/silver_curated/tasks/merge_into_silver.py`
- The former `services/pipeline-orchestrator/sql/` directory is removed from the runtime image and repository.

## Curated Shared SQL Helpers
- Curated task SQL-literal helpers are centralized in `services/pipeline-orchestrator/dags/curated_sql_helpers.py`.
- Gold and silver task modules reuse these shared helpers instead of duplicating local literal-escaping logic.

## Source Contract Expansion
- CDC source contracts now include curated-driving entities from OLTP logical replication tables:
  - `trading.loan`
  - `trading.loan_payment`
  - `trading.loan_status_history`
- Excel scan-pass payload carries `schema_contract_id`; `commission_adjustment_v1` is available as a validated schema contract for curated commission paths.
