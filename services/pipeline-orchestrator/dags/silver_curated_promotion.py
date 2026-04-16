"""Silver curated promotion.

Two DAGs cooperate:

  silver_curated_listener   — @continuous, AwaitMessageTriggerFunctionSensor
                              on ingest.salesforce.bronze.ready.v1; fires one
                              silver_curated_promotion DAG run per message.
  silver_curated_promotion  — schedule=None; processes one bronze event:
                              opens curated_promotion run (parent_run_id =
                              bronze run_id), stages+masks the bronze parquet,
                              MERGE INTO lakehouse.silver.dim_opportunity (SCD2),
                              records silver_checkpoint + emits
                              pipeline.silver.completed.v1 in a single txn.

Failure path: the DAG-level on_failure_callback emits
pipeline.silver.failed.v1 and closes the run with status="failed".
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
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
TOPIC_BRONZE_READY = "ingest.salesforce.bronze.ready.v1"
TOPIC_SILVER_COMPLETED = "pipeline.silver.completed.v1"
TOPIC_SILVER_FAILED = "pipeline.silver.failed.v1"
SILVER_DOMAIN = "salesforce_opportunity"
SILVER_TABLE = "lakehouse.silver.dim_opportunity"
STAGING_PREFIX = "warehouse/_staging/silver_curated_promotion"
TRIGGER_TYPE = "event"
INITIATOR = "airflow"

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
MERGE_SQL_PATH = SQL_DIR / "silver_dim_opportunity_merge.sql"

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


def _get_minio_client():
    from minio import Minio

    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_TRINO_WRITE_USER"],
        secret_key=os.environ["MINIO_TRINO_WRITE_SECRET"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
        region=os.environ.get("MINIO_REGION", "us-east-1"),
    )


def _build_producer():
    from libs.platform_events.producer import EventProducer, ProducerConfig

    return EventProducer(
        ProducerConfig.from_env(
            client_id="silver-curated-promotion-dag",
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
# Listener DAG — one TriggerDagRunOperator per bronze event
# ---------------------------------------------------------------------------

def apply_bronze_event(message, **_):
    """Validate that a Kafka message is a salesforce Opportunity bronze event.

    Returns a dict (event_triggered_function receives this as `event`).
    Returning None / falsy skips the trigger.
    """
    try:
        envelope = json.loads(message.value())
    except (TypeError, ValueError, json.JSONDecodeError):
        return None

    if envelope.get("event_type") != TOPIC_BRONZE_READY:
        return None

    payload = envelope.get("payload") or {}
    if payload.get("object_name") != "Opportunity":
        return None
    if payload.get("stage") != "bronze":
        return None

    run_id = envelope.get("run_id")
    if not run_id:
        return None

    trigger_run_id = f"silver_curated_promotion__{run_id}"
    return {
        "trigger_run_id": trigger_run_id,
        "conf": envelope,
    }


def trigger_promotion(event, **context):
    trigger = TriggerDagRunOperator(
        task_id=f"trigger_{event['trigger_run_id']}",
        trigger_dag_id="silver_curated_promotion",
        trigger_run_id=event["trigger_run_id"],
        conf=event["conf"],
        reset_dag_run=False,
        wait_for_completion=False,
    )
    trigger.execute(context)


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
        topics=[TOPIC_BRONZE_READY],
        apply_function="silver_curated_promotion.apply_bronze_event",
        kafka_config_id="kafka_default",
        event_triggered_function=trigger_promotion,
        poll_interval=5,
        poll_timeout=10,
    )


# ---------------------------------------------------------------------------
# Promotion DAG — one run per bronze event
# ---------------------------------------------------------------------------

def _emit_failure_event(context):
    """DAG-level failure callback: emit pipeline.silver.failed.v1 + close run."""
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
    bronze_trigger_ref = conf.get("trigger_event_ref") or dag_run.run_id

    curated_run_id = (dag_run.conf or {}).get("_curated_run_id") or str(uuid4())

    payload = {
        "message": "Silver curated promotion failed",
        "stage": "silver",
        "silver_domain": SILVER_DOMAIN,
        "output_table": SILVER_TABLE,
        "parent_run_id": parent_run_id,
        "record_count": 0,
        "input_uris": (conf.get("payload") or {}).get("output_uris", []),
        "output_uris": [],
        "transform_id": "silver_curated_promotion",
        "transform_version": "v1",
    }

    try:
        envelope = Envelope.build(
            event_type=TOPIC_SILVER_FAILED,
            source=EventSource.orchestration,
            run_id=UUID(curated_run_id),
            pipeline_class=PipelineClass.curated,
            pipeline_name=PipelineName.curated_promotion,
            parent_run_id=UUID(parent_run_id) if parent_run_id else None,
            trigger_event_ref=bronze_trigger_ref,
            trace_id=UUID(trace_id) if trace_id else uuid4(),
            payload=payload,
        )
    except Exception:
        logger.exception("failed to build silver.failed envelope")
        return

    producer = _build_producer()
    try:
        partition, offset = producer.produce(
            TOPIC_SILVER_FAILED, envelope, key=str(envelope.run_id)
        )
    finally:
        producer.close()

    try:
        with _open_event_store_conn() as conn:
            with conn.transaction():
                append_event(
                    conn,
                    envelope,
                    topic=TOPIC_SILVER_FAILED,
                    partition=partition,
                    kafka_offset=offset,
                )
                close_run(conn, UUID(curated_run_id), status="failed")
    except Exception:
        logger.exception("failed to persist silver.failed event/close run")


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
        from libs.platform_events.envelope import PipelineClass, PipelineName
        from libs.platform_events.event_store import open_run

        dag_run = context["dag_run"]
        bronze_envelope = dag_run.conf or {}
        if not bronze_envelope:
            raise AirflowException("silver_curated_promotion triggered without a bronze envelope in conf")

        parent_run_id = bronze_envelope.get("run_id")
        if not parent_run_id:
            raise AirflowException("bronze envelope missing run_id")

        bronze_payload = bronze_envelope.get("payload") or {}
        bronze_uris = bronze_payload.get("output_uris") or []
        if not bronze_uris:
            raise AirflowException("bronze envelope payload missing output_uris")

        trace_id = bronze_envelope.get("trace_id") or str(uuid4())
        bronze_trigger_ref = bronze_envelope.get("trigger_event_ref") or dag_run.run_id
        trigger_event_ref = f"silver_curated_promotion__{parent_run_id}"

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
        return {
            "curated_run_id": str(effective_run_id),
            "parent_run_id": parent_run_id,
            "trace_id": trace_id,
            "trigger_event_ref": trigger_event_ref,
            "bronze_trigger_ref": bronze_trigger_ref,
            "bronze_uris": bronze_uris,
            "bronze_record_count": int(bronze_payload.get("record_count") or 0),
        }

    @task(task_id="stage_and_mask_bronze")
    def stage_and_mask_bronze(state: dict[str, Any]) -> dict[str, Any]:
        """Read bronze parquet, deterministically mask the account_id, restage it.

        The MERGE SQL reads from the staged URI. We mask the natural FK
        (account_id → account_id_token) via platform_masking.tokenize so the
        silver row carries no raw Salesforce account id. Masking is
        deterministic per tokenize scope so re-runs produce identical keys.
        """
        import io
        from urllib.parse import urlparse

        import pyarrow as pa
        import pyarrow.parquet as pq
        from libs.platform_masking import tokenize
        from minio.sse import SseKMS

        curated_run_id = state["curated_run_id"]
        bucket = os.environ["MINIO_BUCKET_NAME"]
        kms_key = os.environ["MINIO_KMS_KEY_ID"]

        minio_client = _get_minio_client()

        bronze_tables: list[pa.Table] = []
        for uri in state["bronze_uris"]:
            parsed = urlparse(uri)
            if parsed.scheme != "s3":
                raise AirflowException(f"unexpected bronze uri scheme: {uri}")
            object_key = parsed.path.lstrip("/")
            response = minio_client.get_object(bucket, object_key)
            try:
                body = response.read()
            finally:
                response.close()
                response.release_conn()
            bronze_tables.append(pq.read_table(io.BytesIO(body)))

        if not bronze_tables:
            raise AirflowException("no bronze rows to promote")

        table = pa.concat_tables(bronze_tables, promote=True)
        records = table.to_pylist()

        masked_rows: list[dict[str, Any]] = []
        for row in records:
            account_id = row.get("AccountId")
            account_id_token = (
                tokenize(str(account_id), scope="salesforce_account_id")
                if account_id is not None
                else None
            )
            system_mod = row.get("SystemModstamp")
            masked_rows.append(
                {
                    "opportunity_id": row.get("Id"),
                    "account_id_token": account_id_token,
                    "name": row.get("Name"),
                    "stage_name": row.get("StageName"),
                    "amount": row.get("Amount"),
                    "close_date": row.get("CloseDate"),
                    "is_won": row.get("IsWon"),
                    "is_closed": row.get("IsClosed"),
                    "source_system_mod": system_mod,
                }
            )

        staged_table = pa.Table.from_pylist(masked_rows)
        buffer = io.BytesIO()
        pq.write_table(staged_table, buffer, compression="snappy")
        buffer.seek(0)
        body = buffer.getvalue()

        staged_key = f"{STAGING_PREFIX}/run_id={curated_run_id}/part-0.parquet"
        minio_client.put_object(
            bucket_name=bucket,
            object_name=staged_key,
            data=io.BytesIO(body),
            length=len(body),
            content_type="application/octet-stream",
            sse=SseKMS(kms_key, {}),
        )
        staged_uri = f"s3://{bucket}/{staged_key}"

        return {
            **state,
            "staged_uri": staged_uri,
            "staged_row_count": len(masked_rows),
        }

    @task(task_id="merge_into_silver")
    def merge_into_silver(state: dict[str, Any]) -> dict[str, Any]:
        """Execute the SCD2 MERGE against lakehouse.silver.dim_opportunity."""
        merge_sql_template = MERGE_SQL_PATH.read_text()
        merge_sql = (
            merge_sql_template
            .replace(":staged_uri", f"'{state['staged_uri']}'")
            .replace(":parent_run_id", f"'{state['parent_run_id']}'")
            .replace(":curated_run_id", f"'{state['curated_run_id']}'")
        )
        conn, cur = _trino_cursor()
        try:
            merge_stats: dict[str, int] = {"inserted": 0, "updated": 0, "closed": 0}
            for stmt in (s.strip() for s in merge_sql.split(";")):
                if not stmt:
                    continue
                cur.execute(stmt)
                cur.fetchall()
        finally:
            cur.close()
            conn.close()
        return {**state, "merge_stats": merge_stats}

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
            append_silver_checkpoint,
            close_run,
        )

        curated_run_id = UUID(state["curated_run_id"])
        parent_run_id = UUID(state["parent_run_id"])
        trace_id = UUID(state["trace_id"])
        merge_stats = state.get("merge_stats") or {}
        record_count = int(state.get("staged_row_count") or 0)
        output_uris = [f"s3://{os.environ['MINIO_BUCKET_NAME']}/silver/domain={SILVER_DOMAIN}/"]

        payload = {
            "message": f"Promoted {record_count} Salesforce Opportunity rows to silver.",
            "stage": "silver",
            "silver_domain": SILVER_DOMAIN,
            "output_table": SILVER_TABLE,
            "parent_run_id": str(parent_run_id),
            "record_count": record_count,
            "merge_inserted": int(merge_stats.get("inserted") or 0),
            "merge_updated": int(merge_stats.get("updated") or 0),
            "merge_closed": int(merge_stats.get("closed") or 0),
            "input_uris": state.get("bronze_uris", []),
            "output_uris": output_uris,
            "transform_id": "silver_curated_promotion",
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
        try:
            partition, offset = producer.produce(
                TOPIC_SILVER_COMPLETED, envelope, key=str(curated_run_id)
            )
        finally:
            producer.close()

        with _open_event_store_conn() as conn:
            with conn.transaction():
                append_silver_checkpoint(
                    conn,
                    run_id=curated_run_id,
                    parent_run_id=parent_run_id,
                    silver_domain=SILVER_DOMAIN,
                    input_uris=list(state.get("bronze_uris", [])),
                    output_table=SILVER_TABLE,
                    output_uris=output_uris,
                    record_count=record_count,
                    merge_inserted=int(merge_stats.get("inserted") or 0),
                    merge_updated=int(merge_stats.get("updated") or 0),
                    merge_closed=int(merge_stats.get("closed") or 0),
                )
                append_event(
                    conn,
                    envelope,
                    topic=TOPIC_SILVER_COMPLETED,
                    partition=partition,
                    kafka_offset=offset,
                )
                close_run(conn, curated_run_id, status="completed")

    state = open_curated_run()
    staged = stage_and_mask_bronze(state)
    merged = merge_into_silver(staged)
    record_checkpoint_and_emit_event(merged)
