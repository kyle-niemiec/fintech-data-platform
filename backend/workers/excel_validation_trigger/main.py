"""Kafka consumer that triggers the Airflow excel_validation DAG."""

from __future__ import annotations

import json
import logging
import os
import signal
import sys

from confluent_kafka import Consumer, KafkaException
import requests

from .trigger import build_dag_run_id, build_dag_run_payload, trigger_dag_run

logger = logging.getLogger("excel_validation_trigger")

TOPIC_SCAN_PASS = "ingest.excel.scanned.pass.v1"
CONSUMER_GROUP = "excel-validation-trigger-v1"
DAG_ID = "excel_validation"


def _consumer_config() -> dict[str, str]:
    config: dict[str, str] = {
        "bootstrap.servers": os.environ["REDPANDA_BOOTSTRAP_SERVERS"],
        "group.id": CONSUMER_GROUP,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "client.id": "excel-validation-trigger-consumer",
    }
    security_protocol = os.environ.get("REDPANDA_SECURITY_PROTOCOL", "PLAINTEXT")
    if security_protocol != "PLAINTEXT":
        config["security.protocol"] = security_protocol
        config["sasl.mechanism"] = os.environ.get("REDPANDA_SASL_MECHANISM", "SCRAM-SHA-256")
        config["sasl.username"] = os.environ["REDPANDA_AIRFLOW_USER"]
        config["sasl.password"] = os.environ["REDPANDA_AIRFLOW_PASSWORD"]
    return config


def run() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    airflow_base_url = os.environ.get("AIRFLOW_BASE_URL", "http://airflow_webserver:8080")
    airflow_user = os.environ["AIRFLOW_API_USER"]
    airflow_password = os.environ["AIRFLOW_API_PASSWORD"]

    session = requests.Session()
    session.auth = (airflow_user, airflow_password)

    consumer = Consumer(_consumer_config())
    consumer.subscribe([TOPIC_SCAN_PASS])

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
                conf = build_dag_run_payload(envelope)
                run_id = str(envelope["run_id"])
                dag_run_id = build_dag_run_id(run_id)
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.error(
                    "dropping malformed scanned.pass message at offset %s: %s",
                    msg.offset(),
                    exc,
                )
                consumer.commit(message=msg, asynchronous=False)
                continue

            try:
                trigger_dag_run(
                    session=session,
                    airflow_base_url=airflow_base_url,
                    dag_id=DAG_ID,
                    dag_run_id=dag_run_id,
                    conf=conf,
                )
            except Exception:
                logger.exception(
                    "failed to trigger DAG for run_id=%s topic=%s partition=%s offset=%s",
                    run_id,
                    msg.topic(),
                    msg.partition(),
                    msg.offset(),
                )
                continue

            consumer.commit(message=msg, asynchronous=False)
            logger.info(
                "dag_triggered dag_id=%s dag_run_id=%s run_id=%s topic=%s partition=%s offset=%s",
                DAG_ID,
                dag_run_id,
                run_id,
                msg.topic(),
                msg.partition(),
                msg.offset(),
            )
    finally:
        try:
            consumer.close()
        finally:
            session.close()


if __name__ == "__main__":
    try:
        run()
    except Exception:
        logger.exception("excel_validation_trigger crashed")
        sys.exit(1)

