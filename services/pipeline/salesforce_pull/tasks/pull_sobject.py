from __future__ import annotations

import os
from datetime import timezone
from typing import Any
from uuid import uuid4

from airflow.exceptions import AirflowException
from dag_runtime import open_event_store_conn

from salesforce_pull.common import (
    INITIATOR,
    SOBJECT_FIELDS,
    SOURCE_SYSTEM,
    TOPIC_RAW_READY,
    TRIGGER_TYPE,
    _build_producer,
    _build_soql,
    _fetch_token,
    _latest_cursor,
    _pull_pages,
    _write_pages_to_minio,
)


def pull_sobject(sobject: str, context: dict[str, Any]) -> dict[str, Any]:
    """
    Pull incremental data for the specified Salesforce object, write it to MinIO, and emit an event.
    """
    import requests
    from meridian.libs.redpanda_events.envelope import (
        Envelope,
        EventSource,
        PipelineClass,
        PipelineName,
    )
    from meridian.libs.event_store import PgEventStore

    if sobject not in SOBJECT_FIELDS:
        raise AirflowException(f"unknown SObject: {sobject}")

    # Configure the trigger event reference using the DAG to ensure uniqueness.
    dag_run = context["dag_run"]
    logical_ts = dag_run.logical_date.isoformat() if dag_run.logical_date else dag_run.run_id
    trigger_event_ref = f"salesforce_incremental_pull__{logical_ts}__{sobject}"

    # Read configuration from environment variables
    base_url = os.environ["SALESFORCE_BASE_URL"]
    api_version = os.environ.get("SALESFORCE_API_VERSION", "v59.0")
    page_size = int(os.environ.get("SALESFORCE_PAGE_SIZE", "200"))
    bucket = os.environ["MINIO_BUCKET_NAME"]

    fields = SOBJECT_FIELDS[sobject]
    since_ts = _latest_cursor(sobject)

    session = requests.Session()

    # Fetch the Salesforce access token
    try:
        token = _fetch_token(session, base_url)
        soql = _build_soql(sobject, fields, since_ts, page_size)
        pages = _pull_pages(session, base_url, token, api_version, soql)
    finally:
        session.close()

    records_flat: list[dict[str, Any]] = []

    # Flatten the list of pages into a single list of records for easier processing downstream.
    for page in pages:
        records_flat.extend(page.get("records", []))

    if not records_flat:
        return {
            "sobject": sobject,
            "row_count": 0,
            "trigger_event_ref": trigger_event_ref,
        }

    # Generate a unique run ID and trace ID for this pull operation, write the data to MinIO, and emit an event.
    run_id = uuid4()
    trace_id = uuid4()
    output_uris = _write_pages_to_minio(bucket, sobject, str(run_id), pages)

    last = records_flat[-1]
    proposed_cursor_ts = last["SystemModstamp"]
    proposed_cursor_id = last["Id"]

    payload: dict[str, Any] = {
        "message": f"Salesforce incremental pull landed {len(records_flat)} {sobject} rows to raw.",
        "stage": "raw",
        "sobject": sobject,
        "since_cursor_ts": since_ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if since_ts else None,
        "proposed_cursor_ts": proposed_cursor_ts,
        "proposed_cursor_id": proposed_cursor_id,
        "row_count": len(records_flat),
        "page_count": len(pages),
        "fields": list(fields),
        "api_version": api_version,
        "input_uris": [f"{base_url.rstrip('/')}/services/data/{api_version}/query"],
        "output_uris": output_uris,
        "transform_id": "salesforce_incremental_pull",
        "transform_version": "v1",
    }

    envelope = Envelope.build(
        event_type=TOPIC_RAW_READY,
        source=EventSource.salesforce,
        run_id=run_id,
        pipeline_class=PipelineClass.ingestion,
        pipeline_name=PipelineName.salesforce_ingestion,
        trigger_event_ref=trigger_event_ref,
        trace_id=trace_id,
        payload=payload,
    )

    producer = _build_producer()

    # Emit the event to Redpanda and capture the partition and offset for recording in the event store.
    try:
        partition, offset = producer.produce(TOPIC_RAW_READY, envelope, key=f"{sobject}:{run_id}")
    finally:
        producer.close()

    # Persist the event to the event store within the context of the run
    with open_event_store_conn() as conn:
        with conn.begin():
            effective_run_id = PgEventStore.open_run(
                conn,
                run_id=run_id,
                pipeline_class=PipelineClass.ingestion,
                pipeline_name=PipelineName.salesforce_ingestion,
                source_system=SOURCE_SYSTEM,
                trigger_type=TRIGGER_TYPE,
                trigger_event_ref=trigger_event_ref,
                initiator=INITIATOR,
            )

            PgEventStore.append_event(
                conn,
                envelope,
                topic=TOPIC_RAW_READY,
                partition=partition,
                kafka_offset=offset,
            )

    # Return metadata about the pull operation for use in downstream tasks.
    return {
        "sobject": sobject,
        "row_count": len(records_flat),
        "run_id": str(effective_run_id),
        "trigger_event_ref": trigger_event_ref,
        "output_uris": output_uris,
        "proposed_cursor_ts": proposed_cursor_ts,
        "proposed_cursor_id": proposed_cursor_id,
    }
