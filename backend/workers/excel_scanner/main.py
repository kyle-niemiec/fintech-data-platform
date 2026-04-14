"""Entrypoint wiring: Redpanda consumer -> ExcelScanner -> Redpanda + event-store.

Consumes MinIO S3 notifications from `ingest.excel.uploaded.v1` and dispatches
each record to the scanner. Offsets are committed only after the scanner has
persisted to the event-store and produced the verdict event.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
from contextlib import closing
from typing import Any

import clamd  # type: ignore[import-untyped]
import psycopg
from confluent_kafka import Consumer, KafkaException
from minio import Minio  # type: ignore[import-untyped]

from libs.platform_events.envelope import Envelope
from libs.platform_events.producer import EventProducer, ProducerConfig

from .scanner import (
    DEFAULT_ALLOWED_CONTENT_TYPES,
    ExcelScanner,
    ScannerConfig,
    TOPIC_UPLOADED,
)

logger = logging.getLogger("excel_scanner")

CONSUMER_GROUP = "excel-scanner-v1"


class MinioObjectStore:
    def __init__(self, client: Minio):
        self._client = client

    def stat(self, bucket: str, key: str) -> dict[str, Any]:
        obj = self._client.stat_object(bucket, key)
        return {"size": obj.size, "etag": obj.etag, "content_type": obj.content_type}

    def get_stream(self, bucket: str, key: str):
        return self._client.get_object(bucket, key)


class ProducerAdapter:
    def __init__(self, producer: EventProducer):
        self._producer = producer

    def produce(self, topic: str, envelope: Envelope, *, key: str) -> tuple[int, int]:
        return self._producer.produce(topic, envelope, key=key)


def build_scanner() -> tuple[ExcelScanner, psycopg.Connection, EventProducer, Consumer]:
    minio_endpoint = os.environ["MINIO_ENDPOINT"]
    minio_client = Minio(
        minio_endpoint,
        access_key=os.environ["MINIO_INGEST_USER"],
        secret_key=os.environ["MINIO_INGEST_SECRET"],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )

    clamd_client = clamd.ClamdNetworkSocket(
        host=os.environ["CLAMAV_HOST"],
        port=int(os.environ.get("CLAMAV_PORT", "3310")),
    )
    scan_version = clamd_client.version()

    db = psycopg.connect(
        host=os.environ["EVENT_STORE_DB_HOST"],
        port=int(os.environ["EVENT_STORE_DB_PORT"]),
        dbname=os.environ["EVENT_STORE_DB"],
        user=os.environ["EVENT_APPEND_DB_USER"],
        password=os.environ["EVENT_APPEND_DB_PASSWORD"],
        autocommit=False,
    )

    producer_config = ProducerConfig.from_env(
        client_id="excel-scanner",
        username_var="REDPANDA_EXCEL_SCANNER_USER",
        password_var="REDPANDA_EXCEL_SCANNER_PASSWORD",
    )
    producer = EventProducer(producer_config)

    consumer_config: dict[str, str] = {
        "bootstrap.servers": os.environ["REDPANDA_BOOTSTRAP_SERVERS"],
        "group.id": CONSUMER_GROUP,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "client.id": "excel-scanner-consumer",
    }
    security_protocol = os.environ.get("REDPANDA_SECURITY_PROTOCOL", "PLAINTEXT")
    if security_protocol != "PLAINTEXT":
        consumer_config["security.protocol"] = security_protocol
        consumer_config["sasl.mechanism"] = os.environ.get("REDPANDA_SASL_MECHANISM", "SCRAM-SHA-256")
        consumer_config["sasl.username"] = os.environ["REDPANDA_EXCEL_SCANNER_USER"]
        consumer_config["sasl.password"] = os.environ["REDPANDA_EXCEL_SCANNER_PASSWORD"]

    consumer = Consumer(consumer_config)
    consumer.subscribe([TOPIC_UPLOADED])

    scanner = ExcelScanner(
        object_store=MinioObjectStore(minio_client),
        clamd_client=clamd_client,
        producer=ProducerAdapter(producer),
        db=db,
        config=ScannerConfig(
            max_bytes=int(os.environ.get("EXCEL_MAX_BYTES", str(25 * 1024 * 1024))),
            allowed_content_types=DEFAULT_ALLOWED_CONTENT_TYPES,
            scan_engine_version=scan_version,
        ),
    )
    return scanner, db, producer, consumer


def run() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

    scanner, db, producer, consumer = build_scanner()
    shutdown = {"stop": False}

    def _handle_signal(signum: int, _frame: Any) -> None:
        logger.info("signal %s received, shutting down", signum)
        shutdown["stop"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    with closing(db), closing(consumer):
        while not shutdown["stop"]:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

            try:
                notification = json.loads(msg.value())
            except json.JSONDecodeError as exc:
                logger.error("skipping non-JSON message at offset %s: %s", msg.offset(), exc)
                consumer.commit(message=msg, asynchronous=False)
                continue

            records = notification.get("Records") or []
            for record in records:
                try:
                    scanner.handle_record(
                        record,
                        source_topic=msg.topic(),
                        source_partition=msg.partition(),
                        source_offset=msg.offset(),
                    )
                except Exception:
                    logger.exception(
                        "scanner failed on topic=%s partition=%s offset=%s",
                        msg.topic(),
                        msg.partition(),
                        msg.offset(),
                    )
                    raise
            consumer.commit(message=msg, asynchronous=False)

        producer.close()


if __name__ == "__main__":
    try:
        run()
    except Exception:
        logger.exception("excel_scanner crashed")
        sys.exit(1)
