# Code Modularity State

## DAG Responsibility Boundaries
- DAG files use a thin-wrapper pattern where orchestration remains in DAG modules and task logic is delegated to task modules.

## DAG Package Layout
- Curated DAG stacks are package-scoped:
  - `services/pipeline/silver_curated/`
  - `services/pipeline/gold_curated/`
- Ingestion DAG stacks are package-scoped:
  - `services/pipeline/excel_validation/`
  - `services/pipeline/salesforce_pull/`

## Task Module Split
- Curated task callables are split into task-scoped modules under each DAG package:
  - `services/pipeline/silver_curated/tasks/`
  - `services/pipeline/gold_curated/tasks/`
- Excel validation task callables are split into task-scoped modules:
  - `services/pipeline/excel_validation/tasks/parse_conf.py`
  - `services/pipeline/excel_validation/tasks/download_object.py`
  - `services/pipeline/excel_validation/tasks/validate.py`
  - `services/pipeline/excel_validation/tasks/write_raw.py`
  - `services/pipeline/excel_validation/tasks/write_quarantine.py`
  - `services/pipeline/excel_validation/tasks/emit_event.py`
- Salesforce incremental-pull task callables are split into task-scoped modules:
  - `services/pipeline/salesforce_pull/tasks/list_sobjects.py`
  - `services/pipeline/salesforce_pull/tasks/pull_sobject.py`

## Behavioral Compatibility
- DAG identifiers, task identifiers, event types, trigger references, and run lifecycle behavior are preserved through modularization and packaging changes.

## Shared Library Namespace
- The `services/libs/` tree is deployed into runtime images under the `meridian` namespace
  (worker Dockerfiles `COPY services/libs -> /app/meridian/libs`; the orchestrator image places it at
  `/opt/airflow/meridian/libs` on `PYTHONPATH`), so application and DAG code imports shared libraries
  as `meridian.libs.*` (for example `meridian.libs.event_store`, `meridian.libs.minio_store`,
  `meridian.libs.redpanda_events`).
- Tests import the same `meridian.libs.*` namespace; it is supplied by the environment (the container
  image, or a `PYTHONPATH` whose `meridian/libs` resolves to `services/libs`), not fabricated by the
  test harness. `tests/conftest.py` only adds worker/pipeline source roots for `workers.*` imports.

## Worker Runtime Modularity
- Shared worker bootstrap/runtime helpers are centralized in `services/libs/service_runtime/runtime.py` for:
  - Kafka consumer config construction
  - Redpanda producer creation
- Event-store SQLAlchemy engine/connection helpers are centralized in `services/libs/event_store/runtime.py`.
- MinIO client construction and object-store adapter helpers are centralized in `services/libs/minio_store/`.
- Duplicate `MinioObjectStore` entrypoint classes were consolidated to a shared adapter in `services/libs/minio_store/minio_object_store.py`.
- Worker and orchestrator event-store call sites use the `PgEventStore` namespace API with a single class-method declaration per operation in `event_store.PgEventStore`.
- Event-store runtime SQL is externalized under `services/libs/event_store/sql/event_store/`, with `PgEventStore` loading cached statements from package resources.
