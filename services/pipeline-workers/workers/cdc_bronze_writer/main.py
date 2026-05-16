"""CDC bronze writer entrypoint.

Consumes cdc.oltp.assessed.v1 in batches, flushes to MinIO as Parquet,
emits cdc.oltp.bronze.ready.v1, and records a row in event_store.cdc_checkpoint.
"""

from __future__ import annotations

import io
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from uuid import UUID

from confluent_kafka import Consumer, KafkaException
from minio import Minio  # type: ignore[import-untyped]
from minio.sse import SseKMS  # type: ignore[import-untyped]
import psycopg

from libs.platform_events.event_store import (
    append_cdc_checkpoint,
    append_event,
    close_run,
    open_run,
    raise_alert,
)
from libs.platform_events.envelope import Envelope, EventSource, PipelineClass, PipelineName
from libs.platform_events.producer import EventProducer, ProducerConfig

from .writer import (
    AssessedRecord,
    CdcBronzeWriter,
    PreparedBatch,
    SOURCE_SYSTEM,
    TOPIC_ASSESSED,
    TOPIC_BRONZE_READY,
    TRIGGER_TYPE,
    INITIATOR,
)

logger = logging.getLogger("cdc_bronze_writer")

CONSUMER_GROUP = "cdc-bronze-writer-v1"
TOPIC_INTERNAL = "event_store.internal"
TOPIC_BRONZE_PREPARED = "cdc.oltp.bronze.prepared.v1"


def _consumer_config() -> dict[str, str]:
    config: dict[str, str] = {
        "bootstrap.servers": os.environ["REDPANDA_BOOTSTRAP_SERVERS"],
        "group.id": CONSUMER_GROUP,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "client.id": "cdc-bronze-writer-consumer",
    }
    security_protocol = os.environ.get("REDPANDA_SECURITY_PROTOCOL", "PLAINTEXT")
    if security_protocol != "PLAINTEXT":
        config["security.protocol"] = security_protocol
        config["sasl.mechanism"] = os.environ.get("REDPANDA_SASL_MECHANISM", "SCRAM-SHA-256")
        config["sasl.username"] = os.environ["REDPANDA_FRAUD_SERVICE_USER"]
        config["sasl.password"] = os.environ["REDPANDA_FRAUD_SERVICE_PASSWORD"]
    return config


class MinioObjectStore:
    def __init__(self, client: Minio):
        self._client = client

    def write_uri(self, uri: str, data: bytes, *, content_type: str, kms_key_id: str) -> None:
        from urllib.parse import urlparse
        parsed = urlparse(uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        self._client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
            sse=SseKMS(kms_key_id, {}),
        )


def _build() -> tuple[CdcBronzeWriter, Consumer, EventProducer, psycopg.Connection]:
    minio_client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_TRANSFORM_USER"],
        secret_key=os.environ["MINIO_TRANSFORM_SECRET"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
        region=os.environ.get("MINIO_REGION", "us-east-1"),
    )
    event_store_conn = psycopg.connect(
        host=os.environ["EVENT_STORE_DB_HOST"],
        port=int(os.environ["EVENT_STORE_DB_PORT"]),
        dbname=os.environ["EVENT_STORE_DB"],
        user=os.environ["EVENT_APPEND_DB_USER"],
        password=os.environ["EVENT_APPEND_DB_PASSWORD"],
        autocommit=False,
    )
    producer = EventProducer(
        ProducerConfig.from_env(
            client_id="cdc-bronze-writer",
            username_var="REDPANDA_FRAUD_SERVICE_USER",
            password_var="REDPANDA_FRAUD_SERVICE_PASSWORD",
        )
    )
    writer = CdcBronzeWriter(
        store=MinioObjectStore(minio_client),
        kms_key_id=os.environ["MINIO_KMS_KEY_ID"],
        bucket=os.environ["MINIO_BUCKET_NAME"],
    )
    consumer = Consumer(_consumer_config())
    consumer.subscribe([TOPIC_ASSESSED])
    return writer, consumer, producer, event_store_conn


def _prepare_batch_run(
    conn: psycopg.Connection,
    prepared: PreparedBatch,
) -> tuple[UUID, Envelope]:
    """Persist parent pipeline_run + internal prepared event before Kafka publish."""
    with conn.transaction():
        run_id = open_run(
            conn,
            run_id=prepared.run_id,
            pipeline_class=PipelineClass.ingestion,
            pipeline_name=PipelineName.cdc_bronze_write,
            source_system=SOURCE_SYSTEM,
            trigger_type=TRIGGER_TYPE,
            trigger_event_ref=prepared.trigger_event_ref,
            initiator=INITIATOR,
            status="running",
        )

        internal_envelope = Envelope.build(
            event_type=TOPIC_BRONZE_PREPARED,
            source=EventSource.cdc,
            run_id=run_id,
            pipeline_class=PipelineClass.ingestion,
            pipeline_name=PipelineName.cdc_bronze_write,
            trigger_event_ref=prepared.trigger_event_ref,
            trace_id=prepared.envelope.trace_id,
            payload={
                "stage": "bronze",
                "state": "prepared",
                "source_table": prepared.source_table,
                "output_uris": [prepared.bronze_uri],
                "record_count": prepared.record_count,
                "first_lsn": prepared.first_lsn,
                "last_lsn": prepared.last_lsn,
            },
        )
        append_event(
            conn,
            internal_envelope,
            topic=TOPIC_INTERNAL,
            partition=-1,
            kafka_offset=-1,
        )

    ready_envelope = prepared.envelope.model_copy(update={"run_id": run_id})
    return run_id, ready_envelope


