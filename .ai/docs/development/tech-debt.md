# Tech Debt Ledger

Track temporary compromises and deferred cleanup work.

## Workflow
- Add an entry when introducing a workaround, deferral, or temporary guard.
- Update the entry whenever scope, impact, or timeline changes.
- Mark entries resolved in the same round they are fixed.
- Keep entries aligned with related code comments (`TODO`/`FIXME`/debt notes).

## Open Items

| ID | Date | Area | Description | Code Reference | Owner | Target | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TD-001 | 2026-05-05 | Process | Initialize debt ledger and replace placeholder with real debt entries as work proceeds. | `.ai/docs/development/tech-debt.md` | AI Session | 2026-05-05 | Resolved |
| TD-002 | 2026-05-05 | DAG modularity | Curated Airflow `@task` callables were extracted into per-domain task modules to reduce DAG file responsibility and support future curated-domain growth. | `services/pipeline-orchestrator/dags/silver_curated/tasks/promotion_tasks.py`, `services/pipeline-orchestrator/dags/gold_curated/tasks/aggregation_tasks.py` | AI Session | 2026-05-05 | Resolved |
| TD-003 | 2026-05-05 | Service boundaries | Curated lakehouse DDL bootstrap was executed inside Airflow DAG tasks instead of infra-managed Trino bootstrap; this was corrected by moving DDL to `infra/db/lakehouse-migrations` and gating Airflow startup on one-shot `trino_curated_init`. | `infra/db/lakehouse-migrations/01_silver_dim_opportunity.sql`, `infra/db/lakehouse-migrations/02_gold_kpi_pipeline_conversion.sql`, `infra/compose/curated-pipeline.yaml`, `infra/compose/orchestration.yaml` | AI Session | 2026-05-05 | Resolved |
| TD-004 | 2026-05-05 | DAG modularity | Curated DAG tasks were grouped per pipeline in monolithic files (`promotion_tasks.py`, `aggregation_tasks.py`), which reduced per-task ownership clarity; replaced with one-file-per-task modules under each `tasks/` package. | `services/pipeline-orchestrator/dags/silver_curated/tasks/`, `services/pipeline-orchestrator/dags/gold_curated/tasks/`, `tests/test_silver_curated_promotion_dag.py`, `tests/test_gold_curated_aggregation_dag.py` | AI Session | 2026-05-05 | Resolved |
| TD-005 | 2026-05-05 | SQL packaging | Curated transform SQL lived in shared external files and required placeholder text replacement at runtime; this was replaced by task-local SQL builders in the exact modules that execute SQL, and the now-unused `services/pipeline-orchestrator/sql/` folder was removed. | `services/pipeline-orchestrator/dags/gold_curated/tasks/run_aggregation_sql.py`, `services/pipeline-orchestrator/dags/silver_curated/tasks/merge_into_silver.py`, `services/pipeline-orchestrator/Dockerfile` | AI Session | 2026-05-05 | Resolved |
| TD-006 | 2026-05-05 | Helper duplication | Curated task SQL literal helpers were duplicated across silver/gold task modules, and curated `common.py` files had thin wrapper functions for `dag_runtime` helpers; these were consolidated into shared `curated_sql_helpers.py` and direct `dag_runtime` imports at call sites. | `services/pipeline-orchestrator/dags/curated_sql_helpers.py`, `services/pipeline-orchestrator/dags/gold_curated/tasks/run_aggregation_sql.py`, `services/pipeline-orchestrator/dags/silver_curated/tasks/merge_into_silver.py`, `services/pipeline-orchestrator/dags/gold_curated/common.py`, `services/pipeline-orchestrator/dags/silver_curated/common.py` | AI Session | 2026-05-05 | Resolved |
| TD-007 | 2026-05-06 | UI filtering | Homepage `CURATED` filter used stale pipeline names (`silver_curation`, `gold_curation`) and excluded valid curated runs; updated mapping to canonical `curated_promotion`. | `apps/ui/src/lib/pipelineColors.ts` | AI Session | 2026-05-06 | Resolved |
