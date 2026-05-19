"""Entrypoint for the Salesforce bronze writer worker."""

from __future__ import annotations

import json
import logging
import os
import signal
import sys

from confluent_kafka import Consumer, KafkaException

from libs.platform_events.producer import EventProducer
from libs.platform_storage import MinioObjectStore
from libs.platform_worker_runtime import (
    build_consumer_config,
    build_event_producer,
    build_event_store_conn,
    build_minio_client,
)

from .writer import (
    RawReadyMessage,
    SalesforceBronzeWriter,
    TOPIC_RAW_READY,
)

logger = logging.getLogger("salesforce_bronze_writer")

CONSUMER_GROUP = "salesforce-bronze-writer-v1"


def _consumer_config() -> dict[str, str]:
    return build_consumer_config(
        consumer_group=CONSUMER_GROUP,
        client_id="salesforce-bronze-writer-consumer",
        username_var="REDPANDA_SALESFORCE_BRONZE_USER",
        password_var="REDPANDA_SALESFORCE_BRONZE_PASSWORD",
    )


def build_writer() -> tuple[SalesforceBronzeWriter, Consumer, EventProducer]:
    minio_client = build_minio_client(
        access_key_var="MINIO_TRANSFORM_USER",
        secret_key_var="MINIO_TRANSFORM_SECRET",
    )
    db = build_event_store_conn()
    producer = build_event_producer(
        client_id="salesforce-bronze-writer",
        username_var="REDPANDA_SALESFORCE_BRONZE_USER",
        password_var="REDPANDA_SALESFORCE_BRONZE_PASSWORD",
    )
    writer = SalesforceBronzeWriter(
        store=MinioObjectStore(minio_client),
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
            except json.JSONDecodeError:
                logger.exception("dropping non-JSON raw.ready at offset %s", msg.offset())
                consumer.commit(message=msg, asynchronous=False)
                continue

            raw = RawReadyMessage(
                envelope=envelope,
                kafka_topic=msg.topic(),
                kafka_partition=msg.partition(),
                kafka_offset=msg.offset(),
            )
            try:
                handled = writer.handle_raw_ready(raw)
            except Exception:
                logger.exception(
                    "unhandled bronze writer failure topic=%s partition=%s offset=%s",
                    msg.topic(), msg.partition(), msg.offset(),
                )
                continue

            if handled:
                logger.info(
                    "salesforce_bronze_ready run_id=%s sobject=%s offset=%s",
                    envelope.get("run_id"),
                    (envelope.get("payload") or {}).get("sobject"),
                    msg.offset(),
                )
            else:
                logger.warning(
                    "salesforce bronze write failed; run closed as failed run_id=%s",
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
        logger.exception("salesforce_bronze_writer crashed")
        sys.exit(1)
