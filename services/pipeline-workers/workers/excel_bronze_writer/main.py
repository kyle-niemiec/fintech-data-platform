"""Entrypoint for Excel bronze writer worker."""

from __future__ import annotations

import io
import json
import logging
import os
import signal
import sys

from confluent_kafka import Consumer, KafkaException
from minio import Minio  # type: ignore[import-untyped]
from minio.sse import SseKMS  # type: ignore[import-untyped]
import psycopg

from libs.platform_events.producer import EventProducer, ProducerConfig

from .writer import ExcelBronzeWriter, PandasParquetConverter, TOPIC_RAW_READY, split_s3_uri

logger = logging.getLogger("excel_bronze_writer")

CONSUMER_GROUP = "excel-bronze-writer-v1"


class MinioObjectStore:
    def __init__(self, client: Minio):
        self._client = client

    def read_uri(self, uri: str) -> bytes:
        bucket, key = split_s3_uri(uri)
        obj = self._client.get_object(bucket, key)
        try:
            return obj.read()
        finally:
            obj.close()
            obj.release_conn()

    def write_uri(self, uri: str, data: bytes, *, content_type: str, kms_key_id: str) -> None:
        bucket, key = split_s3_uri(uri)
        stream = io.BytesIO(data)
        self._client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=stream,
            length=len(data),
            content_type=content_type,
            sse=SseKMS(kms_key_id, {}),
        )


def _consumer_config() -> dict[str, str]:
    config: dict[str, str] = {
        "bootstrap.servers": os.environ["REDPANDA_BOOTSTRAP_SERVERS"],
        "group.id": CONSUMER_GROUP,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "client.id": "excel-bronze-writer-consumer",
    }
    security_protocol = os.environ.get("REDPANDA_SECURITY_PROTOCOL", "PLAINTEXT")
    if security_protocol != "PLAINTEXT":
        config["security.protocol"] = security_protocol
        config["sasl.mechanism"] = os.environ.get("REDPANDA_SASL_MECHANISM", "SCRAM-SHA-256")
        config["sasl.username"] = os.environ["REDPANDA_EXCEL_BRONZE_USER"]
        config["sasl.password"] = os.environ["REDPANDA_EXCEL_BRONZE_PASSWORD"]
    return config


def build_writer() -> tuple[ExcelBronzeWriter, Consumer, EventProducer]:
    minio_client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_TRANSFORM_USER"],
        secret_key=os.environ["MINIO_TRANSFORM_SECRET"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
        region=os.environ.get("MINIO_REGION", "us-east-1"),
    )
    db = psycopg.connect(
        host=os.environ["EVENT_STORE_DB_HOST"],
        port=int(os.environ["EVENT_STORE_DB_PORT"]),
        dbname=os.environ["EVENT_STORE_DB"],
        user=os.environ["EVENT_APPEND_DB_USER"],
        password=os.environ["EVENT_APPEND_DB_PASSWORD"],
        autocommit=False,
    )
    producer = EventProducer(
        ProducerConfig.from_env(
            client_id="excel-bronze-writer",
            username_var="REDPANDA_EXCEL_BRONZE_USER",
            password_var="REDPANDA_EXCEL_BRONZE_PASSWORD",
        )
    )
    writer = ExcelBronzeWriter(
        store=MinioObjectStore(minio_client),
        converter=PandasParquetConverter(),
        producer=producer,
        db=db,
        kms_key_id=os.environ["MINIO_KMS_KEY_ID"],
    )
    consumer = Consumer(_consumer_config())
    consumer.subscribe([TOPIC_RAW_READY])
    return writer, consumer, producer


def run() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    writer, consumer, producer = build_writer()
    shutdown = {"stop": False}

    def _handle_signal(signum, _frame) -> None:  # type: ignore[no-untyped-def]
        logger.info("signal %s received, shutting down", signum)
        shutdown["stop"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        while not shutdown["stop"]:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

            try:
                envelope = json.loads(msg.value())
            except json.JSONDecodeError as exc:
                logger.error("dropping non-JSON raw.ready message at offset %s: %s", msg.offset(), exc)
                consumer.commit(message=msg, asynchronous=False)
                continue

            try:
                handled = writer.handle_raw_ready(envelope)
            except Exception:
                logger.exception(
                    "unhandled bronze writer failure topic=%s partition=%s offset=%s",
                    msg.topic(),
                    msg.partition(),
                    msg.offset(),
                )
                continue

            if handled:
                logger.info(
                    "bronze_ready_emitted run_id=%s topic=%s partition=%s offset=%s",
                    envelope.get("run_id"),
                    msg.topic(),
                    msg.partition(),
                    msg.offset(),
                )
            else:
                logger.warning(
                    "bronze write failed but run closed as failed run_id=%s",
                    envelope.get("run_id"),
                )
            consumer.commit(message=msg, asynchronous=False)
    finally:
        try:
            consumer.close()
        finally:
            producer.close()


if __name__ == "__main__":
    try:
        run()
    except Exception:
        logger.exception("excel_bronze_writer crashed")
        sys.exit(1)

