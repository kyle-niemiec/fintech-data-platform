"""End-to-end Salesforce pipeline integration test (skipped by default).

Enable with `pytest -m integration`. Requires the full salesforce-pipeline
compose stack (salesforce_mock + airflow + salesforce_bronze_writer) plus
foundation services to be running.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.integration


def test_salesforce_pipeline_end_to_end_placeholder() -> None:
    pytest.skip("integration harness wiring lands in a later phase")
