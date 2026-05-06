# Runtime Integrations State

## Shared DAG Runtime Services
- DAG runtime helpers are centralized in `services/pipeline-orchestrator/dags/dag_runtime.py`.
- Shared helper coverage includes:
  - UTC timestamp creation
  - Event-store database connection setup
  - MinIO client creation
  - Redpanda producer creation

## Pipeline Adoption
- Shared runtime helpers are applied in:
  - `services/pipeline-orchestrator/dags/excel_validation/common.py`
  - `services/pipeline-orchestrator/dags/salesforce_pull/common.py`

## Curated Trino Bootstrap
- Curated lakehouse schema/table DDL is bootstrap-managed in `infra/db/lakehouse-migrations/`.
- `infra/compose/curated-pipeline.yaml` runs one-shot `trino_curated_init` to apply ordered migrations through Trino CLI after `fintech_trino` becomes healthy.
- `make infra-curated-pipeline` readiness requires: `iceberg_rest` healthy, `trino` healthy, and `trino_curated_init` exit code `0`.

## Curated Transform SQL Packaging
- Curated transform SQL is task-scoped and embedded in the task modules that execute it:
  - `services/pipeline-orchestrator/dags/gold_curated/tasks/run_aggregation_sql.py`
  - `services/pipeline-orchestrator/dags/silver_curated/tasks/merge_into_silver.py`
- The former `services/pipeline-orchestrator/sql/` directory is removed from the runtime image and repository.

## Curated Shared SQL Helpers
- Curated task SQL-literal helpers are centralized in `services/pipeline-orchestrator/dags/curated_sql_helpers.py`.
- Gold and silver task modules reuse these shared helpers instead of duplicating local literal-escaping logic.
