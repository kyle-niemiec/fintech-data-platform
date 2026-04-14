"""Envelope construction, hashing, and validation rules."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from libs.platform_events.envelope import (
    Envelope,
    EventSource,
    PipelineClass,
    PipelineName,
    SCHEMA_VERSION,
    canonical_payload_hash,
)


def _sample_payload() -> dict:
    return {
        "bucket": "fintech-lakehouse",
        "object_key": "landing/source=excel/year=2026/month=04/day=13/run_id=abc/payroll.xlsx",
        "uploader_principal": "finance-user-1",
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "size_bytes": 8421,
    }


def test_canonical_hash_is_order_independent():
    a = {"z": 1, "a": {"b": 2, "a": 3}}
    b = {"a": {"a": 3, "b": 2}, "z": 1}
    assert canonical_payload_hash(a) == canonical_payload_hash(b)


def test_canonical_hash_changes_when_payload_changes():
    base = _sample_payload()
    mutated = {**base, "size_bytes": base["size_bytes"] + 1}
    assert canonical_payload_hash(base) != canonical_payload_hash(mutated)


def test_canonical_hash_format():
    digest = canonical_payload_hash(_sample_payload())
    assert digest.startswith("sha256-")
    assert len(digest) == len("sha256-") + 64


def test_build_populates_required_fields():
    run_id = uuid4()
    trace_id = uuid4()
    env = Envelope.build(
        event_type="ingest.excel.uploaded.v1",
        source=EventSource.excel,
        run_id=run_id,
        pipeline_class=PipelineClass.ingestion,
        pipeline_name=PipelineName.excel_ingestion,
        trigger_event_ref="minio:fintech-lakehouse:landing/source=excel/...xlsx:etag-1",
        trace_id=trace_id,
        payload=_sample_payload(),
    )
    assert env.event_type == "ingest.excel.uploaded.v1"
    assert env.source == EventSource.excel.value
    assert env.run_id == run_id
    assert env.schema_version == SCHEMA_VERSION
    assert env.payload_hash == canonical_payload_hash(_sample_payload())
    assert env.occurred_at.tzinfo is not None


def test_wire_roundtrip_preserves_payload_and_hash():
    env = Envelope.build(
        event_type="ingest.excel.uploaded.v1",
        source=EventSource.excel,
        run_id=uuid4(),
        pipeline_class=PipelineClass.ingestion,
        pipeline_name=PipelineName.excel_ingestion,
        trigger_event_ref="ref-1",
        trace_id=uuid4(),
        payload=_sample_payload(),
    )
    wire = env.to_wire()
    reconstructed = Envelope.model_validate_json(wire)
    assert reconstructed.payload == env.payload
    assert reconstructed.payload_hash == env.payload_hash
    assert canonical_payload_hash(reconstructed.payload) == reconstructed.payload_hash


def test_occurred_at_requires_timezone():
    naive = datetime(2026, 4, 13, 12, 0, 0)
    with pytest.raises(ValidationError):
        Envelope(
            event_type="x",
            source=EventSource.excel,
            run_id=uuid4(),
            pipeline_class=PipelineClass.ingestion,
            pipeline_name=PipelineName.excel_ingestion,
            trigger_event_ref="ref",
            trace_id=uuid4(),
            occurred_at=naive,
            payload_hash=canonical_payload_hash({}),
            payload={},
        )


def test_trigger_event_ref_cannot_be_blank():
    with pytest.raises(ValidationError):
        Envelope.build(
            event_type="x",
            source=EventSource.excel,
            run_id=uuid4(),
            pipeline_class=PipelineClass.ingestion,
            pipeline_name=PipelineName.excel_ingestion,
            trigger_event_ref="   ",
            trace_id=uuid4(),
            payload={},
        )


def test_payload_hash_format_validated():
    with pytest.raises(ValidationError):
        Envelope(
            event_type="x",
            source=EventSource.excel,
            run_id=uuid4(),
            pipeline_class=PipelineClass.ingestion,
            pipeline_name=PipelineName.excel_ingestion,
            trigger_event_ref="ref",
            trace_id=uuid4(),
            occurred_at=datetime.now(timezone.utc),
            payload_hash="notahash",
            payload={},
        )


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        Envelope(
            event_type="x",
            source=EventSource.excel,
            run_id=uuid4(),
            pipeline_class=PipelineClass.ingestion,
            pipeline_name=PipelineName.excel_ingestion,
            trigger_event_ref="ref",
            trace_id=uuid4(),
            occurred_at=datetime.now(timezone.utc),
            payload_hash=canonical_payload_hash({}),
            payload={},
            surprise="field",
        )


def test_wire_includes_all_envelope_keys():
    env = Envelope.build(
        event_type="x",
        source=EventSource.excel,
        run_id=uuid4(),
        pipeline_class=PipelineClass.ingestion,
        pipeline_name=PipelineName.excel_ingestion,
        trigger_event_ref="ref",
        trace_id=uuid4(),
        payload={},
    )
    parsed = json.loads(env.to_wire())
    expected_keys = {
        "event_id",
        "event_type",
        "source",
        "run_id",
        "pipeline_class",
        "pipeline_name",
        "parent_run_id",
        "trigger_event_ref",
        "trace_id",
        "occurred_at",
        "schema_version",
        "payload_hash",
        "payload",
    }
    assert expected_keys.issubset(parsed.keys())
