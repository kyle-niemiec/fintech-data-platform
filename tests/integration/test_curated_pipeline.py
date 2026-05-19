"""End-to-end curated integration coverage (requires full compose stack)."""

from __future__ import annotations

import io
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from meridian.libs.redpanda_events.envelope import Envelope, EventSource, PipelineClass, PipelineName


pytestmark = pytest.mark.integration


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"missing required integration env var: {name}")
    return value


def _build_minio_client():
    minio = pytest.importorskip("minio")
    return minio.Minio(
        _require_env("MINIO_ENDPOINT"),
        access_key=_require_env("MINIO_TRANSFORM_USER"),
        secret_key=_require_env("MINIO_TRANSFORM_SECRET"),
        secure=_require_env("MINIO_SECURE").lower() == "true",
        region=os.environ.get("MINIO_REGION", "us-east-1"),
    )


def _build_kafka_producer():
    kafka = pytest.importorskip("confluent_kafka")
    config: dict[str, Any] = {"bootstrap.servers": _require_env("REDPANDA_BOOTSTRAP_SERVERS")}
    protocol = os.environ.get("REDPANDA_SECURITY_PROTOCOL", "PLAINTEXT")
    if protocol != "PLAINTEXT":
        config["security.protocol"] = protocol
        config["sasl.mechanism"] = os.environ.get("REDPANDA_SASL_MECHANISM", "SCRAM-SHA-256")
        config["sasl.username"] = _require_env("REDPANDA_FRAUD_SERVICE_USER")
        config["sasl.password"] = _require_env("REDPANDA_FRAUD_SERVICE_PASSWORD")
    return kafka.Producer(config)


def _event_store_conn() -> psycopg.Connection:
    return psycopg.connect(
        host=_require_env("EVENT_STORE_DB_HOST"),
        port=int(_require_env("EVENT_STORE_DB_PORT")),
        dbname=_require_env("EVENT_STORE_DB"),
        user=_require_env("EVENT_APPEND_DB_USER"),
        password=_require_env("EVENT_APPEND_DB_PASSWORD"),
        autocommit=True,
    )


def _trino_conn():
    trino = pytest.importorskip("trino.dbapi")
    return trino.connect(
        host=os.environ.get("TRINO_HOST", "trino"),
        port=int(os.environ.get("TRINO_PORT", "8080")),
        user=os.environ.get("TRINO_USER", "trino_etl"),
        catalog="lakehouse",
    )


def _upload_parquet(*, client, bucket: str, object_key: str, rows: list[dict[str, Any]]) -> str:
    body = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(rows), body, compression="snappy")
    body.seek(0)
    client.put_object(bucket_name=bucket, object_name=object_key, data=body, length=len(body.getbuffer()))
    return f"s3://{bucket}/{object_key}"


@dataclass(frozen=True)
class CuratedScenario:
    topic: str
    event_type: str
    source: EventSource
    payload: dict[str, Any]
    silver_domain: str
    silver_table: str
    gold_metric: str | None
    gold_table: str | None


def _scenario_envelope(scenario: CuratedScenario, *, run_id: UUID, uri: str) -> Envelope:
    payload = {**scenario.payload, "stage": "bronze", "format": "parquet", "input_uris": [], "output_uris": [uri], "record_count": 1}
    return Envelope.build(
        event_type=scenario.event_type,
        source=scenario.source,
        run_id=run_id,
        pipeline_class=PipelineClass.ingestion,
        pipeline_name=PipelineName.salesforce_ingestion if scenario.source == EventSource.salesforce else PipelineName.cdc_bronze_write if scenario.source == EventSource.cdc else PipelineName.excel_ingestion,
        trigger_event_ref=f"integration:{scenario.event_type}:{run_id}",
        trace_id=uuid4(),
        payload=payload,
    )


