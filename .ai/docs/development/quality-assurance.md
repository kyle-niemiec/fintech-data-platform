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
- Command: `python3 -m py_compile services/workers/fraud_worker/handler.py tests/test_fraud_handler.py`
- Result: passed.
- Command: `python3 -m pytest -q tests/test_fraud_handler.py`
- Result: blocked in this workspace (`No module named pytest`).
