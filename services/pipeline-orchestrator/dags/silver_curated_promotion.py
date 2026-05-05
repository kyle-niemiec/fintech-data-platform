"""Silver curated promotion DAG.

Processes one bronze event and promotes Opportunity data into
lakehouse.silver.dim_opportunity.
"""

from __future__ import annotations

import io
import logging
import os
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pendulum
from airflow import DAG
from airflow.decorators import task
from airflow.exceptions import AirflowException

from silver_curated_common import (
    INITIATOR,
    MERGE_SQL_PATH,
    SILVER_DDL_SQL_PATH,
    SILVER_DOMAIN,
    SILVER_TABLE,
    SOURCE_SYSTEM,
    STAGING_PREFIX,
    TOPIC_SILVER_COMPLETED,
    TOPIC_SILVER_FAILED,
    TOPIC_SILVER_STARTED,
    TRIGGER_TYPE,
    _build_producer,
    _get_minio_client,
    _iter_sql_statements,
    _now_utc,
    _open_event_store_conn,
    _trino_cursor,
    default_args,
)

logger = logging.getLogger(__name__)


def _emit_failure_event(context):
    """
    DAG-level failure callback: emit pipeline.silver.failed.v1 + close run.
    """
    from libs.platform_events.envelope import (
        Envelope,
        EventSource,
        PipelineClass,
        PipelineName,
    )
    from libs.platform_events.event_store import append_event, close_run

    # Get DAG information from context and prepare the payload
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

    # Build the Kafka message envelope
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

    # Initiate the producer and output the failure to a Kafka event
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


