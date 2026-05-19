"""Silver curated listener DAG.

Consumes bronze-ready events and triggers one silver_curated_promotion DAG run per
matching Salesforce Opportunity event.
"""

from __future__ import annotations

import pendulum
from airflow import DAG
from airflow.providers.apache.kafka.sensors.kafka import AwaitMessageTriggerFunctionSensor

from curated_dag_helpers import (
    attach_trigger_metadata,
    build_trigger_event,
    parse_event_envelope,
    trigger_dag,
)
from curated_specs import resolve_silver_spec
from silver_curated.common import TOPICS_BRONZE_READY, default_args


def apply_bronze_event(message, **_):
    """
    Validate Kafka message and prepare TriggerDagRun payload.
    """
    envelope = parse_event_envelope(message)
    if envelope is None:
        return None

    if envelope.get("event_type") not in TOPICS_BRONZE_READY:
        return None

    payload = envelope.get("payload") or {}

    if payload.get("stage") != "bronze":
        return None

    silver_spec = resolve_silver_spec(envelope)

    if silver_spec is None:
        return None

    run_id = envelope.get("run_id")

    if not run_id:
        return None

    trigger_run_id = f"silver_curated_promotion__{run_id}"
    envelope = attach_trigger_metadata(envelope, message)

    envelope["_curated_silver_domain"] = silver_spec.domain
    envelope["_curated_silver_output_table"] = silver_spec.output_table
    envelope["_curated_silver_transform_id"] = silver_spec.transform_id

    return build_trigger_event(trigger_run_id=trigger_run_id, conf=envelope)


def trigger_promotion(event, **context):
    """
    Trigger silver_curated_promotion with the event conf.
    """
    trigger_dag(event, target_dag_id="silver_curated_promotion", context=context)


"""
Define the DAG that listens for bronze_ready events and triggers
silver_curated_promotion runs.
"""
with DAG(
    dag_id="silver_curated_listener",
    description="Long-running Kafka listener that triggers silver_curated_promotion.",
    default_args=default_args,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule="@continuous",
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["curated", "silver", "listener"],
):
    AwaitMessageTriggerFunctionSensor(
        task_id="await_bronze_ready",
        topics=list(TOPICS_BRONZE_READY),
        apply_function="silver_curated.listener.apply_bronze_event",
        kafka_config_id="kafka_default",
        event_triggered_function=trigger_promotion,
        poll_interval=5,
        poll_timeout=10,
    )
