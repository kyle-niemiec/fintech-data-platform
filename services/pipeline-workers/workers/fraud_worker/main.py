"""Fraud worker entrypoint. Consumes cdc.oltp.raw.v1; emits cdc.oltp.assessed.v1."""

from __future__ import annotations

import logging
import os
import signal
import sys

from confluent_kafka import Consumer, KafkaException
import psycopg

from libs.platform_events.producer import EventProducer, ProducerConfig

from .handler import FraudHandler, RawMessage, decode_message

logger = logging.getLogger("fraud_worker")

TOPIC_RAW = "cdc.oltp.raw.v1"
CONSUMER_GROUP = "fraud-worker-v1"


def _consumer_config() -> dict[str, str]:
    config: dict[str, str] = {
        "bootstrap.servers": os.environ["REDPANDA_BOOTSTRAP_SERVERS"],
        "group.id": CONSUMER_GROUP,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "client.id": "fraud-worker-consumer",
    }
    security_protocol = os.environ.get("REDPANDA_SECURITY_PROTOCOL", "PLAINTEXT")
    if security_protocol != "PLAINTEXT":
        config["security.protocol"] = security_protocol
        config["sasl.mechanism"] = os.environ.get("REDPANDA_SASL_MECHANISM", "SCRAM-SHA-256")
        config["sasl.username"] = os.environ["REDPANDA_FRAUD_SERVICE_USER"]
        config["sasl.password"] = os.environ["REDPANDA_FRAUD_SERVICE_PASSWORD"]
    return config


def _build_handler() -> tuple[FraudHandler, Consumer, EventProducer]:
    oltp_conn = psycopg.connect(
        host=os.environ["OLTP_DB_HOST"],
        port=int(os.environ["OLTP_DB_PORT"]),
        dbname=os.environ["OLTP_DB"],
        user=os.environ["OLTP_APP_USER"],
        password=os.environ["OLTP_APP_PASSWORD"],
        autocommit=True,
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
            client_id="fraud-worker",
            username_var="REDPANDA_FRAUD_SERVICE_USER",
            password_var="REDPANDA_FRAUD_SERVICE_PASSWORD",
        )
    )
    consumer = Consumer(_consumer_config())
    consumer.subscribe([TOPIC_RAW])
    handler = FraudHandler(
        oltp_conn=oltp_conn,
        event_store_conn=event_store_conn,
        producer=producer,
    )
    return handler, consumer, producer


def run() -> None:
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
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())
            if msg.value() is None:
                # Tombstone; commit and move on.
                consumer.commit(message=msg, asynchronous=False)
                continue

            try:
                value = decode_message(msg.value())
            except Exception:
                logger.exception(
                    "dropping non-JSON raw message topic=%s partition=%s offset=%s",
                    msg.topic(), msg.partition(), msg.offset(),
                )
                consumer.commit(message=msg, asynchronous=False)
                continue

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

            if emitted:
                logger.info(
                    "fraud_assessed_emitted topic=%s partition=%s offset=%s",
                    msg.topic(), msg.partition(), msg.offset(),
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
        logger.exception("fraud_worker crashed")
        sys.exit(1)
