# Code Modularity State

## DAG Responsibility Boundaries
- DAG files use a thin-wrapper pattern where orchestration remains in DAG modules and task logic is delegated to task modules.

## Curated Task Modules
- Task modules currently used for curated workflows:
  - `services/pipeline-orchestrator/dags/silver_curated/tasks/promotion_tasks.py`
  - `services/pipeline-orchestrator/dags/gold_curated/tasks/aggregation_tasks.py`
- Task package declarations are explicit:
  - `services/pipeline-orchestrator/dags/silver_curated/tasks/__init__.py`
  - `services/pipeline-orchestrator/dags/gold_curated/tasks/__init__.py`

## Behavioral Compatibility
- DAG identifiers, task identifiers, event types, and curated run lifecycle behavior are preserved through modularization and packaging changes.
