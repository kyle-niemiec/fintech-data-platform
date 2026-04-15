"""End-to-end CDC pipeline integration test (skipped by default).

Enable with `pytest -m integration`. Requires the full cdc-pipeline compose
stack to be running.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.integration


def test_cdc_pipeline_end_to_end_placeholder() -> None:
    pytest.skip("integration harness wiring lands in a later phase")
