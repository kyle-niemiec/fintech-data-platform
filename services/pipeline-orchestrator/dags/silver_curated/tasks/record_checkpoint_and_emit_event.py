from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from dag_runtime import open_event_store_conn
from silver_curated.common import TOPIC_SILVER_COMPLETED, _build_producer


def record_checkpoint_and_emit_event(state: dict[str, Any]) -> None:
    """
    The record_checkpoint_and_emit_event task performs two critical functions at the end of the silver curated promotion pipeline:
    1. It records a checkpoint in the event store to mark the completion of the silver promotion.
    2. It emits a "silver completed" event to notify downstream consumers of the completed promotion.
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
    merge_stats = state.get("merge_stats") or {}
    silver_domain = state["silver_domain"]
    silver_table = state["silver_table"]
    transform_id = state.get("silver_transform_id") or "silver_curated_promotion"
    record_count = int(state.get("staged_row_count") or 0)
    output_uris = [f"s3://{os.environ['MINIO_BUCKET_NAME']}/silver/domain={silver_domain}/"]

    payload = {
        "message": f"Promoted {record_count} rows to silver domain {silver_domain}.",
        "stage": "silver",
        "silver_domain": silver_domain,
        "output_table": silver_table,
        "parent_run_id": str(parent_run_id),
        "record_count": record_count,
        "merge_inserted": int(merge_stats.get("inserted") or 0),
        "merge_updated": int(merge_stats.get("updated") or 0),
        "merge_closed": int(merge_stats.get("closed") or 0),
        "input_uris": state.get("bronze_uris", []),
        "output_uris": output_uris,
        "transform_id": transform_id,
        "transform_version": "v1",
    }

    envelope = Envelope.build(
        event_type=TOPIC_SILVER_COMPLETED,
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

    # Emit the "silver completed" event to notify downstream consumers, and capture the partition and offset for recording in the event store
    try:
        partition, offset = producer.produce(
            TOPIC_SILVER_COMPLETED, envelope, key=str(curated_run_id)
        )
    finally:
        producer.close()

    # Persist the checkpoint and emitted event in the event store within a transaction
    with open_event_store_conn() as conn:
        with conn.transaction():
            # Append the silver checkpoint to the event store with details about the completed promotion.
            PgEventStore.append_silver_checkpoint(
                conn,
                run_id=curated_run_id,
                parent_run_id=parent_run_id,
                silver_domain=silver_domain,
                input_uris=list(state.get("bronze_uris", [])),
                output_table=silver_table,
                output_uris=output_uris,
                record_count=record_count,
                merge_inserted=int(merge_stats.get("inserted") or 0),
                merge_updated=int(merge_stats.get("updated") or 0),
                merge_closed=int(merge_stats.get("closed") or 0),
            )

            # Append the "silver completed" event to the event store with the partition and offset from Kafka.
            PgEventStore.append_event(
                conn,
                envelope,
                topic=TOPIC_SILVER_COMPLETED,
                partition=partition,
                kafka_offset=offset,
            )

            # Close the event store run for the silver curated promotion pipeline.
            PgEventStore.close_run(conn, curated_run_id, status="completed")