def _finalize_published_batch(
    conn: psycopg.Connection,
    *,
    prepared: PreparedBatch,
    run_id: UUID,
    ready_envelope: Envelope,
    produce_partition: int,
    produce_offset: int,
) -> None:
    """Persist published bronze-ready event + checkpoint and close run completed."""
    with conn.transaction():
        append_event(
            conn,
            ready_envelope,
            topic=TOPIC_BRONZE_READY,
            partition=produce_partition,
            kafka_offset=produce_offset,
        )
        append_cdc_checkpoint(
            conn,
            run_id=run_id,
            source_table=prepared.source_table,
            lsn_start=prepared.first_lsn,
            lsn_end=prepared.last_lsn,
            kafka_partition=prepared.kafka_partition,
            offset_start=prepared.offset_start,
            offset_end=prepared.offset_end,
            record_count=prepared.record_count,
        )
        close_run(conn, run_id, status="completed")


def _mark_batch_failed(
    conn: psycopg.Connection,
    *,
    run_id: UUID,
    prepared: PreparedBatch,
    error: Exception,
) -> None:
    """Record explicit failure mode for publish/finalize errors."""
    with conn.transaction():
        raise_alert(
            conn,
            run_id=run_id,
            severity="high",
            category="cdc_bronze_ready_publish_failed",
            summary="CDC bronze-ready publish failed",
            details={
                "error": str(error),
                "source_table": prepared.source_table,
                "trigger_event_ref": prepared.trigger_event_ref,
                "output_uri": prepared.bronze_uri,
            },
            occurred_at=datetime.now(timezone.utc),
        )
        close_run(conn, run_id, status="failed")


def run() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    writer, consumer, producer, event_store_conn = _build()
    max_records = int(os.environ.get("CDC_BATCH_MAX_RECORDS", "100"))
    max_seconds = int(os.environ.get("CDC_BATCH_MAX_SECONDS", "30"))

    shutdown = {"stop": False}

    def _handle_signal(signum, _frame) -> None:  # type: ignore[no-untyped-def]
        logger.info("signal %s received, shutting down", signum)
        shutdown["stop"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    pending: list[AssessedRecord] = []
    pending_msgs: list = []
    batch_started_at = time.monotonic()

    def _flush() -> None:
        nonlocal pending, pending_msgs, batch_started_at
        if not pending:
            batch_started_at = time.monotonic()
            return
        flush = writer.build_flush(pending)
        prepared_batches = writer.write_batches(flush)
        for prepared in prepared_batches:
            effective_run_id = None
            try:
                effective_run_id, ready_envelope = _prepare_batch_run(
                    event_store_conn,
                    prepared,
                )
                produce_partition, produce_offset = producer.produce(
                    TOPIC_BRONZE_READY, ready_envelope, key=f"{prepared.source_table}:{effective_run_id}"
                )
                _finalize_published_batch(
                    event_store_conn,
                    prepared=prepared,
                    run_id=effective_run_id,
                    ready_envelope=ready_envelope,
                    produce_partition=produce_partition,
                    produce_offset=produce_offset,
                )
            except Exception as exc:
                if effective_run_id is not None:
                    try:
                        _mark_batch_failed(
                            event_store_conn,
                            run_id=effective_run_id,
                            prepared=prepared,
                            error=exc,
                        )
                    except Exception:
                        logger.exception(
                            "failed to record publish failure run_id=%s table=%s",
                            effective_run_id,
                            prepared.source_table,
                        )
                raise

            logger.info(
                "cdc_bronze_ready run_id=%s table=%s records=%s first_lsn=%s last_lsn=%s",
                effective_run_id,
                prepared.source_table,
                prepared.record_count,
                prepared.first_lsn,
                prepared.last_lsn,
            )
        # Commit the last message in the batch; that advances the group offset
        # past every record in `pending`.
        last_msg = pending_msgs[-1]
        consumer.commit(message=last_msg, asynchronous=False)
        pending = []
        pending_msgs = []
        batch_started_at = time.monotonic()

    try:
        while not shutdown["stop"]:
            timeout = max(0.1, max_seconds - (time.monotonic() - batch_started_at))
            msg = consumer.poll(min(1.0, timeout))
            if msg is not None:
                if msg.error():
                    raise KafkaException(msg.error())
                if msg.value() is None:
                    consumer.commit(message=msg, asynchronous=False)
                else:
                    try:
                        envelope = json.loads(msg.value())
                    except json.JSONDecodeError:
                        logger.exception(
                            "dropping non-JSON assessed message offset=%s", msg.offset()
                        )
                        consumer.commit(message=msg, asynchronous=False)
                    else:
                        pending.append(AssessedRecord(
                            envelope=envelope,
                            kafka_topic=msg.topic(),
                            kafka_partition=msg.partition(),
                            kafka_offset=msg.offset(),
                        ))
                        pending_msgs.append(msg)

            if pending and (
                len(pending) >= max_records
                or (time.monotonic() - batch_started_at) >= max_seconds
            ):
                try:
                    _flush()
                except Exception:
                    logger.exception("flush failed; batch will be replayed")
                    try:
                        event_store_conn.rollback()
                    except Exception:
                        pass
                    # Drop pending so the same offsets replay from Kafka.
                    pending = []
                    pending_msgs = []
                    batch_started_at = time.monotonic()
    finally:
        try:
            consumer.close()
        finally:
            producer.close()


if __name__ == "__main__":
    try:
        run()
    except Exception:
        logger.exception("cdc_bronze_writer crashed")
        sys.exit(1)
