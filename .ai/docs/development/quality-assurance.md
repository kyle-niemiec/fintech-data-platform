# Quality Assurance State

## Structural Coverage
- Structural tests validate curated DAG boundaries and task delegation for:
  - `tests/test_silver_curated_promotion_dag.py`
  - `tests/test_gold_curated_aggregation_dag.py`

## Environment Constraint
- `pytest` is currently unavailable in this environment, so full test-suite execution status is not confirmed here.
- `npm` is currently unavailable in this environment, so `apps/ui` TypeScript typecheck (`npm run typecheck`) could not be executed in-session.

## Latest Round Verification
- Homepage pipeline filter mapping was corrected so `CURATED` filters by `curated_promotion`, which is the pipeline name emitted for silver/gold curated runs.
- Command attempt: `npm run typecheck` from `apps/ui` failed with `/bin/bash: npm: command not found`.
