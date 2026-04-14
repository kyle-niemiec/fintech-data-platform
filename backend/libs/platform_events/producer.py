"""Thin confluent-kafka producer wrapper for platform events.

Partitioning follows docs/event-contracts.md: ingest.*/pipeline.* keyed by
run_id, cdc.* keyed by (source_table, business_key), ui.alert.* by run_id.
Callers pass the key explicitly; this module does not infer it.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from confluent_kafka import Producer

from .envelope import Envelope

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProducerConfig:
    bootstrap_servers: str
    sasl_username: Optional[str] = None
    sasl_password: Optional[str] = None
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: str = "SCRAM-SHA-256"
    client_id: str = "platform-events"

    @classmethod
    def from_env(
        cls,
        *,
        client_id: str,
        username_var: str | None = None,
        password_var: str | None = None,
    ) -> "ProducerConfig":
        return cls(
            bootstrap_servers=os.environ["REDPANDA_BOOTSTRAP_SERVERS"],
            sasl_username=os.environ.get(username_var) if username_var else None,
            sasl_password=os.environ.get(password_var) if password_var else None,
            security_protocol=os.environ.get("REDPANDA_SECURITY_PROTOCOL", "PLAINTEXT"),
            sasl_mechanism=os.environ.get("REDPANDA_SASL_MECHANISM", "SCRAM-SHA-256"),
            client_id=client_id,
        )

    def to_librdkafka(self) -> dict[str, str]:
        conf: dict[str, str] = {
            "bootstrap.servers": self.bootstrap_servers,
            "client.id": self.client_id,
            "enable.idempotence": "true",
            "acks": "all",
            "compression.type": "zstd",
        }
        if self.security_protocol != "PLAINTEXT":
            conf["security.protocol"] = self.security_protocol
            if self.sasl_username and self.sasl_password:
                conf["sasl.mechanism"] = self.sasl_mechanism
                conf["sasl.username"] = self.sasl_username
                conf["sasl.password"] = self.sasl_password
        return conf


class EventProducer:
    """Synchronous produce-and-flush wrapper.

    Workers emit one event per logical step; throughput is low enough that
    flushing per-produce keeps the at-least-once contract obvious without
    coupling callers to delivery callbacks.
    """

    def __init__(self, config: ProducerConfig):
        self._producer = Producer(config.to_librdkafka())

    def produce(self, topic: str, envelope: Envelope, *, key: str) -> tuple[int, int]:
        """Produce and return (partition, offset) once the broker acks."""
        result: dict[str, Any] = {}

        def _ack(err: Any, msg: Any) -> None:
            if err is not None:
                result["error"] = str(err)
                return
            result["partition"] = msg.partition()
            result["offset"] = msg.offset()

        self._producer.produce(
            topic=topic,
            key=key.encode("utf-8"),
            value=envelope.to_wire(),
            headers=[
                ("event_id", str(envelope.event_id).encode("utf-8")),
                ("schema_version", envelope.schema_version.encode("utf-8")),
                ("trace_id", str(envelope.trace_id).encode("utf-8")),
            ],
            on_delivery=_ack,
        )
        remaining = self._producer.flush(timeout=10.0)
        if remaining > 0:
            raise RuntimeError(f"Redpanda flush left {remaining} messages undelivered")
        if "error" in result:
            raise RuntimeError(f"Redpanda produce failed: {result['error']}")
        logger.info(
            "event_produced topic=%s event_type=%s event_id=%s run_id=%s partition=%s offset=%s",
            topic,
            envelope.event_type,
            envelope.event_id,
            envelope.run_id,
            result["partition"],
            result["offset"],
        )
        return result["partition"], result["offset"]

    def close(self) -> None:
        self._producer.flush(timeout=10.0)
