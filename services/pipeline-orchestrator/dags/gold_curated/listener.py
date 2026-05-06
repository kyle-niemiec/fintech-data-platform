"""Gold curated listener DAG."""

from __future__ import annotations

import json

import pendulum
from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.apache.kafka.sensors.kafka import AwaitMessageTriggerFunctionSensor

from gold_curated.common import TOPIC_SILVER_COMPLETED, default_args


def apply_silver_event(message, **_):
    try:
        envelope = json.loads(message.value())
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    if envelope.get("event_type") != TOPIC_SILVER_COMPLETED:
        return None

    silver_run_id = envelope.get("run_id")
    if not silver_run_id:
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
    trigger = TriggerDagRunOperator(
        task_id=f"trigger_{event['trigger_run_id']}",
        trigger_dag_id="gold_curated_aggregation",
        trigger_run_id=event["trigger_run_id"],
        conf=event["conf"],
        reset_dag_run=False,
        wait_for_completion=False,
    )
    trigger.execute(context)


with DAG(
    dag_id="gold_curated_listener",
    description="Long-running Kafka listener that triggers gold_curated_aggregation.",
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
