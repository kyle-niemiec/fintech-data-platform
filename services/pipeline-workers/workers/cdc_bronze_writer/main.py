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

from confluent_kafka import Consumer, KafkaException
from minio import Minio  # type: ignore[import-untyped]
from minio.sse import SseKMS  # type: ignore[import-untyped]
import psycopg

from libs.platform_events.event_store import (
    append_cdc_checkpoint,
    append_event,
    close_run,
    open_run,
)
from libs.platform_events.envelope import PipelineClass, PipelineName
from libs.platform_events.producer import EventProducer, ProducerConfig

from .writer import (
    AssessedRecord,
    CdcBronzeWriter,
    EmittedBatch,
    SOURCE_SYSTEM,
    TOPIC_ASSESSED,
    TOPIC_BRONZE_READY,
    TRIGGER_TYPE,
    INITIATOR,
)

logger = logging.getLogger("cdc_bronze_writer")

CONSUMER_GROUP = "cdc-bronze-writer-v1"


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
        producer=producer,
        kms_key_id=os.environ["MINIO_KMS_KEY_ID"],
        bucket=os.environ["MINIO_BUCKET_NAME"],
    )
    consumer = Consumer(_consumer_config())
    consumer.subscribe([TOPIC_ASSESSED])
    return writer, consumer, producer, event_store_conn


def _persist_batch(conn: psycopg.Connection, emitted: EmittedBatch) -> None:
    """Open a run, append the bronze_ready event, record checkpoint, close run."""
    run_id = open_run(
        conn,
        run_id=emitted.run_id,
        pipeline_class=PipelineClass.ingestion,
        pipeline_name=PipelineName.cdc_ingestion,
        source_system=SOURCE_SYSTEM,
        trigger_type=TRIGGER_TYPE,
        trigger_event_ref=emitted.trigger_event_ref,
        initiator=INITIATOR,
    )
    with conn.transaction():
        append_event(
            conn,
            emitted.envelope,
            topic=TOPIC_BRONZE_READY,
            partition=emitted.produce_partition,
            kafka_offset=emitted.produce_offset,
        )
        append_cdc_checkpoint(
            conn,
            run_id=run_id,
            source_table=emitted.source_table,
            lsn_start=emitted.first_lsn,
            lsn_end=emitted.last_lsn,
            kafka_partition=emitted.kafka_partition,
            offset_start=emitted.offset_start,
            offset_end=emitted.offset_end,
            record_count=emitted.record_count,
        )
        close_run(conn, run_id, status="completed")


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
        emitted_batches = writer.write_and_emit(flush)
        for emitted in emitted_batches:
            _persist_batch(event_store_conn, emitted)
            logger.info(
                "cdc_bronze_ready run_id=%s table=%s records=%s first_lsn=%s last_lsn=%s",
                emitted.run_id,
                emitted.source_table,
                emitted.record_count,
                emitted.first_lsn,
                emitted.last_lsn,
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
