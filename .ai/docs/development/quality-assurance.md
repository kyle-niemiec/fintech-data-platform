# Quality Assurance State

## Structural Coverage
- Structural tests validate curated DAG boundaries and task delegation for:
  - `tests/test_silver_curated_promotion_dag.py`
  - `tests/test_gold_curated_aggregation_dag.py`
- Curated config/routing coverage exists in:
  - `tests/test_curated_specs.py`
- Lakehouse follow-on migration presence is covered in:
  - `tests/test_lakehouse_migrations_phase6.py`
- Ingestion DAG packaging and task-module split is covered by:
  - `tests/test_excel_validation_dag.py`
  - `tests/test_salesforce_incremental_pull_dag.py`

## Latest Round Verification
- Tests import shared libraries via `meridian.libs.*`, matching the runtime image layout
  (`services/libs -> /app/meridian/libs`). The namespace must be supplied by the environment;
  `tests/conftest.py` only adds worker/pipeline source roots and does not fabricate `meridian`.
- Canonical run is inside the container image (where `meridian` already exists). To run locally,
  expose the libraries as `meridian` first, e.g.:
  `M=$(mktemp -d); mkdir "$M/meridian"; ln -s "$PWD/services/libs" "$M/meridian/libs"; PYTHONPATH="$M" python3 -m pytest -q`
- Result: 142 passed, 3 skipped, 0 failed. The 3 skips are integration-tier tests under
  `tests/integration/` that require testcontainers/MinIO and are out of scope for the unit run.
