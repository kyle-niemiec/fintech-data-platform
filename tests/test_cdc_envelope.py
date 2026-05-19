"""Verify CDC payload shapes match docs/event-contracts.md."""

from __future__ import annotations

from uuid import uuid4

from meridian.libs.redpanda_events.envelope import Envelope, EventSource, PipelineClass, PipelineName


def _build(event_type: str, payload: dict) -> Envelope:
    pipeline_name = (
        PipelineName.cdc_bronze_write
        if event_type == "cdc.oltp.bronze.ready.v1"
        else PipelineName.cdc_ingestion
    )
    return Envelope.build(
        event_type=event_type,
        source=EventSource.cdc,
        run_id=uuid4(),
        pipeline_class=PipelineClass.ingestion,
        pipeline_name=pipeline_name,
        trigger_event_ref="cdc.oltp.raw.v1:0:1",
        trace_id=uuid4(),
        payload=payload,
    )


def test_assessed_payload_required_fields() -> None:
    payload = {
        "risk_score": 0.9,
        "risk_flags": ["risk_threshold_exceeded"],
        "fraud_rule_version": "demo_continuous_risk",
        "loan_id": "loan-123",
        "payment_amount": 1250.25,
        "payment_due_date": "2026-05-01",
        "commission_adjustment_amount": 350.0,
        "status_code": "current",
        "original_topic_metadata": {
            "topic": "cdc.oltp.raw.v1",
            "partition": 0,
            "offset": 1,
            "lsn": "0/16B5C10",
            "source_ts_ms": 1700000000000,
        },
    }
    env = _build("cdc.oltp.assessed.v1", payload)
    for field in (
        "risk_score",
        "risk_flags",
        "fraud_rule_version",
        "loan_id",
        "payment_amount",
        "payment_due_date",
        "commission_adjustment_amount",
        "status_code",
        "original_topic_metadata",
    ):
        assert field in env.payload


def test_bronze_ready_payload_required_fields() -> None:
    payload = {
        "stage": "bronze",
        "format": "parquet",
        "input_uris": ["kafka://cdc.oltp.assessed.v1/0/1"],
        "output_uris": ["s3://fintech-lakehouse/bronze/source=cdc/..."],
        "record_count": 1,
        "first_lsn": "0/16B5C10",
        "last_lsn": "0/16B5C10",
        "source_table": "trading.transaction",
    }
    env = _build("cdc.oltp.bronze.ready.v1", payload)
    for field in ("stage", "input_uris", "output_uris", "record_count", "first_lsn", "last_lsn"):
        assert field in env.payload
