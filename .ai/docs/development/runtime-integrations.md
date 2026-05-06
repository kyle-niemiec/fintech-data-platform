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
  - `services/pipeline-orchestrator/dags/excel_validation.py`
  - `services/pipeline-orchestrator/dags/salesforce_incremental_pull.py`
