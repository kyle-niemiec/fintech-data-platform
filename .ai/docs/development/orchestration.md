# Orchestration State

## Curated Workflow Topology
- Curated orchestration is separated into listener and transformation DAG layers per curation stage.
- Curated DAG stacks are packaged under:
  - `services/pipeline-orchestrator/dags/gold_curated/`
  - `services/pipeline-orchestrator/dags/silver_curated/`
- Curated DAG tasks execute transform SQL only (`MERGE`/`INSERT`); Iceberg table/schema bootstrap is no longer performed in DAG runtime code.
- Curated task callables are split into one module per task name under each DAG's `tasks/` package (e.g. `open_curated_run.py`, `merge_into_silver.py`) instead of one monolithic task module.
- Task-scoped transform SQL is embedded directly in the task modules that execute it (`run_aggregation_sql.py`, `merge_into_silver.py`) rather than loaded from a shared orchestrator SQL directory.
- Curated tasks import `dag_runtime` helpers directly (`now_utc`, `open_event_store_conn`, `build_minio_client`) instead of via wrapper functions in domain `common.py`.

## Ingestion DAG Packaging
- `excel_validation` is packaged under `services/pipeline-orchestrator/dags/excel_validation/` with task callables split under `tasks/`.
- `salesforce_incremental_pull` is packaged under `services/pipeline-orchestrator/dags/salesforce_pull/` with task callables split under `tasks/`.
- Existing DAG IDs and task IDs are preserved (`excel_validation`, `salesforce_incremental_pull`) to avoid runtime contract drift.

## Stage Handoff Bindings
- Sensor apply-function bindings use packaged module paths for stage handoff:
  - `silver_curated.listener.apply_bronze_event`
  - `gold_curated.listener.apply_silver_event`
- Airflow runtime startup is gated on curated Trino bootstrap completion (`trino_curated_init`) so curated DAGs do not start before required lakehouse tables exist.
- Airflow API auth backend configuration now explicitly includes session auth plus basic auth in compose env to align with Airflow UI requirements ahead of Airflow 3.0.
- Trino readiness gating checks `/v1/info/state == ACTIVE` before marking the Trino service healthy, preventing `trino_curated_init` from running while the coordinator is still initializing.
- `trino_curated_init` retries each migration command up to 30 times (2s backoff) to tolerate transient Trino startup race conditions during fresh infra boot.
