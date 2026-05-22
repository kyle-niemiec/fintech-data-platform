"""
Shared runtime helpers for pipeline worker entrypoints.
"""

from __future__ import annotations

import os

from meridian.libs.redpanda_events.producer import EventProducer, ProducerConfig


def build_consumer_config(
    *,
    consumer_group: str,
    client_id: str,
    username_var: str,
    password_var: str,
) -> dict[str, str]:
    """
    Build a Redpanda consumer config dict, using credentials from env vars.
    """
    config: dict[str, str] = {
        "bootstrap.servers": os.environ["REDPANDA_BOOTSTRAP_SERVERS"],
        "group.id": consumer_group,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "client.id": client_id,
    }

    security_protocol = os.environ.get("REDPANDA_SECURITY_PROTOCOL", "PLAINTEXT")

    if security_protocol != "PLAINTEXT":
        config["security.protocol"] = security_protocol
        config["sasl.mechanism"] = os.environ.get("REDPANDA_SASL_MECHANISM", "SCRAM-SHA-256")
        config["sasl.username"] = os.environ[username_var]
        config["sasl.password"] = os.environ[password_var]

    return config


def build_event_producer(
    *,
    client_id: str,
    username_var: str,
    password_var: str,
) -> EventProducer:
    """
    Build an EventProducer, using credentials from env vars.
    """
    return EventProducer(
        ProducerConfig.from_env(
            client_id=client_id,
            username_var=username_var,
            password_var=password_var,
        )
    )
