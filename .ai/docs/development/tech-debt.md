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
