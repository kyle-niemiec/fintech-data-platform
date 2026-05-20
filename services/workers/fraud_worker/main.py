"""
Fraud worker entrypoint.

    Consumes:   cdc.oltp.raw.v1
    Emits:      cdc.oltp.assessed.v1

"""

from __future__ import annotations

import logging
import os
import signal
import sys

from confluent_kafka import Consumer, KafkaException
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from meridian.libs.event_store import ManagedConnection, open_event_store_conn
from meridian.libs.redpanda_events.producer import EventProducer
from meridian.libs.service_runtime import build_consumer_config, build_event_producer

from .handler import FraudHandler, RawMessage, decode_message

logger = logging.getLogger("fraud_worker")

TOPIC_RAW = "cdc.oltp.raw.v1"
CONSUMER_GROUP = "fraud-worker-v1"


def _consumer_config() -> dict[str, str]:
    """
    Build the configuration for the Redpanda consumer, including credentials from environment variables.

    TECH-DEBT: Reused code for building platform services should be consolidated using factories.
    """
    return build_consumer_config(
        consumer_group=CONSUMER_GROUP,
        client_id="fraud-worker-consumer",
        username_var="REDPANDA_FRAUD_SERVICE_USER",
        password_var="REDPANDA_FRAUD_SERVICE_PASSWORD",
    )


def _build_oltp_conn() -> ManagedConnection:
    """
    Build a connection to the OLTP database using credentials from environment variables.
    """
    url = URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["OLTP_APP_USER"],
        password=os.environ["OLTP_APP_PASSWORD"],
        host=os.environ["OLTP_DB_HOST"],
        port=int(os.environ["OLTP_DB_PORT"]),
        database=os.environ["OLTP_DB"],
    )

    engine = create_engine(url)
    return ManagedConnection(engine=engine, connection=engine.connect())


def _build_handler() -> tuple[FraudHandler, Consumer, EventProducer]:
    """
    Build the FraudHandler along with its dependencies (OLTP connection, event store connection, and event producer).
    """
    oltp_conn = _build_oltp_conn()

    producer = build_event_producer(
        client_id="fraud-worker",
        username_var="REDPANDA_FRAUD_SERVICE_USER",
        password_var="REDPANDA_FRAUD_SERVICE_PASSWORD",
    )

    consumer = Consumer(_consumer_config())
    consumer.subscribe([TOPIC_RAW])

    handler = FraudHandler(
        oltp_conn=oltp_conn,
        event_store_connection_factory=open_event_store_conn,
        producer=producer,
    )

    return handler, consumer, producer


def run() -> None:
    """
    Main run loop for the fraud worker. Polls for messages from Redpanda, processes
    them using the handler, and commits offsets.
    """
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    handler, consumer, producer = _build_handler()
    shutdown = {"stop": False}

    def _handle_signal(signum, _frame) -> None:  # type: ignore[no-untyped-def]
        logger.info("signal %s received, shutting down", signum)
        shutdown["stop"] = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        while not shutdown["stop"]:
            # Poll for a message
            msg = consumer.poll(1.0)

            if msg is None:
                continue

            if msg.error():
                raise KafkaException(msg.error())

            if msg.value() is None:
                # Tombstone; commit and move on.
                consumer.commit(message=msg, asynchronous=False)
                continue

            # Process the message value
            try:
                value = decode_message(msg.value())
            except Exception:
                logger.exception(
                    "dropping non-JSON raw message topic=%s partition=%s offset=%s",
                    msg.topic(), msg.partition(), msg.offset(),
                )
                consumer.commit(message=msg, asynchronous=False)
                continue

            # Build the envelope for the handler
            raw = RawMessage(
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
                value=value,
                key=msg.key().decode("utf-8") if msg.key() else None,
            )

            try:
                emitted = handler.handle(raw)
            except Exception:
                logger.exception(
                    "fraud handler failed; leaving offset uncommitted topic=%s partition=%s offset=%s",
                    msg.topic(), msg.partition(), msg.offset(),
                )
                # No commit -> Kafka redelivers.
                continue

            # Log any emitted events
            if emitted:
                logger.info(
                    "fraud_assessed_emitted topic=%s partition=%s offset=%s",
                    msg.topic(), msg.partition(), msg.offset(),
                )

            # Commit the offset after processing
            consumer.commit(message=msg, asynchronous=False)
    finally:
        try:
            consumer.close()
        finally:
            try:
                producer.close()
            finally:
                handler.oltp_conn.close()


if __name__ == "__main__":
    try:
        run()
    except Exception:
        logger.exception("fraud_worker crashed")
        sys.exit(1)
