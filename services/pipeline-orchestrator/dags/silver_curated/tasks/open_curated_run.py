from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from airflow.exceptions import AirflowException
from dag_runtime import open_event_store_conn

from silver_curated.common import (
    INITIATOR,
    SOURCE_SYSTEM,
    TOPIC_SILVER_STARTED,
    TRIGGER_TYPE,
)


def open_curated_run(context: dict[str, Any]) -> dict[str, Any]:
    """
    This task initializes a new run for the silver curated promotion pipeline.
    It expects to receive a "bronze envelope" in the DAG run configuration,
    which contains metadata about the completed bronze pipeline run that triggered
    this silver run.
    """
    from libs.platform_events.envelope import (
        Envelope,
        EventSource,
        PipelineClass,
        PipelineName,
    )
    from libs.platform_events.event_store import append_event, open_run

    # Extract the bronze envelope from the DAG run configuration
    dag_run = context["dag_run"]
    bronze_envelope = dag_run.conf or {}

    if not bronze_envelope:
        raise AirflowException("silver_curated_promotion triggered without a bronze envelope in conf")

    parent_run_id = bronze_envelope.get("run_id")

    if not parent_run_id:
        raise AirflowException("bronze envelope missing run_id")

    bronze_payload = bronze_envelope.get("payload") or {}
    bronze_uris = bronze_payload.get("output_uris") or []

    if not bronze_uris:
        raise AirflowException("bronze envelope payload missing output_uris")

    # Create an event reference for this silver run
    trace_id = bronze_envelope.get("trace_id") or str(uuid4())
    trigger_event_ref = f"silver_curated_promotion__{parent_run_id}"

    curated_run_id = uuid4()
    trace_uuid = UUID(trace_id)

    # Open a connection to the event store and create a new run for the silver curated promotion pipeline.
    with open_event_store_conn() as conn:
        with conn.transaction():
            # Open the event store run for the silver curated promotion pipeline
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

            # Create the envelope for the silver curated promotion pipeline
            started_envelope = Envelope.build(
                event_type=TOPIC_SILVER_STARTED,
                source=EventSource.orchestration,
                run_id=effective_run_id,
                pipeline_class=PipelineClass.curated,
                pipeline_name=PipelineName.curated_promotion,
                parent_run_id=UUID(parent_run_id),
                trigger_event_ref=trigger_event_ref,
                trace_id=trace_uuid,
                payload={
                    "message": "Silver curated promotion started.",
                    "stage": "silver",
                    "parent_run_id": parent_run_id,
                    "input_uris": bronze_uris,
                    "transform_id": "silver_curated_promotion",
                    "transform_version": "v1",
                },
            )

            # Append the "silver started" event to the event store
            append_event(
                conn,
                started_envelope,
                topic=TOPIC_SILVER_STARTED,
                partition=-1,
                kafka_offset=-1,
            )

    # Return the relevant metadata about the opened run and the bronze input for downstream tasks
    return {
        "curated_run_id": str(effective_run_id),
        "parent_run_id": parent_run_id,
        "trace_id": trace_id,
        "trigger_event_ref": trigger_event_ref,
        "bronze_uris": bronze_uris,
        "bronze_record_count": int(bronze_payload.get("record_count") or 0),
    }
