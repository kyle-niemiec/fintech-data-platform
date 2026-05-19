from __future__ import annotations

import os
from uuid import UUID

from dag_runtime import open_event_store_conn
from gold_curated.common import TOPIC_GOLD_COMPLETED, _build_producer


def record_checkpoint_and_emit_event(state: dict[str, str]) -> None:
    """
    The record_checkpoint_and_emit_event task performs two critical functions at the end of the gold curated aggregation pipeline:
    1. It records a checkpoint in the event store to mark the completion of the gold aggregation.
    2. It emits a "gold completed" event to notify downstream consumers of the completed aggregation.
    """
    from libs.platform_events.envelope import (
        Envelope,
        EventSource,
        PipelineClass,
        PipelineName,
    )
    from libs.platform_events.event_store import PgEventStore

    # Extract necessary information from the state to construct the event and checkpoint
    curated_run_id = UUID(state["curated_run_id"])
    parent_run_id = UUID(state["parent_run_id"])
    trace_id = UUID(state["trace_id"])
    metric = state["gold_metric"]
    output_table = state["gold_table"]
    transform_id = state.get("gold_transform_id") or "gold_curated_aggregation"
    record_count = int(state.get("record_count") or 0)
    output_uris = [f"s3://{os.environ['MINIO_BUCKET_NAME']}/gold/metric={metric}/"]
    input_uris = [state["silver_table"]] if state.get("silver_table") else []

    payload = {
        "message": f"Computed {metric} KPI with {record_count} rows.",
        "stage": "gold",
        "metric": metric,
        "output_table": output_table,
        "parent_run_id": str(parent_run_id),
        "record_count": record_count,
        "snapshot_date": state["snapshot_date"],
        "computed_at": state["computed_at"],
        "silver_domain": state.get("silver_domain"),
        "input_uris": input_uris,
        "output_uris": output_uris,
        "transform_id": transform_id,
        "transform_version": "v1",
    }

    envelope = Envelope.build(
        event_type=TOPIC_GOLD_COMPLETED,
        source=EventSource.orchestration,
        run_id=curated_run_id,
        pipeline_class=PipelineClass.curated,
        pipeline_name=PipelineName.curated_promotion,
        parent_run_id=parent_run_id,
        trigger_event_ref=state["trigger_event_ref"],
        trace_id=trace_id,
        payload=payload,
    )

    producer = _build_producer()

    # Emit the "gold completed" event to the Kafka topic
    try:
        partition, offset = producer.produce(
            TOPIC_GOLD_COMPLETED, envelope, key=str(curated_run_id)
        )
    finally:
        producer.close()

    # Record the checkpoint in the event store and append the "gold completed" event to the event store.
    with open_event_store_conn() as conn:
        with conn.transaction():
            # Append the checkpoint for the gold run
            PgEventStore.append_gold_checkpoint(
                conn,
                run_id=curated_run_id,
                parent_run_id=parent_run_id,
                metric=metric,
                input_uris=input_uris,
                output_table=output_table,
                output_uris=output_uris,
                record_count=record_count,
            )

            # Append the "gold completed" event
            PgEventStore.append_event(
                conn,
                envelope,
                topic=TOPIC_GOLD_COMPLETED,
                partition=partition,
                kafka_offset=offset,
            )

            # Close the run in the event store
            PgEventStore.close_run(conn, curated_run_id, status="completed")
