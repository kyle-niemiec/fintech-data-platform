"""Gold curated listener DAG."""

from __future__ import annotations

import json

import pendulum
from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.apache.kafka.sensors.kafka import AwaitMessageTriggerFunctionSensor

from curated_specs import resolve_gold_metric
from gold_curated.common import default_args
from silver_curated.common import TOPIC_SILVER_COMPLETED


def apply_silver_event(message, **_):
    """
    This function is applied to messages received from the RedPanda topic that
    signals the completion of silver pipeline runs. It inspects the message
    to determine if it corresponds to a completed silver run that should trigger
    a gold curated aggregation run. If so, it extracts the necessary metadata
    from the message and returns a dictionary that can be used to trigger the
    `gold_curated_aggregation` DAG with the appropriate configuration.
    """
    try:
        envelope = json.loads(message.value())
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    # Look for the event type and the run ID of the completed silver run in the message envelope.
    # If the event type is not "silver.completed" or if the run ID is missing, return None to ignore.
    if envelope.get("event_type") != TOPIC_SILVER_COMPLETED:
        return None

    silver_run_id = envelope.get("run_id")

    if not silver_run_id:
        return None

    silver_domain = str((envelope.get("payload") or {}).get("silver_domain") or "")

    if not silver_domain or resolve_gold_metric(silver_domain) is None:
        return None

    trigger_run_id = f"gold_curated_aggregation__{silver_run_id}"
    envelope["_trigger_topic"] = message.topic()
    envelope["_trigger_partition"] = int(message.partition())
    envelope["_trigger_offset"] = int(message.offset())

    return {
        "trigger_run_id": trigger_run_id,
        "conf": envelope,
    }


def trigger_aggregation(event, **context):
    """
    This function is called when the `apply_function` detects a relevant
    silver-completed event. It uses the metadata from the message to trigger a
    new run of the `gold_curated_aggregation` DAG.
    """
    trigger = TriggerDagRunOperator(
        task_id=f"trigger_{event['trigger_run_id']}",
        trigger_dag_id="gold_curated_aggregation",
        trigger_run_id=event["trigger_run_id"],
        conf=event["conf"],
        reset_dag_run=False,
        wait_for_completion=False,
    )
    trigger.execute(context)

"""
This DAG defines a long-running RedPanda listener that waits for messages indicating
the completion of silver pipeline runs.
"""
with DAG(
    dag_id="gold_curated_listener",
    description="Long-running RedPanda listener that triggers gold_curated_aggregation.",
    default_args=default_args,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule="@continuous",
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["curated", "gold", "listener"],
):
    AwaitMessageTriggerFunctionSensor(
        task_id="await_silver_completed",
        topics=[TOPIC_SILVER_COMPLETED],
        apply_function="gold_curated.listener.apply_silver_event",
        kafka_config_id="kafka_default",
        event_triggered_function=trigger_aggregation,
        poll_interval=5,
        poll_timeout=10,
    )
