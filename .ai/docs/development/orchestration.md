# Orchestration State

## Curated Workflow Topology
- Curated orchestration is separated into listener and transformation DAG layers per curation stage.
- Curated DAG stacks are packaged under:
  - `services/pipeline-orchestrator/dags/gold_curated/`
  - `services/pipeline-orchestrator/dags/silver_curated/`
- Curated DAG tasks execute transform SQL only (`MERGE`/`INSERT`); Iceberg table/schema bootstrap is no longer performed in DAG runtime code.
- Curated task callables are split into one module per task name under each DAG's `tasks/` package (e.g. `open_curated_run.py`, `merge_into_silver.py`) instead of one monolithic task module.
- Task-scoped transform SQL is embedded directly in the task modules that execute it (`run_aggregation_sql.py`, `merge_into_silver.py`) rather than loaded from a shared orchestrator SQL directory.
- Curated tasks now import `dag_runtime` helpers directly (`now_utc`, `open_event_store_conn`, `build_minio_client`) and no longer route those calls through thin wrappers in domain `common.py`.

## Stage Handoff Bindings
- Sensor apply-function bindings use packaged module paths for stage handoff:
  - `silver_curated.listener.apply_bronze_event`
  - `gold_curated.listener.apply_silver_event`
- Airflow runtime startup is gated on curated Trino bootstrap completion (`trino_curated_init`) so curated DAGs do not start before required lakehouse tables exist.
