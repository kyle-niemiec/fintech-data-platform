from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from airflow.exceptions import AirflowException
from dag_runtime import open_event_store_conn

from curated_specs import resolve_gold_metric
from gold_curated.common import (
    INITIATOR,
    SOURCE_SYSTEM,
    TOPIC_GOLD_STARTED,
    TRIGGER_TYPE,
)


def open_curated_run(context: dict[str, Any]) -> dict[str, Any]:
    """
    This task initializes a new run for the gold curated aggregation pipeline.
    It expects to receive a "silver envelope" in the DAG run configuration,
    which contains metadata about the completed silver pipeline run that triggered
    this gold run.
    """
    from libs.platform_events.envelope import (
        Envelope,
        EventSource,
        PipelineClass,
        PipelineName,
    )
    from libs.platform_events.event_store import append_event, open_run

    # Extract the silver envelope from the DAG run configuration
    dag_run = context["dag_run"]
    silver_envelope = dag_run.conf or {}

    if not silver_envelope:
        raise AirflowException("gold_curated_aggregation triggered without a silver envelope in conf")

    parent_run_id = silver_envelope.get("run_id")

    if not parent_run_id:
        raise AirflowException("silver envelope missing run_id")

    silver_payload = silver_envelope.get("payload") or {}
    silver_domain = str(silver_payload.get("silver_domain") or "")
    metric_spec = resolve_gold_metric(silver_domain)

    if metric_spec is None:
        raise AirflowException(f"no gold metric mapping for silver domain {silver_domain!r}")

    # Create an event reference for this gold run
    trace_id = silver_envelope.get("trace_id") or str(uuid4())
    trigger_event_ref = f"gold_curated_aggregation__{parent_run_id}"

    curated_run_id = uuid4()
    trace_uuid = UUID(trace_id)

    # Open a connection to the event store and create a new run for the gold curated aggregation pipeline.
    with open_event_store_conn() as conn:
        with conn.transaction():
            # Open the event store run for the gold curated aggregation pipeline
            effective_run_id = open_run(
                conn,
                run_id=curated_run_id,
                pipeline_class=PipelineClass.curated,
                pipeline_name=PipelineName.curated_promotion,
                source_system=SOURCE_SYSTEM,
                trigger_type=TRIGGER_TYPE,
                trigger_event_ref=trigger_event_ref,
                initiator=INITIATOR,
                status="running",
                parent_run_id=UUID(parent_run_id),
            )

            # Create the envelope for the gold curated aggregation pipeline
            started_envelope = Envelope.build(
                event_type=TOPIC_GOLD_STARTED,
                source=EventSource.orchestration,
                run_id=effective_run_id,
                pipeline_class=PipelineClass.curated,
                pipeline_name=PipelineName.curated_promotion,
                parent_run_id=UUID(parent_run_id),
                trigger_event_ref=trigger_event_ref,
                trace_id=trace_uuid,
                payload={
                    "message": "Gold curated aggregation started.",
                    "stage": "gold",
                    "metric": metric_spec.metric,
                    "silver_domain": silver_domain,
                    "parent_run_id": parent_run_id,
                    "input_table": (silver_envelope.get("payload") or {}).get("output_table"),
                    "transform_id": metric_spec.transform_id,
                    "transform_version": "v1",
                },
            )

            # Append the "gold started" event to the event store
            append_event(
                conn,
                started_envelope,
                topic=TOPIC_GOLD_STARTED,
                partition=-1,
                kafka_offset=-1,
            )

    # Extract the output table name from the silver envelope to pass to downstream tasks
    return {
        "curated_run_id": str(effective_run_id),
        "parent_run_id": parent_run_id,
        "trace_id": trace_id,
        "trigger_event_ref": trigger_event_ref,
        "silver_domain": silver_domain,
        "silver_table": silver_payload.get("output_table"),
        "gold_metric": metric_spec.metric,
        "gold_table": metric_spec.output_table,
        "gold_transform_id": metric_spec.transform_id,
    }
