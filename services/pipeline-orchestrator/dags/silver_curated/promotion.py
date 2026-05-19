"""
Silver curated promotion DAG.

Processes one bronze event and promotes Opportunity data into
lakehouse.silver.dim_opportunity.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

import pendulum
from airflow import DAG
from airflow.decorators import task
from curated_dag_helpers import safe_emit_curated_failure_event

from silver_curated.common import (
    TOPIC_SILVER_FAILED,
    default_args,
    _build_producer,
)
from silver_curated.tasks.merge_into_silver import merge_into_silver as merge_into_silver_task
from silver_curated.tasks.open_curated_run import open_curated_run as open_curated_run_task
from silver_curated.tasks.record_checkpoint_and_emit_event import (
    record_checkpoint_and_emit_event as record_checkpoint_and_emit_event_task,
)
from silver_curated.tasks.stage_and_mask_bronze import (
    stage_and_mask_bronze as stage_and_mask_bronze_task,
)

logger = logging.getLogger(__name__)


def _emit_failure_event(context):
    """
    DAG-level failure callback: emit pipeline.silver.failed.v1 + close run.
    """
    dag_run = context["dag_run"]
    conf = dag_run.conf or {}
    parent_run_id = conf.get("run_id")
    trace_id = conf.get("trace_id")
    bronze_trigger_ref = conf.get("trigger_event_ref") or dag_run.run_id

    curated_run_id = (dag_run.conf or {}).get("_curated_run_id") or str(uuid4())

    payload = {
        "message": "Silver curated promotion failed",
        "stage": "silver",
        "silver_domain": conf.get("_curated_silver_domain") or "unknown",
        "output_table": conf.get("_curated_silver_output_table") or "unknown",
        "parent_run_id": parent_run_id,
        "record_count": 0,
        "input_uris": (conf.get("payload") or {}).get("output_uris", []),
        "output_uris": [],
        "transform_id": conf.get("_curated_silver_transform_id") or "silver_curated_promotion",
        "transform_version": "v1",
    }

    safe_emit_curated_failure_event(
        run_id=UUID(curated_run_id),
        parent_run_id=UUID(parent_run_id) if parent_run_id else None,
        trace_id=UUID(trace_id) if trace_id else uuid4(),
        trigger_event_ref=bronze_trigger_ref,
        topic=TOPIC_SILVER_FAILED,
        payload=payload,
        producer_builder=_build_producer,
    )


with DAG(
    dag_id="silver_curated_promotion",
    description="Promote one Salesforce Opportunity bronze batch to silver.dim_opportunity (SCD2).",
    default_args=default_args,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=4,
    is_paused_upon_creation=False,
    on_failure_callback=_emit_failure_event,
    tags=["curated", "silver"],
) as promotion_dag:

    @task(task_id="open_curated_run")
    def open_curated_run(**context) -> dict[str, Any]:
        return open_curated_run_task(context)

    @task(task_id="stage_and_mask_bronze")
    def stage_and_mask_bronze(state: dict[str, Any]) -> dict[str, Any]:
        return stage_and_mask_bronze_task(state)

    @task(task_id="merge_into_silver")
    def merge_into_silver(state: dict[str, Any]) -> dict[str, Any]:
        return merge_into_silver_task(state)

    @task(task_id="record_checkpoint_and_emit_event")
    def record_checkpoint_and_emit_event(state: dict[str, Any]) -> None:
        record_checkpoint_and_emit_event_task(state)

    state = open_curated_run()
    staged = stage_and_mask_bronze(state)
    merged = merge_into_silver(staged)
    record_checkpoint_and_emit_event(merged)