"""
Create the promotion DAG using the defined tasks. The DAG is triggered manually
with a bronze envelope in the conf, which is emitted by the bronze DAG upon
completion of a batch. The promotion DAG will read the bronze data, apply masking,
merge into silver.dim_opportunity using SCD2 logic, and emit a silver.completed
event with details about the promotion.
"""
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

    # ——————————————————————————————————————————————————
    # TASK: Open curated run
    # ——————————————————————————————————————————————————
    @task(task_id="open_curated_run")
    def open_curated_run(**context) -> dict[str, Any]:
        """
        Open a new curated run.
        """
        from libs.platform_events.envelope import (
            Envelope,
            EventSource,
            PipelineClass,
            PipelineName,
        )
        from libs.platform_events.event_store import append_event, open_run

        # Extract the bronze envelope from the DAG run configuration
        dag_run = context["dag_run"]
        bronze_envelope = dag_run.conf or {}

        if not bronze_envelope:
            raise AirflowException("silver_curated_promotion triggered without a bronze envelope in conf")

        # Ensure the parent run ID is present
        parent_run_id = bronze_envelope.get("run_id")

        if not parent_run_id:
            raise AirflowException("bronze envelope missing run_id")

        # Ensure that the output context is contained in the payload
        bronze_payload = bronze_envelope.get("payload") or {}
        bronze_uris = bronze_payload.get("output_uris") or []

        if not bronze_uris:
            raise AirflowException("bronze envelope payload missing output_uris")

        # Create event refs for tracability
        trace_id = bronze_envelope.get("trace_id") or str(uuid4())
        bronze_trigger_ref = bronze_envelope.get("trigger_event_ref") or dag_run.run_id
        trigger_event_ref = f"silver_curated_promotion__{parent_run_id}"

        curated_run_id = uuid4()
        trace_uuid = UUID(trace_id)

        # Open a new run for the silver promotion and emit a silver.started event
        with _open_event_store_conn() as conn:
            with conn.transaction():
                # Configure the new run
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

                # Emit the silver.started event
                started_envelope = Envelope.build(
                    event_type=TOPIC_SILVER_STARTED,
                    source=EventSource.orchestration,
                    run_id=effective_run_id,
                    pipeline_class=PipelineClass.curated,
                    pipeline_name=PipelineName.curated_promotion,
                    parent_run_id=UUID(parent_run_id),
                    trigger_event_ref=trigger_event_ref,
                    trace_id=trace_uuid,
                    payload={
                        "message": "Silver curated promotion started.",
                        "stage": "silver",
                        "parent_run_id": parent_run_id,
                        "input_uris": bronze_uris,
                        "transform_id": "silver_curated_promotion",
                        "transform_version": "v1",
                    },
                )

                # Write the event to the event store
                append_event(
                    conn,
                    started_envelope,
                    topic=TOPIC_SILVER_STARTED,
                    partition=-1,
                    kafka_offset=-1,
                )

        # Return state for downstream tasks
        return {
            "curated_run_id": str(effective_run_id),
            "parent_run_id": parent_run_id,
            "trace_id": trace_id,
            "trigger_event_ref": trigger_event_ref,
            "bronze_trigger_ref": bronze_trigger_ref,
            "bronze_uris": bronze_uris,
            "bronze_record_count": int(bronze_payload.get("record_count") or 0),
        }


    # ——————————————————————————————————————————————————
    # TASK: Stage and mask bronze data
    # ——————————————————————————————————————————————————
    @task(task_id="stage_and_mask_bronze")
    def stage_and_mask_bronze(state: dict[str, Any]) -> dict[str, Any]:
        """
        Read bronze parquet, deterministically mask the account_id, restage it.
        """
        import pyarrow as pa
        import pyarrow.parquet as pq
        from libs.platform_masking import tokenize
        from minio.sse import SseKMS

        curated_run_id = state["curated_run_id"]
        bucket = os.environ["MINIO_BUCKET_NAME"]
        kms_key = os.environ["MINIO_KMS_KEY_ID"]

        minio_client = _get_minio_client()
        bronze_tables: list[pa.Table] = []

        # Read each bronze parquet file into a PyArrow table
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

        # Validate that we have bronze data to promote
        if not bronze_tables:
            raise AirflowException("no bronze rows to promote")

        table = pa.concat_tables(bronze_tables, promote=True)
        records = table.to_pylist()
        masked_rows: list[dict[str, Any]] = []

        # Apply masking to the account_id and prepare records for staging
        for row in records:
            account_id = row.get("AccountId")

            account_id_token = (
                tokenize(str(account_id), scope="salesforce_account_id")
                if account_id is not None
                else None
            )

            system_mod = row.get("SystemModstamp")

            # Append the masked record to the list of rows to be staged
            masked_rows.append({
                "opportunity_id": row.get("Id"),
                "account_id_token": account_id_token,
                "name": row.get("Name"),
                "stage_name": row.get("StageName"),
                "amount": row.get("Amount"),
                "close_date": row.get("CloseDate"),
                "is_won": row.get("IsWon"),
                "is_closed": row.get("IsClosed"),
                "source_system_mod": system_mod,
            })

        # Stage the masked rows
        staged_table = pa.Table.from_pylist(masked_rows)
        buffer = io.BytesIO()
        pq.write_table(staged_table, buffer, compression="snappy")
        buffer.seek(0)
        body = buffer.getvalue()
        now = _now_utc()

        staged_key = (
            f"{STAGING_PREFIX}/year={now:%Y}/month={now:%m}/day={now:%d}/"
            f"run_id={curated_run_id}/_staging/part-0.parquet"
        )

        # Write the masked data back to MinIO for consumption by the merge task
        minio_client.put_object(
            bucket_name=bucket,
            object_name=staged_key,
            data=io.BytesIO(body),
            length=len(body),
            content_type="application/octet-stream",
            sse=SseKMS(kms_key, {}),
        )

        staged_uri = f"s3://{bucket}/{staged_key}"

        # Return the staged URI and record count for downstream tasks
        return {
            **state,
            "staged_uri": staged_uri,
            "staged_row_count": len(masked_rows),
        }


    # ——————————————————————————————————————————————————
    # TASK: Merge into silver with SCD2 logic
    # ——————————————————————————————————————————————————
    @task(task_id="merge_into_silver")
    def merge_into_silver(state: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the SCD2 MERGE against lakehouse.silver.dim_opportunity.
        """
        ddl_sql_template = SILVER_DDL_SQL_PATH.read_text()
        merge_sql_template = MERGE_SQL_PATH.read_text()

        # Replace placeholders in the SQL templates with actual values from the state
        merge_sql = (
            merge_sql_template
            .replace(":staged_uri", f"'{state['staged_uri']}'")
            .replace(":parent_run_id", f"'{state['parent_run_id']}'")
            .replace(":curated_run_id", f"'{state['curated_run_id']}'")
        )

        # Create the Trino cursor
        conn, cur = _trino_cursor()

        # Execute the DDL to ensure the silver table exists, then execute the MERGE statement
        try:
            merge_stats: dict[str, int] = {"inserted": 0, "updated": 0, "closed": 0}

            for stmt in _iter_sql_statements(ddl_sql_template):
                cur.execute(stmt)
                cur.fetchall()
            for stmt in _iter_sql_statements(merge_sql):
                cur.execute(stmt)
                cur.fetchall()
        finally:
            cur.close()
            conn.close()

        # Return the merge statistics for downstream tasks
        return {**state, "merge_stats": merge_stats}


    # ——————————————————————————————————————————————————
    # TASK: Record checkpoint and emit silver.completed event
    # ——————————————————————————————————————————————————
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

        # Extract necessary information from the state to build the silver.completed event
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

        # Emit the silver.completed event to Kafka and capture the partition and offset for event store persistence
        try:
            partition, offset = producer.produce(
                TOPIC_SILVER_COMPLETED, envelope, key=str(curated_run_id)
            )
        finally:
            producer.close()

        # Record a checkpoint in the event store, persist the silver.completed event, and close the run as completed
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


    # ——————————————————————————————————————————————————
    # DEPENDENCIES: Define the DAG task execution order
    # ——————————————————————————————————————————————————
    state = open_curated_run()
    staged = stage_and_mask_bronze(state)
    merged = merge_into_silver(staged)
    record_checkpoint_and_emit_event(merged)
