from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from airflow.exceptions import AirflowException
from curated_dag_helpers import open_curated_run_and_append_started_event

from curated_specs import resolve_silver_spec
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

    silver_spec = resolve_silver_spec(bronze_envelope)
    if silver_spec is None:
        raise AirflowException("bronze envelope did not resolve to a supported silver domain")

    # Create an event reference for this silver run
    trace_id = bronze_envelope.get("trace_id") or str(uuid4())
    trigger_event_ref = f"silver_curated_promotion__{parent_run_id}"

    curated_run_id = uuid4()
    trace_uuid = UUID(trace_id)

    effective_run_id = open_curated_run_and_append_started_event(
        run_id=curated_run_id,
        parent_run_id=UUID(parent_run_id),
        trace_id=trace_uuid,
        trigger_event_ref=trigger_event_ref,
        source_system=SOURCE_SYSTEM,
        trigger_type=TRIGGER_TYPE,
        initiator=INITIATOR,
        started_topic=TOPIC_SILVER_STARTED,
        started_payload={
            "message": "Silver curated promotion started.",
            "stage": "silver",
            "silver_domain": silver_spec.domain,
            "output_table": silver_spec.output_table,
            "parent_run_id": parent_run_id,
            "input_uris": bronze_uris,
            "transform_id": silver_spec.transform_id,
            "transform_version": "v1",
        },
    )

    # Return the relevant metadata about the opened run and the bronze input for downstream tasks
    return {
        "curated_run_id": str(effective_run_id),
        "parent_run_id": parent_run_id,
        "trace_id": trace_id,
        "trigger_event_ref": trigger_event_ref,
        "bronze_uris": bronze_uris,
        "bronze_record_count": int(bronze_payload.get("record_count") or 0),
        "silver_domain": silver_spec.domain,
        "silver_table": silver_spec.output_table,
        "silver_transform_id": silver_spec.transform_id,
        "bronze_envelope": bronze_envelope,
    }
