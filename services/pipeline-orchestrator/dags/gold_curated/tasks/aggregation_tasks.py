"""Task callables for gold curated aggregation."""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID, uuid4

from airflow.exceptions import AirflowException

from gold_curated.common import (
    AGG_SQL_PATH,
    GOLD_DDL_SQL_PATH,
    GOLD_METRIC,
    GOLD_TABLE,
    INITIATOR,
    SOURCE_SYSTEM,
    TOPIC_GOLD_COMPLETED,
    TOPIC_GOLD_STARTED,
    TRIGGER_TYPE,
    _build_producer,
    _iter_sql_statements,
    _now_utc,
    _open_event_store_conn,
    _trino_cursor,
)


def open_curated_run(context: dict[str, Any]) -> dict[str, Any]:
    from libs.platform_events.envelope import (
        Envelope,
        EventSource,
        PipelineClass,
        PipelineName,
    )
    from libs.platform_events.event_store import append_event, open_run

    dag_run = context["dag_run"]
    silver_envelope = dag_run.conf or {}
    if not silver_envelope:
        raise AirflowException("gold_curated_aggregation triggered without a silver envelope in conf")

    parent_run_id = silver_envelope.get("run_id")
    if not parent_run_id:
        raise AirflowException("silver envelope missing run_id")

    trace_id = silver_envelope.get("trace_id") or str(uuid4())
    trigger_event_ref = f"gold_curated_aggregation__{parent_run_id}"

    curated_run_id = uuid4()
    trace_uuid = UUID(trace_id)
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
            started_envelope = Envelope.build(
                event_type=TOPIC_GOLD_STARTED,
                source=EventSource.orchestration,
                run_id=effective_run_id,
                pipeline_class=PipelineClass.curated,
                pipeline_name=PipelineName.curated_promotion,
                parent_run_id=UUID(parent_run_id),
                trigger_event_ref=trigger_event_ref,
                trace_id=trace_uuid,
                payload={
                    "message": "Gold curated aggregation started.",
                    "stage": "gold",
                    "parent_run_id": parent_run_id,
                    "input_table": (silver_envelope.get("payload") or {}).get("output_table"),
                    "transform_id": "gold_curated_aggregation",
                    "transform_version": "v1",
                },
            )
            append_event(
                conn,
                started_envelope,
                topic=TOPIC_GOLD_STARTED,
                partition=-1,
                kafka_offset=-1,
            )
    silver_payload = silver_envelope.get("payload") or {}
    return {
        "curated_run_id": str(effective_run_id),
        "parent_run_id": parent_run_id,
        "trace_id": trace_id,
        "trigger_event_ref": trigger_event_ref,
        "silver_table": silver_payload.get("output_table"),
    }


def run_aggregation_sql(state: dict[str, Any]) -> dict[str, Any]:
    computed_at = _now_utc()
    snapshot_date = computed_at.date().isoformat()
    computed_at_iso = computed_at.isoformat()

    ddl_sql_template = GOLD_DDL_SQL_PATH.read_text()
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
        for stmt in _iter_sql_statements(ddl_sql_template):
            cur.execute(stmt)
            cur.fetchall()
        for stmt in _iter_sql_statements(agg_sql):
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
