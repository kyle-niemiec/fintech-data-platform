"""
Shared helper utilities for curated DAG listeners and run lifecycle.
Contains functions for parsing and validating incoming Kafka messages, building
trigger events, triggering DAGs, and managing event store interactions for run
lifecycle events.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID, uuid4

from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator

from dag_runtime import open_event_store_conn

logger = logging.getLogger(__name__)


def parse_event_envelope(message) -> dict[str, Any] | None:  # noqa: ANN001
    """
    Parse the message value as JSON and validate that it's a dict (envelope). If
    the message value is not valid JSON or not a dict, return None to ignore.
    """
    try:
        envelope = json.loads(message.value())
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    return envelope if isinstance(envelope, dict) else None


def attach_trigger_metadata(envelope: dict[str, Any], message) -> dict[str, Any]:  # noqa: ANN001
    """
    Attach metadata from the Kafka message to the envelope, so it's available in
    the triggered DAG's conf.
    """
    envelope["_trigger_topic"] = message.topic()
    envelope["_trigger_partition"] = int(message.partition())
    envelope["_trigger_offset"] = int(message.offset())

    return envelope


def build_trigger_event(*, trigger_run_id: str, conf: dict[str, Any]) -> dict[str, Any]:
    """
    Build the event dict that will be used as the payload to trigger the DAG.
    """
    return {
        "trigger_run_id": trigger_run_id,
        "conf": conf,
    }


def trigger_dag(event: dict[str, Any], *, target_dag_id: str, context: dict[str, Any]) -> None:
    """
    Trigger the specified DAG with the given event.
    """
    trigger = TriggerDagRunOperator(
        task_id=f"trigger_{event['trigger_run_id']}",
        trigger_dag_id=target_dag_id,
        trigger_run_id=event["trigger_run_id"],
        conf=event["conf"],
        reset_dag_run=False,
        wait_for_completion=False,
    )

    trigger.execute(context)


def open_curated_run_and_append_started_event(
    *,
    run_id: UUID,
    parent_run_id: UUID,
    trace_id: UUID,
    trigger_event_ref: str,
    source_system: str,
    trigger_type: str,
    initiator: str,
    started_topic: str,
    started_payload: dict[str, Any],
) -> UUID:
    """
    Open a new run in the event store for a curated pipeline, and append a "started"
    event to the event store for that run.
    """
    from meridian.libs.redpanda_events.envelope import (
        Envelope,
        EventSource,
        PipelineClass,
        PipelineName,
    )
    from meridian.libs.event_store import PgEventStore

    with open_event_store_conn() as conn:
        with conn.begin():
            effective_run_id = PgEventStore.open_run(
                conn,
                run_id=run_id,
                pipeline_class=PipelineClass.curated,
                pipeline_name=PipelineName.curated_promotion,
                source_system=source_system,
                trigger_type=trigger_type,
                trigger_event_ref=trigger_event_ref,
                initiator=initiator,
                status="running",
                parent_run_id=parent_run_id,
            )

            started_envelope = Envelope.build(
                event_type=started_topic,
                source=EventSource.orchestration,
                run_id=effective_run_id,
                pipeline_class=PipelineClass.curated,
                pipeline_name=PipelineName.curated_promotion,
                parent_run_id=parent_run_id,
                trigger_event_ref=trigger_event_ref,
                trace_id=trace_id,
                payload=started_payload,
            )

            PgEventStore.append_event(
                conn,
                started_envelope,
                topic=started_topic,
                partition=-1,
                kafka_offset=-1,
            )

    return effective_run_id


def emit_curated_failure_event(
    *,
    run_id: UUID,
    parent_run_id: UUID | None,
    trace_id: UUID,
    trigger_event_ref: str,
    topic: str,
    payload: dict[str, Any],
    producer_builder,
) -> None:
    """
    Emit a failure event to the specified topic, and append it to the event store.
    """
    from meridian.libs.redpanda_events.envelope import (
        Envelope,
        EventSource,
        PipelineClass,
        PipelineName,
    )
    from meridian.libs.event_store import PgEventStore

    envelope = Envelope.build(
        event_type=topic,
        source=EventSource.orchestration,
        run_id=run_id,
        pipeline_class=PipelineClass.curated,
        pipeline_name=PipelineName.curated_promotion,
        parent_run_id=parent_run_id,
        trigger_event_ref=trigger_event_ref,
        trace_id=trace_id,
        payload=payload,
    )

    producer = producer_builder()

    try:
        partition, offset = producer.produce(topic, envelope, key=str(envelope.run_id))
    finally:
        producer.close()

    with open_event_store_conn() as conn:
        with conn.begin():
            PgEventStore.append_event(
                conn,
                envelope,
                topic=topic,
                partition=partition,
                kafka_offset=offset,
            )

            PgEventStore.close_run(conn, run_id, status="failed")


def safe_emit_curated_failure_event(**kwargs: Any) -> None:
    """
    Safely emit a curated failure event, catching and logging any exceptions to
    avoid interfering with Airflow's own failure handling.
    """
    try:
        emit_curated_failure_event(**kwargs)
    except Exception:
        logger.exception("failed to persist curated failure event")