def _publish_envelope(producer, topic: str, envelope: Envelope) -> None:
    delivered: list[Exception | None] = []

    def _delivery(err, _msg):  # noqa: ANN001
        delivered.append(err)

    producer.produce(topic, envelope.to_wire(), key=str(envelope.run_id), callback=_delivery)
    producer.flush(10.0)
    if delivered and delivered[0] is not None:
        raise RuntimeError(f"failed to publish integration envelope: {delivered[0]}")


def _poll_silver_completion(conn: psycopg.Connection, *, parent_run_id: str, silver_domain: str, timeout_s: int = 180) -> UUID:
    deadline = time.time() + timeout_s
    with conn.cursor() as cur:
        while time.time() < deadline:
            cur.execute(
                """
                SELECT run_id
                FROM event_store.event_log
                WHERE event_type = 'pipeline.silver.completed.v1'
                  AND payload->>'parent_run_id' = %s
                  AND payload->>'silver_domain' = %s
                ORDER BY occurred_at DESC
                LIMIT 1
                """,
                (parent_run_id, silver_domain),
            )
            row = cur.fetchone()
            if row:
                return UUID(str(row[0]))
            time.sleep(2)
    raise TimeoutError(f"timed out waiting for silver completion for run_id={parent_run_id} domain={silver_domain}")


def _poll_gold_completion(conn: psycopg.Connection, *, parent_run_id: str, metric: str, timeout_s: int = 180) -> UUID:
    deadline = time.time() + timeout_s
    with conn.cursor() as cur:
        while time.time() < deadline:
            cur.execute(
                """
                SELECT run_id
                FROM event_store.event_log
                WHERE event_type = 'pipeline.gold.completed.v1'
                  AND payload->>'parent_run_id' = %s
                  AND payload->>'metric' = %s
                ORDER BY occurred_at DESC
                LIMIT 1
                """,
                (parent_run_id, metric),
            )
            row = cur.fetchone()
            if row:
                return UUID(str(row[0]))
            time.sleep(2)
    raise TimeoutError(f"timed out waiting for gold completion for parent_run_id={parent_run_id} metric={metric}")


def _assert_silver_checkpoint(conn: psycopg.Connection, run_id: UUID, domain: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM event_store.silver_checkpoint WHERE run_id = %s AND silver_domain = %s",
            (str(run_id), domain),
        )
        assert cur.fetchone() is not None


def _assert_gold_checkpoint(conn: psycopg.Connection, run_id: UUID, metric: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM event_store.gold_checkpoint WHERE run_id = %s AND metric = %s",
            (str(run_id), metric),
        )
        assert cur.fetchone() is not None


def _assert_table_has_run(conn, table_name: str, run_id: UUID) -> None:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE curated_run_id = %s", (str(run_id),))
        row = cur.fetchone()
    assert row is not None
    assert int(row[0]) >= 1


