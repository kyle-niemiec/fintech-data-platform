"""Consumer-group lag via the Kafka protocol.

Lag is a Kafka-protocol concept, not part of the Redpanda Admin HTTP API, so we
read it the same way `make consumer-lag` (`rpk group describe`) does: committed
group offsets via the admin client, and per-partition high watermarks via a
consumer. `lag = high_watermark - committed_offset`.
"""

from __future__ import annotations

from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any

from confluent_kafka import (
    Consumer,
    ConsumerGroupTopicPartitions,
    KafkaException,
    TopicPartition,
)
from confluent_kafka.admin import AdminClient

from config import settings

# Platform consumer groups we surface on the Metrics page.
KNOWN_GROUPS = [
    "excel-scanner-v1",
    "excel-trigger-v1",
    "excel-bronze-writer-v1",
    "cdc-fraud-worker-v1",
    "cdc-bronze-writer-v1",
    "salesforce-bronze-writer-v1",
    "airflow-curated-silver-v1",
    "airflow-curated-gold-v1",
]

_PROBE_GROUP = "ui-api-lag-probe"


class ConsumerLagUnavailable(Exception):
    """Redpanda could not be reached or queried for consumer-group lag."""


def _client_config() -> dict[str, str]:
    config: dict[str, str] = {
        "bootstrap.servers": settings.redpanda_bootstrap_servers,
    }
    if settings.redpanda_security_protocol != "PLAINTEXT":
        config["security.protocol"] = settings.redpanda_security_protocol
        config["sasl.mechanism"] = settings.redpanda_sasl_mechanism
        config["sasl.username"] = settings.redpanda_ui_service_user
        config["sasl.password"] = settings.redpanda_ui_service_password
    return config


def fetch_consumer_lag(
    *,
    admin: Any | None = None,
    consumer: Any | None = None,
    groups: list[str] = KNOWN_GROUPS,
    timeout: float = 5.0,
) -> list[dict[str, Any]]:
    """Return per-partition lag for the known consumer groups.

    `admin`/`consumer` are injectable for tests; in production they are built
    from settings. Raises `ConsumerLagUnavailable` only when the broker itself
    cannot be reached — a missing/empty group (e.g. a pipeline that has not run
    yet) is skipped, not an error.
    """
    config = _client_config()
    if admin is None:
        admin = AdminClient(config)

    # Connectivity probe: distinguishes "broker down" (-> 503) from a group that
    # simply has no committed offsets yet (-> skip).
    try:
        admin.list_topics(timeout=timeout)
    except KafkaException as exc:
        raise ConsumerLagUnavailable(str(exc)) from exc

    owns_consumer = consumer is None
    if consumer is None:
        consumer = Consumer({**config, "group.id": _PROBE_GROUP, "enable.auto.commit": False})

    items: list[dict[str, Any]] = []
    try:
        # librdkafka accepts only one consumer group per request, so query each
        # group individually.
        for group in groups:
            futures = admin.list_consumer_group_offsets(
                [ConsumerGroupTopicPartitions(group, None)]
            )
            future = next(iter(futures.values()))
            try:
                result = future.result(timeout=timeout)
            except (KafkaException, FutureTimeoutError):
                # Group absent or not yet describable; skip rather than fail all.
                continue
            for tp in result.topic_partitions or []:
                committed = tp.offset
                if committed is None or committed < 0:
                    continue  # no committed offset for this partition
                try:
                    _, high = consumer.get_watermark_offsets(
                        TopicPartition(tp.topic, tp.partition),
                        timeout=timeout,
                        cached=False,
                    )
                except KafkaException:
                    continue  # topic/partition gone; skip this entry
                items.append(
                    {
                        "group": group,
                        "topic": tp.topic,
                        "partition": tp.partition,
                        "current_offset": committed,
                        "log_end_offset": high,
                        "lag": max(0, high - committed),
                    }
                )
    finally:
        if owns_consumer:
            consumer.close()

    items.sort(key=lambda i: (i["group"], i["topic"], i["partition"]))
    return items
