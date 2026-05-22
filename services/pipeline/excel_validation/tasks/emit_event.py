from __future__ import annotations

from typing import Any
from uuid import UUID

from airflow.exceptions import AirflowException
from dag_runtime import open_event_store_conn

from excel_validation.common import (
    TOPIC_QUARANTINED,
    TOPIC_RAW_READY,
    TRANSFORM_ID,
    TRANSFORM_VERSION,
    _build_producer,
)


def emit_event(*branch_outputs: dict[str, Any]) -> None:
    """
    Emit an event to Redpanda based on the outcome of the validation and append it.
    """
    from meridian.libs.redpanda_events.envelope import (
        Envelope,
        EventSource,
        PipelineClass,
        PipelineName,
    )
    from meridian.libs.event_store import PgEventStore

    # Check that the outcome is present
    outcome = next((output for output in branch_outputs if output), None)

    if outcome is None:
        raise AirflowException("emit_event received no branch output")

    # Determine the topic based on the validation outcome and build the event payload
    stage = outcome["stage"]
    is_raw = stage == "raw"
    topic = TOPIC_RAW_READY if is_raw else TOPIC_QUARANTINED

    payload: dict[str, Any] = {
        "message": (
            f"Excel upload accepted and landed to raw: {outcome['output_key']}"
            if is_raw
            else f"Excel upload failed schema validation: {outcome['output_key']}"
        ),
        "stage": stage,
        "input_uris": [f"s3://{outcome['bucket']}/{outcome['object_key']}"],
        "output_uris": [f"s3://{outcome['bucket']}/{outcome['output_key']}"],
        "row_count": outcome["row_count"],
        "transform_id": TRANSFORM_ID,
        "transform_version": TRANSFORM_VERSION,
    }

    if is_raw:
        payload["schema_contract_id"] = outcome["contract_id"]
    else:
        payload["errors"] = outcome["errors"]

    envelope = Envelope.build(
        event_type=topic,
        source=EventSource.excel,
        run_id=UUID(outcome["run_id"]),
        pipeline_class=PipelineClass.ingestion,
        pipeline_name=PipelineName.excel_ingestion,
        trigger_event_ref=outcome["trigger_event_ref"],
        trace_id=UUID(outcome["trace_id"]),
        payload=payload,
    )

    producer = _build_producer()

    # Emit the event to Redpanda and capture the partition and offset for event store persistence
    try:
        partition, offset = producer.produce(topic, envelope, key=outcome["run_id"])
    finally:
        producer.close()

    # Persist the emitted event to the event store; for quarantine, also close
    # the run and raise an alert. For the raw-ready path the run stays open —
    # the bronze writer closes it as "completed" after writing the Parquet.
    # Calling close_run here on the success path created a race condition where
    # a fast bronze writer would commit "completed" before this transaction,
    # which would then overwrite it with the intermediate "running" state.
    with open_event_store_conn() as conn:
        with conn.begin():
            PgEventStore.append_event(
                conn,
                envelope,
                topic=topic,
                partition=partition,
                kafka_offset=offset,
            )

            # Handle quarantine-specific event store updates and alerting.
            if not is_raw:
                # Close the run since it will not proceed to bronze.
                PgEventStore.close_run(
                    conn,
                    UUID(outcome["run_id"]),
                    status="quarantined",
                )

                # Raise an alert for the quarantine event.
                PgEventStore.raise_alert(
                    conn,
                    run_id=UUID(outcome["run_id"]),
                    severity="medium",
                    category="excel_schema_quarantined",
                    summary=f"Excel upload quarantined: schema validation failed ({outcome['output_key']})",
                    details={
                        "object_key": outcome["object_key"],
                        "output_key": outcome["output_key"],
                        "errors": outcome["errors"],
                    },
                )
