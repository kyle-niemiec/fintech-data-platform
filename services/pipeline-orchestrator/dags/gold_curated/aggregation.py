"""Gold curated aggregation DAG."""

from __future__ import annotations

import logging
import pendulum
from typing import Any
from uuid import UUID, uuid4
from airflow import DAG
from airflow.decorators import task
from dag_runtime import open_event_store_conn
from gold_curated.common import (
    TOPIC_GOLD_FAILED,
    default_args,
    _build_producer,
)
from gold_curated.tasks.open_curated_run import open_curated_run as open_curated_run_task
from gold_curated.tasks.record_checkpoint_and_emit_event import (
    record_checkpoint_and_emit_event as record_checkpoint_and_emit_event_task,
)
from gold_curated.tasks.run_aggregation_sql import run_aggregation_sql as run_aggregation_sql_task

logger = logging.getLogger(__name__)


def _emit_failure_event(context):
    """
    This function is an Airflow failure callback that emits a "gold.failed" event to the event store.
    """
    from libs.platform_events.envelope import (
        Envelope,
        EventSource,
        PipelineClass,
        PipelineName,
    )
    from libs.platform_events.event_store import append_event, close_run

    # Extract relevant information from the DAG run context to include in the failure event payload and metadata.
    dag_run = context["dag_run"]
    conf = dag_run.conf or {}
    parent_run_id = conf.get("run_id")
    trace_id = conf.get("trace_id")
    silver_trigger_ref = conf.get("trigger_event_ref") or dag_run.run_id
    curated_run_id = (dag_run.conf or {}).get("_curated_run_id") or str(uuid4())

    payload = {
        "message": "Gold curated aggregation failed",
        "stage": "gold",
        "metric": conf.get("payload", {}).get("metric") if isinstance(conf.get("payload"), dict) else "unknown",
        "output_table": conf.get("payload", {}).get("output_table") if isinstance(conf.get("payload"), dict) else "unknown",
        "parent_run_id": parent_run_id,
        "record_count": 0,
        "input_uris": [(conf.get("payload") or {}).get("output_table") or ""],
        "output_uris": [],
        "transform_id": "gold_curated_aggregation",
        "transform_version": "v1",
    }

    try:
        envelope = Envelope.build(
            event_type=TOPIC_GOLD_FAILED,
            source=EventSource.orchestration,
            run_id=UUID(curated_run_id),
            pipeline_class=PipelineClass.curated,
            pipeline_name=PipelineName.curated_promotion,
            parent_run_id=UUID(parent_run_id) if parent_run_id else None,
            trigger_event_ref=silver_trigger_ref,
            trace_id=UUID(trace_id) if trace_id else uuid4(),
            payload=payload,
        )
    except Exception:
        logger.exception("failed to build gold.failed envelope")
        return

    producer = _build_producer()

    # Emit the "gold.failed" event to Redpanda and capture the partition and offset
    try:
        partition, offset = producer.produce(
            TOPIC_GOLD_FAILED, envelope, key=str(envelope.run_id)
        )
    finally:
        producer.close()

    # Persist the "gold.failed" event and close the event store run with a "failed" status
    try:
        with open_event_store_conn() as conn:
            with conn.transaction():
                append_event(
                    conn,
                    envelope,
                    topic=TOPIC_GOLD_FAILED,
                    partition=partition,
                    kafka_offset=offset,
                )

                close_run(conn, UUID(curated_run_id), status="failed")
    except Exception:
        logger.exception("failed to persist gold.failed event/close run")


"""
Define the Airflow DAG for the gold curated aggregation pipeline, which consists
of three main tasks:

1. open_curated_run: Opens a new run in the event store for the gold curated
   aggregation pipeline and emits a "gold.started" event.
2. run_aggregation_sql: Executes the appropriate aggregation SQL based on the
   specified gold metric and records metadata about the run.
3. record_checkpoint_and_emit_event: Records a checkpoint in the event store and
   emits a "gold.completed" event with the final metadata about the run.
"""
with DAG(
    dag_id="gold_curated_aggregation",
    description="Compute pipeline_conversion KPI from silver.dim_opportunity.",
    default_args=default_args,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=4,
    is_paused_upon_creation=False,
    on_failure_callback=_emit_failure_event,
    tags=["curated", "gold"],
) as aggregation_dag:

    @task(task_id="open_curated_run")
    def open_curated_run(**context) -> dict[str, Any]:
        return open_curated_run_task(context)

    @task(task_id="run_aggregation_sql")
    def run_aggregation_sql(state: dict[str, Any]) -> dict[str, Any]:
        return run_aggregation_sql_task(state)

    @task(task_id="record_checkpoint_and_emit_event")
    def record_checkpoint_and_emit_event(state: dict[str, Any]) -> None:
        record_checkpoint_and_emit_event_task(state)

    state = open_curated_run()
    computed = run_aggregation_sql(state)
    record_checkpoint_and_emit_event(computed)
