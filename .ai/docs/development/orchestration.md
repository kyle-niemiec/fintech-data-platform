# Orchestration State

## Curated Workflow Topology
- Curated orchestration is separated into listener and transformation DAG layers per curation stage.
- Curated DAG stacks are packaged under:
  - `services/pipeline-orchestrator/dags/gold_curated/`
  - `services/pipeline-orchestrator/dags/silver_curated/`

## Stage Handoff Bindings
- Sensor apply-function bindings use packaged module paths for stage handoff:
  - `silver_curated.listener.apply_bronze_event`
  - `gold_curated.listener.apply_silver_event`
