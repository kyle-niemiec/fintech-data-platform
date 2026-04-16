"""End-to-end curated pipeline integration test (skipped by default).

Enable with `pytest -m integration`. Requires the full foundation +
orchestration + curated-pipeline compose stack to be running, including
iceberg-rest, Trino, Redpanda, MinIO with SSE-KMS, and the event store.

When wired up, this test should:
  1. Seed a bronze parquet under a fresh run_id via the MinIO SDK.
  2. Publish ingest.salesforce.bronze.ready.v1 pointing at that URI.
  3. Poll lakehouse.silver.dim_opportunity until the rows land (SCD2
     MERGE completes) and pipeline.silver.completed.v1 reaches the
     event store.
  4. Poll lakehouse.gold.kpi_pipeline_conversion until the KPI row
     appears and pipeline.gold.completed.v1 is emitted.
  5. Confirm replay idempotency (republish the same event; no
     duplicate silver rows, no duplicate gold snapshot per stage).
  6. Confirm SCD2 change detection (republish with a changed
     stage_name; two rows for that opportunity_id with exactly one
     is_current=true).
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.integration


def test_curated_pipeline_end_to_end_placeholder() -> None:
    pytest.skip("integration harness wiring lands in a later phase")
