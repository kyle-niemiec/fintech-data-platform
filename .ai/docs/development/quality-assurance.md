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
- Excel worker runtime resilience and commit semantics are covered by:
  - `tests/test_excel_worker_main_loops.py`
  - `tests/test_excel_bronze_writer.py`
  - `tests/test_scanner.py`
- Salesforce/CDC/Fraud worker runtime resilience and connection-factory adoption are covered by:
  - `tests/test_worker_main_loops_additional.py`
  - `tests/test_salesforce_bronze_writer.py`
  - `tests/test_cdc_bronze_writer_main.py`
  - `tests/test_fraud_handler.py`
  - `tests/test_event_store_connection_factory_audit.py`
- Fraud risk-event alerting (`cdc_fraud_high_risk` raised on the high-risk success path, suppressed for normal scores and on deduped replays) is covered by `tests/test_fraud_handler.py`.
- Query-plane and demo-trigger coverage (Phase 7):
  - `tests/test_ui_query.py` exercises the read-model handlers directly (runs, run detail/404, events, lineage, artifacts, recent transactions, bounded/`run_id`-filtered alerts).
  - `tests/test_demo_oltp.py` covers the CDC transaction generator's fraud-shape contract (high-risk AAPL>$10k vs normal <$10k) and single-insert behavior.
  - `tests/test_keycloak_users.py` covers finance-user resolution: selection, list caching, email fallback, and failure modes (missing secret, empty role, bad token/response, transport error).
  - `tests/test_demo_xlsx.py` extends to assert the invalid workbook is a real xlsx that fails the payroll_v1 contract; `tests/test_scanner.py` adds canonical `uploader-principal` metadata override coverage.

## Latest Round Verification
- Tests import shared libraries via `meridian.libs.*`, matching the runtime image layout
  (`services/libs -> /app/meridian/libs`). The namespace must be supplied by the environment;
  `tests/conftest.py` only adds worker/pipeline source roots and does not fabricate `meridian`.
- Canonical run is inside the container image (where `meridian` already exists). To run locally,
  expose the libraries as `meridian` first, e.g.:
  `M=$(mktemp -d); mkdir "$M/meridian"; ln -s "$PWD/services/libs" "$M/meridian/libs"; PYTHONPATH="$M" python3 -m pytest -q`
- Result: 182 passed, 3 skipped, 0 failed. The 3 skips are integration-tier tests under
  `tests/integration/` that require testcontainers/MinIO and are out of scope for the unit run.
