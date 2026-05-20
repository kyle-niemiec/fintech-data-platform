# Orchestration State

## Curated Workflow Topology
- Curated orchestration is separated into listener and transformation DAG layers per curation stage.
- Curated DAG stacks are packaged under:
  - `services/pipeline/gold_curated/`
  - `services/pipeline/silver_curated/`
- Curated route-selection is config-driven via `services/pipeline/curated_specs.py`; silver routing resolves by bronze topic payload (`sobject`, `source_table`, `schema_contract_id`) and gold routing resolves by `silver_domain`.
- Curated DAG tasks execute transform SQL only (`MERGE`/`INSERT`); Iceberg table/schema bootstrap is no longer performed in DAG runtime code.
- Curated task callables are split into one module per task name under each DAG's `tasks/` package (e.g. `open_curated_run.py`, `merge_into_silver.py`) instead of one monolithic task module.
- Task-scoped transform SQL is embedded directly in the task modules that execute it (`run_aggregation_sql.py`, `merge_into_silver.py`) rather than loaded from a shared orchestrator SQL directory.
- Curated tasks import `dag_runtime` helpers directly (`now_utc`, `open_event_store_conn`, `build_minio_client`) instead of via wrapper functions in domain `common.py`.

## Ingestion DAG Packaging
- `excel_validation` is packaged under `services/pipeline/excel_validation/` with task callables split under `tasks/`.
- `salesforce_incremental_pull` is packaged under `services/pipeline/salesforce_pull/` with task callables split under `tasks/`.
- Existing DAG IDs and task IDs are preserved (`excel_validation`, `salesforce_incremental_pull`) to avoid runtime contract drift.

## Stage Handoff Bindings
- Sensor apply-function bindings use packaged module paths for stage handoff:
  - `silver_curated.listener.apply_bronze_event`
  - `gold_curated.listener.apply_silver_event`
- `silver_curated_listener` subscribes to Salesforce + CDC + Excel bronze-ready topics; `gold_curated_listener` remains keyed on `pipeline.silver.completed.v1`.
- `gold_curated.listener.apply_silver_event` now drops unsupported `silver_domain` values (no `resolve_gold_metric` match) so non-routable silver completions do not open failing gold DAG runs.
- `cdc_bronze_writer` persists parent `pipeline_run` visibility before publishing `cdc.oltp.bronze.ready.v1`, then records publish metadata/checkpoint and closes the run; publish/finalize failures explicitly alert and mark the run `failed`.
- Airflow runtime startup is gated on curated Trino bootstrap completion (`trino_curated_init`) so curated DAGs do not start before required lakehouse tables exist.
- Airflow runtime runs on 3.x service topology: `airflow api-server` replaces `webserver`, and a dedicated `airflow dag-processor` service is started alongside scheduler/triggerer.
- Airflow auth manager is explicitly set to FAB (`airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager`) so existing `airflow users` bootstrap flow and UI login continue to work after 3.x migration.
- Excel validation trigger worker now targets Airflow REST API v2 (`/api/v2/dags/.../dagRuns`) with bearer token authentication via `/auth/token`.
- Excel validation trigger includes required `logical_date` when creating DAG runs through Airflow API v2, preventing 422 rejections that left runs parked at `ingest.excel.scanned.pass.v1`.
- Trino readiness gating checks `/v1/info/state == ACTIVE` before marking the Trino service healthy, preventing `trino_curated_init` from running while the coordinator is still initializing.
- `trino_curated_init` retries each migration command up to 30 times (2s backoff) to tolerate transient Trino startup race conditions during fresh infra boot.
- `salesforce_incremental_pull` opens `pipeline_run` before publishing `ingest.salesforce.raw.ready.v1` so downstream bronze workers cannot hit FK races on `event_log.run_id` during fast-consume windows.
- `salesforce_incremental_pull.pull_sobject` now appends an `ingest.sf.pull.started.v1` event_log row in the same transaction as `open_run`, satisfying the deferred event-store invariant that every inserted `pipeline_run` must commit with at least one `event_log` row.
- `fraud_worker` now appends an internal `cdc.oltp.assessed.started.v1` event_log row in the same transaction as `open_run`, preventing deferred-constraint failures on `pipeline_run` commits before `cdc.oltp.assessed.v1` publish completes.
- `fraud_worker` now decodes Debezium NUMERIC payloads for CDC loan/payment fields before assessed-envelope assembly; envelope-build failures after `cdc.oltp.assessed.started.v1` are explicitly alerted (`cdc_assessed_envelope_build_failed`) and the run is closed `failed` instead of lingering in `running`.
- `excel_scanner` no longer crashes the process for per-record persistence failures; failed messages remain uncommitted so Kafka replay can recover once event-store connectivity returns.
- `excel_bronze_writer` now treats post-publish event-store finalization failures as retryable (offset left uncommitted) while terminal conversion/write failures still attempt alert+failed close and then commit.
- `salesforce_bronze_writer` now uses event-store connection factories per persistence phase and treats post-publish finalization failures as retryable (offset left uncommitted) while terminal conversion/write failures still attempt alert+failed close and commit.
- `cdc_bronze_writer` now opens fresh event-store connections for prepare/finalize/failure-mark phases instead of reusing one long-lived connection; flush failures continue to replay without committing offsets.
- `fraud_worker` now opens fresh event-store connections for started/failure/completion persistence phases while preserving no-commit replay behavior on handler failures.
