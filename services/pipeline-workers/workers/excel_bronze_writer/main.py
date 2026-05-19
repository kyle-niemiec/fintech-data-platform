"""
Entrypoint for Excel bronze writer worker.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys

from confluent_kafka import Consumer, KafkaException

from meridian.libs.event_store import build_event_store_conn
from meridian.libs.minio_store import MinioObjectStore, build_minio_client
from meridian.libs.redpanda_events.producer import EventProducer
from meridian.libs.service_runtime import build_consumer_config, build_event_producer

from .writer import ExcelBronzeWriter, PandasParquetConverter, TOPIC_RAW_READY

logger = logging.getLogger("excel_bronze_writer")

CONSUMER_GROUP = "excel-bronze-writer-v1"


def _consumer_config() -> dict[str, str]:
    """
    Build the RedPanda consumer config for the Excel bronze writer, using credentials
    from env vars.
    """
    return build_consumer_config(
        consumer_group=CONSUMER_GROUP,
        client_id="excel-bronze-writer-consumer",
        username_var="REDPANDA_EXCEL_BRONZE_USER",
        password_var="REDPANDA_EXCEL_BRONZE_PASSWORD",
    )


def build_writer() -> tuple[ExcelBronzeWriter, Consumer, EventProducer]:
    """
    Build the ExcelBronzeWriter, along with its dependencies (RedPanda consumer and
    event producer, Minio client, and event store connection).
    """
    minio_client = build_minio_client(
        access_key_var="MINIO_TRANSFORM_USER",
        secret_key_var="MINIO_TRANSFORM_SECRET",
    )

    db = build_event_store_conn()

    producer = build_event_producer(
        client_id="excel-bronze-writer",
        username_var="REDPANDA_EXCEL_BRONZE_USER",
        password_var="REDPANDA_EXCEL_BRONZE_PASSWORD",
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
    """
    Main run loop for the Excel bronze writer. Polls for messages from the Redpanda
    topic that signals when raw data is ready, and attempts to process each message with
    the ExcelBronzeWriter.
    """
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    writer, consumer, producer = build_writer()
    shutdown = {"stop": False}

    def _handle_signal(signum, _frame) -> None:  # type: ignore[no-untyped-def]
        logger.info("signal %s received, shutting down", signum)
        shutdown["stop"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # The worker will keep running until it receives a shutdown signal.
    try:
        while not shutdown["stop"]:
            msg = consumer.poll(1.0)

            if msg is None:
                continue

            if msg.error():
                raise KafkaException(msg.error())

            # Load the message value as JSON, and log and skip if it's not valid JSON.
            try:
                envelope = json.loads(msg.value())
            except json.JSONDecodeError as exc:
                logger.error("dropping non-JSON raw.ready message at offset %s: %s", msg.offset(), exc)
                consumer.commit(message=msg, asynchronous=False)
                continue

            # Process the message with the ExcelBronzeWriter, and log any exceptions.
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

            # If the message was processed successfully, commit the offset.
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
