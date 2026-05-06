"""Task callables for silver curated promotion."""

from __future__ import annotations

import io
import logging
import os
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from airflow.exceptions import AirflowException

from silver_curated.common import (
    INITIATOR,
    MERGE_SQL_PATH,
    SILVER_DDL_SQL_PATH,
    SILVER_DOMAIN,
    SILVER_TABLE,
    SOURCE_SYSTEM,
    STAGING_PREFIX,
    TOPIC_SILVER_COMPLETED,
    TOPIC_SILVER_STARTED,
    TRIGGER_TYPE,
    _build_producer,
    _get_minio_client,
    _iter_sql_statements,
    _now_utc,
    _open_event_store_conn,
    _trino_cursor,
)

logger = logging.getLogger(__name__)


def open_curated_run(context: dict[str, Any]) -> dict[str, Any]:
    from libs.platform_events.envelope import (
        Envelope,
        EventSource,
        PipelineClass,
        PipelineName,
    )
    from libs.platform_events.event_store import append_event, open_run

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
    trigger_event_ref = f"silver_curated_promotion__{parent_run_id}"

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

            append_event(
                conn,
                started_envelope,
                topic=TOPIC_SILVER_STARTED,
                partition=-1,
                kafka_offset=-1,
            )

    return {
        "curated_run_id": str(effective_run_id),
        "parent_run_id": parent_run_id,
        "trace_id": trace_id,
        "trigger_event_ref": trigger_event_ref,
        "bronze_uris": bronze_uris,
        "bronze_record_count": int(bronze_payload.get("record_count") or 0),
    }


def stage_and_mask_bronze(state: dict[str, Any]) -> dict[str, Any]:
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
    now = _now_utc()

    staged_key = (
        f"{STAGING_PREFIX}/year={now:%Y}/month={now:%m}/day={now:%d}/"
        f"run_id={curated_run_id}/_staging/part-0.parquet"
    )

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
        "masked_rows": masked_rows,
    }


def merge_into_silver(state: dict[str, Any]) -> dict[str, Any]:
    def _sql_string_literal(value: Any) -> str:
        if value is None:
            return "NULL"
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

    def _sql_bool_literal(value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "t", "1", "yes", "y"}:
                return "TRUE"
            if normalized in {"false", "f", "0", "no", "n"}:
                return "FALSE"
        raise AirflowException(f"unsupported boolean value in masked row: {value!r}")

    ddl_sql_template = SILVER_DDL_SQL_PATH.read_text()
    merge_sql_template = MERGE_SQL_PATH.read_text()
    masked_rows = list(state.get("masked_rows") or [])

    row_values_sql = []
    for row in masked_rows:
        row_values_sql.append(
            "("
            f"{_sql_string_literal(row.get('opportunity_id'))}, "
            f"{_sql_string_literal(row.get('account_id_token'))}, "
            f"{_sql_string_literal(row.get('name'))}, "
            f"{_sql_string_literal(row.get('stage_name'))}, "
            f"{_sql_string_literal(row.get('amount'))}, "
            f"{_sql_string_literal(row.get('close_date'))}, "
            f"{_sql_bool_literal(row.get('is_won'))}, "
            f"{_sql_bool_literal(row.get('is_closed'))}, "
            f"{_sql_string_literal(row.get('source_system_mod'))}"
            ")"
        )

    merge_sql = (
        merge_sql_template.replace(
            "VALUES\n        :source_rows_values",
            "VALUES\n        " + ",\n        ".join(row_values_sql),
        )
        .replace(
            "CAST(:parent_run_id AS VARCHAR)",
            f"CAST('{state['parent_run_id']}' AS VARCHAR)",
        )
        .replace(
            "CAST(:curated_run_id AS VARCHAR)",
            f"CAST('{state['curated_run_id']}' AS VARCHAR)",
        )
    )

    conn, cur = _trino_cursor()

    try:
        merge_stats: dict[str, int] = {"inserted": 0, "updated": 0, "closed": 0}

        for stmt in _iter_sql_statements(ddl_sql_template):
            cur.execute(stmt)
            cur.fetchall()
        if not row_values_sql:
            logger.info("no masked rows available for merge; skipping MERGE statement")
            return {**state, "merge_stats": merge_stats}

        cur.execute(merge_sql.strip().rstrip(";"))
        cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return {**state, "merge_stats": merge_stats}


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
