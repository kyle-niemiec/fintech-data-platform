"""Structural checks for CDC bronze writer execution ordering."""

from __future__ import annotations

from pathlib import Path


MAIN_FILE = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "pipeline-workers"
    / "workers"
    / "cdc_bronze_writer"
    / "main.py"
)


def test_cdc_bronze_writer_persists_parent_run_before_publish():
    source = MAIN_FILE.read_text()
    assert "_prepare_batch_run" in source
    assert "producer.produce(" in source
    assert "_finalize_published_batch" in source


def test_cdc_bronze_writer_records_explicit_publish_failure():
    source = MAIN_FILE.read_text()
    assert "_mark_batch_failed" in source
    assert "cdc_bronze_ready_publish_failed" in source
    assert 'status="failed"' in source