def test_curated_pipeline_end_to_end():
    minio_client = _build_minio_client()
    producer = _build_kafka_producer()
    event_store = _event_store_conn()
    trino_conn = _trino_conn()
    bucket = _require_env("MINIO_BUCKET_NAME")

    now = datetime.now(timezone.utc)
    scenarios = [
        (
            CuratedScenario(
                topic="ingest.salesforce.bronze.ready.v1",
                event_type="ingest.salesforce.bronze.ready.v1",
                source=EventSource.salesforce,
                payload={"sobject": "Opportunity", "object_name": "Opportunity"},
                silver_domain="salesforce_opportunity",
                silver_table="lakehouse.silver.dim_opportunity",
                gold_metric="pipeline_conversion",
                gold_table="lakehouse.gold.kpi_pipeline_conversion",
            ),
            [
                {
                    "Id": f"006{uuid4().hex[:12]}",
                    "AccountId": f"001{uuid4().hex[:12]}",
                    "Name": "Integration Opportunity",
                    "StageName": "Prospecting",
                    "Amount": 15000.0,
                    "CloseDate": now.date().isoformat(),
                    "IsWon": False,
                    "IsClosed": False,
                    "SystemModstamp": now.isoformat(),
                }
            ],
            "bronze/source=salesforce/object=Opportunity",
        ),
        (
            CuratedScenario(
                topic="cdc.oltp.bronze.ready.v1",
                event_type="cdc.oltp.bronze.ready.v1",
                source=EventSource.cdc,
                payload={"source_table": "trading.loan"},
                silver_domain="loan",
                silver_table="lakehouse.silver.dim_loan",
                gold_metric="portfolio_health",
                gold_table="lakehouse.gold.kpi_portfolio_health",
            ),
            [
                {
                    "source_table": "trading.loan",
                    "loan_id": f"loan-{uuid4()}",
                    "account_id": str(uuid4()),
                    "status_code": "current",
                    "principal_balance": 23000.25,
                    "days_past_due": 0,
                    "source_ts_ms": int(now.timestamp() * 1000),
                    "assessed_payload": "{}",
                }
            ],
            "bronze/source=cdc/table=trading.loan",
        ),
        (
            CuratedScenario(
                topic="cdc.oltp.bronze.ready.v1",
                event_type="cdc.oltp.bronze.ready.v1",
                source=EventSource.cdc,
                payload={"source_table": "trading.loan_payment"},
                silver_domain="loan_payment",
                silver_table="lakehouse.silver.fact_loan_payment",
                gold_metric="payment_performance",
                gold_table="lakehouse.gold.kpi_payment_performance",
            ),
            [
                {
                    "source_table": "trading.loan_payment",
                    "loan_id": f"loan-{uuid4()}",
                    "payment_amount": 425.5,
                    "payment_due_date": now.date().isoformat(),
                    "payment_posted_at": now.date().isoformat(),
                    "source_ts_ms": int(now.timestamp() * 1000),
                    "assessed_payload": "{}",
                }
            ],
            "bronze/source=cdc/table=trading.loan_payment",
        ),
        (
            CuratedScenario(
                topic="ingest.excel.bronze.ready.v1",
                event_type="ingest.excel.bronze.ready.v1",
                source=EventSource.excel,
                payload={"schema_contract_id": "commission_adjustment_v1"},
                silver_domain="commission_adjustment",
                silver_table="lakehouse.silver.fact_commission_adjustment",
                gold_metric="commission_economics",
                gold_table="lakehouse.gold.kpi_commission_economics",
            ),
            [
                {
                    "advisor_id": "A12345",
                    "adjustment_date": now.date().isoformat(),
                    "adjustment_amount": 500.0,
                    "adjustment_reason": "retro_credit",
                    "currency": "USD",
                }
            ],
            "bronze/source=excel",
        ),
    ]

    try:
        for scenario, rows, prefix in scenarios:
            run_id = uuid4()
            key = (
                f"{prefix}/year={now:%Y}/month={now:%m}/day={now:%d}/"
                f"run_id={run_id}/part-0.parquet"
            )
            uri = _upload_parquet(client=minio_client, bucket=bucket, object_key=key, rows=rows)
            envelope = _scenario_envelope(scenario, run_id=run_id, uri=uri)
            _publish_envelope(producer, scenario.topic, envelope)

            silver_run_id = _poll_silver_completion(
                event_store,
                parent_run_id=str(run_id),
                silver_domain=scenario.silver_domain,
            )
            _assert_silver_checkpoint(event_store, silver_run_id, scenario.silver_domain)
            _assert_table_has_run(trino_conn, scenario.silver_table, silver_run_id)

            if scenario.gold_metric and scenario.gold_table:
                gold_run_id = _poll_gold_completion(
                    event_store,
                    parent_run_id=str(silver_run_id),
                    metric=scenario.gold_metric,
                )
                _assert_gold_checkpoint(event_store, gold_run_id, scenario.gold_metric)
                _assert_table_has_run(trino_conn, scenario.gold_table, gold_run_id)
    finally:
        event_store.close()
        trino_conn.close()
