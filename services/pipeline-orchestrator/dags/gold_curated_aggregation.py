"""Gold curated aggregation.

Same cooperating-DAG split as silver_curated_promotion:

  gold_curated_listener     — @continuous, AwaitMessageTriggerFunctionSensor
                              on pipeline.silver.completed.v1; triggers one
                              gold_curated_aggregation run per message.
  gold_curated_aggregation  — schedule=None; opens curated_promotion run with
                              parent_run_id = silver.run_id, re-computes the
                              KPI via a Trino INSERT on silver.dim_opportunity,
                              records gold_checkpoint + emits
                              pipeline.gold.completed.v1 in a single txn.

Failure emits pipeline.gold.failed.v1 and closes the run status=failed.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pendulum
from airflow import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowException
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.apache.kafka.sensors.await_message import (
    AwaitMessageTriggerFunctionSensor,
)

logger = logging.getLogger(__name__)

SOURCE_SYSTEM = "curated"
TOPIC_SILVER_COMPLETED = "pipeline.silver.completed.v1"
TOPIC_GOLD_COMPLETED = "pipeline.gold.completed.v1"
TOPIC_GOLD_FAILED = "pipeline.gold.failed.v1"
GOLD_METRIC = "pipeline_conversion"
GOLD_TABLE = "lakehouse.gold.kpi_pipeline_conversion"
TRIGGER_TYPE = "event"
INITIATOR = "airflow"

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
AGG_SQL_PATH = SQL_DIR / "gold_kpi_pipeline_conversion_insert.sql"

default_args = {
    "owner": "curated_promotion",
    "depends_on_past": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=2),
    "email_on_failure": False,
    "email_on_retry": False,
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _open_event_store_conn():
    import psycopg

    return psycopg.connect(
        host=os.environ["EVENT_STORE_DB_HOST"],
        port=int(os.environ["EVENT_STORE_DB_PORT"]),
        dbname=os.environ["EVENT_STORE_DB"],
        user=os.environ["EVENT_APPEND_DB_USER"],
        password=os.environ["EVENT_APPEND_DB_PASSWORD"],
        autocommit=False,
    )


def _build_producer():
    from libs.platform_events.producer import EventProducer, ProducerConfig

    return EventProducer(
        ProducerConfig.from_env(
            client_id="gold-curated-aggregation-dag",
            username_var="REDPANDA_ORCHESTRATOR_SERVICE_USER",
            password_var="REDPANDA_ORCHESTRATOR_SERVICE_PASSWORD",
        )
    )


def _trino_cursor():
    from trino.dbapi import connect

    conn = connect(
        host=os.environ.get("TRINO_HOST", "trino"),
        port=int(os.environ.get("TRINO_PORT", "8080")),
        user=os.environ.get("TRINO_USER", "trino_etl"),
        catalog="lakehouse",
    )
    return conn, conn.cursor()


# ---------------------------------------------------------------------------
# Listener DAG
# ---------------------------------------------------------------------------

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
        apply_function="gold_curated_aggregation.apply_silver_event",
        kafka_config_id="kafka_default",
        event_triggered_function=trigger_aggregation,
        poll_interval=5,
        poll_timeout=10,
    )


# ---------------------------------------------------------------------------
# Aggregation DAG
# ---------------------------------------------------------------------------

def _emit_failure_event(context):
    from libs.platform_events.envelope import (
        Envelope,
        EventSource,
        PipelineClass,
        PipelineName,
    )
    from libs.platform_events.event_store import append_event, close_run

    dag_run = context["dag_run"]
    conf = dag_run.conf or {}
    parent_run_id = conf.get("run_id")
    trace_id = conf.get("trace_id")
    silver_trigger_ref = conf.get("trigger_event_ref") or dag_run.run_id
    curated_run_id = (dag_run.conf or {}).get("_curated_run_id") or str(uuid4())

    payload = {
        "message": "Gold curated aggregation failed",
        "stage": "gold",
        "metric": GOLD_METRIC,
        "output_table": GOLD_TABLE,
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
    try:
        partition, offset = producer.produce(
            TOPIC_GOLD_FAILED, envelope, key=str(envelope.run_id)
        )
    finally:
        producer.close()

    try:
        with _open_event_store_conn() as conn:
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
        from libs.platform_events.envelope import PipelineClass, PipelineName
        from libs.platform_events.event_store import open_run

        dag_run = context["dag_run"]
        silver_envelope = dag_run.conf or {}
        if not silver_envelope:
            raise AirflowException("gold_curated_aggregation triggered without a silver envelope in conf")

        parent_run_id = silver_envelope.get("run_id")
        if not parent_run_id:
            raise AirflowException("silver envelope missing run_id")

        trace_id = silver_envelope.get("trace_id") or str(uuid4())
        silver_trigger_ref = silver_envelope.get("trigger_event_ref") or dag_run.run_id
        trigger_event_ref = f"gold_curated_aggregation__{parent_run_id}"

        curated_run_id = uuid4()
        with _open_event_store_conn() as conn:
            with conn.transaction():
                effective_run_id = open_run(
                    conn,
                    run_id=curated_run_id,
                    pipeline_class=PipelineClass.curated,
                    pipeline_name=PipelineName.curated_promotion,
                    source_system=SOURCE_SYSTEM,
                    trigger_type=TRIGGER_TYPE,
                    trigger_event_ref=trigger_event_ref,
                    initiator=INITIATOR,
                    status="running",
                    parent_run_id=UUID(parent_run_id),
                )
        silver_payload = silver_envelope.get("payload") or {}
        return {
            "curated_run_id": str(effective_run_id),
            "parent_run_id": parent_run_id,
            "trace_id": trace_id,
            "trigger_event_ref": trigger_event_ref,
            "silver_trigger_ref": silver_trigger_ref,
            "silver_table": silver_payload.get("output_table"),
        }

    @task(task_id="run_aggregation_sql")
    def run_aggregation_sql(state: dict[str, Any]) -> dict[str, Any]:
        computed_at = _now_utc()
        snapshot_date = computed_at.date().isoformat()
        computed_at_iso = computed_at.isoformat()

        agg_sql_template = AGG_SQL_PATH.read_text()
        agg_sql = (
            agg_sql_template
            .replace(":curated_run_id", f"'{state['curated_run_id']}'")
            .replace(":computed_at", f"'{computed_at_iso}'")
            .replace(":snapshot_date", f"'{snapshot_date}'")
        )

        record_count = 0
        conn, cur = _trino_cursor()
        try:
            for stmt in (s.strip() for s in agg_sql.split(";")):
                if not stmt:
                    continue
                cur.execute(stmt)
                cur.fetchall()
            count_cur = conn.cursor()
            try:
                count_cur.execute(
                    f"SELECT COUNT(*) FROM {GOLD_TABLE} "
                    f"WHERE curated_run_id = '{state['curated_run_id']}'"
                )
                row = count_cur.fetchone()
                record_count = int(row[0]) if row else 0
            finally:
                count_cur.close()
        finally:
            cur.close()
            conn.close()

        return {
            **state,
            "snapshot_date": snapshot_date,
            "computed_at": computed_at_iso,
            "record_count": record_count,
        }

    @task(task_id="record_checkpoint_and_emit_event")
    def record_checkpoint_and_emit_event(state: dict[str, Any]) -> None:
        from libs.platform_events.envelope import (
            Envelope,
            EventSource,
            PipelineClass,
            PipelineName,
        )
        from libs.platform_events.event_store import (
            append_event,
            append_gold_checkpoint,
            close_run,
        )

        curated_run_id = UUID(state["curated_run_id"])
        parent_run_id = UUID(state["parent_run_id"])
        trace_id = UUID(state["trace_id"])
        record_count = int(state.get("record_count") or 0)
        output_uris = [f"s3://{os.environ['MINIO_BUCKET_NAME']}/gold/metric={GOLD_METRIC}/"]
        input_uris = [state["silver_table"]] if state.get("silver_table") else []

        payload = {
            "message": f"Computed {GOLD_METRIC} KPI with {record_count} rows.",
            "stage": "gold",
            "metric": GOLD_METRIC,
            "output_table": GOLD_TABLE,
            "parent_run_id": str(parent_run_id),
            "record_count": record_count,
            "snapshot_date": state["snapshot_date"],
            "computed_at": state["computed_at"],
            "input_uris": input_uris,
            "output_uris": output_uris,
            "transform_id": "gold_curated_aggregation",
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
        try:
            partition, offset = producer.produce(
                TOPIC_GOLD_COMPLETED, envelope, key=str(curated_run_id)
            )
        finally:
            producer.close()

        with _open_event_store_conn() as conn:
            with conn.transaction():
                append_gold_checkpoint(
                    conn,
                    run_id=curated_run_id,
                    parent_run_id=parent_run_id,
                    metric=GOLD_METRIC,
                    input_uris=input_uris,
                    output_table=GOLD_TABLE,
                    output_uris=output_uris,
                    record_count=record_count,
                )
                append_event(
                    conn,
                    envelope,
                    topic=TOPIC_GOLD_COMPLETED,
                    partition=partition,
                    kafka_offset=offset,
                )
                close_run(conn, curated_run_id, status="completed")

    state = open_curated_run()
    computed = run_aggregation_sql(state)
    record_checkpoint_and_emit_event(computed)
