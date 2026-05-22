"""Unit coverage for Kafka-protocol consumer-lag computation.

The admin client and consumer are injected as fakes so the lag math, group
filtering, and broker-unavailable handling are tested without a live Redpanda.
"""

from __future__ import annotations

import os

# config.Settings has required fields; provide them before importing app modules.
os.environ.setdefault("EVENT_STORE_DB", "test_event_store")
os.environ.setdefault("EVENT_QUERY_DB_USER", "test_reader")
os.environ.setdefault("EVENT_QUERY_DB_PASSWORD", "test_password")

import pytest
from confluent_kafka import (
    ConsumerGroupTopicPartitions,
    KafkaException,
    TopicPartition,
)

from services.consumer_lag import ConsumerLagUnavailable, fetch_consumer_lag


class _Future:
    def __init__(self, result=None, error: Exception | None = None):
        self._result = result
        self._error = error

    def result(self, timeout=None):
        if self._error is not None:
            raise self._error
        return self._result


class _FakeAdmin:
    """Returns canned committed offsets; can simulate an unreachable broker."""

    def __init__(self, offsets_by_group, *, reachable: bool = True):
        self._offsets = offsets_by_group
        self._reachable = reachable
        self.requested_groups: list[str] = []
        self.request_sizes: list[int] = []

    def list_topics(self, timeout=None):
        if not self._reachable:
            raise KafkaException("broker down")
        return object()

    def list_consumer_group_offsets(self, requests):
        # librdkafka rejects more than one group per request; the service must
        # call this once per group.
        self.request_sizes.append(len(requests))
        futures = {}
        for req in requests:
            group = req.group_id
            self.requested_groups.append(group)
            entry = self._offsets.get(group)
            if isinstance(entry, Exception):
                futures[group] = _Future(error=entry)
            else:
                futures[group] = _Future(
                    result=ConsumerGroupTopicPartitions(group, entry or [])
                )
        return futures


class _FakeConsumer:
    """Returns canned (low, high) watermarks keyed by (topic, partition)."""

    def __init__(self, watermarks):
        self._watermarks = watermarks
        self.closed = False

    def get_watermark_offsets(self, tp, timeout=None, cached=False):
        key = (tp.topic, tp.partition)
        if key not in self._watermarks:
            raise KafkaException("unknown partition")
        return self._watermarks[key]

    def close(self):
        self.closed = True


def test_fetch_consumer_lag_computes_lag_and_sorts():
    admin = _FakeAdmin(
        {
            "cdc-bronze-writer-v1": [TopicPartition("cdc.events", 0, 80)],
            "excel-scanner-v1": [TopicPartition("excel.uploaded", 0, 50)],
        }
    )
    consumer = _FakeConsumer(
        {
            ("cdc.events", 0): (0, 100),
            ("excel.uploaded", 0): (0, 50),
        }
    )

    rows = fetch_consumer_lag(
        admin=admin,
        consumer=consumer,
        groups=["cdc-bronze-writer-v1", "excel-scanner-v1"],
    )

    assert [r["group"] for r in rows] == ["cdc-bronze-writer-v1", "excel-scanner-v1"]
    cdc = rows[0]
    assert cdc["current_offset"] == 80
    assert cdc["log_end_offset"] == 100
    assert cdc["lag"] == 20
    assert rows[1]["lag"] == 0  # caught up
    # Regression guard: each offsets request must carry exactly one group.
    assert admin.request_sizes == [1, 1]


def test_skips_partition_without_committed_offset():
    admin = _FakeAdmin(
        {"cdc-bronze-writer-v1": [TopicPartition("cdc.events", 0, -1001)]}
    )
    consumer = _FakeConsumer({("cdc.events", 0): (0, 100)})
    rows = fetch_consumer_lag(
        admin=admin, consumer=consumer, groups=["cdc-bronze-writer-v1"]
    )
    assert rows == []


def test_skips_absent_group_without_failing_all():
    admin = _FakeAdmin(
        {
            "missing-group": KafkaException("group not found"),
            "cdc-bronze-writer-v1": [TopicPartition("cdc.events", 0, 90)],
        }
    )
    consumer = _FakeConsumer({("cdc.events", 0): (0, 100)})
    rows = fetch_consumer_lag(
        admin=admin,
        consumer=consumer,
        groups=["missing-group", "cdc-bronze-writer-v1"],
    )
    assert [r["group"] for r in rows] == ["cdc-bronze-writer-v1"]
    assert rows[0]["lag"] == 10


def test_negative_lag_is_clamped_to_zero():
    admin = _FakeAdmin(
        {"cdc-bronze-writer-v1": [TopicPartition("cdc.events", 0, 120)]}
    )
    consumer = _FakeConsumer({("cdc.events", 0): (0, 100)})
    rows = fetch_consumer_lag(
        admin=admin, consumer=consumer, groups=["cdc-bronze-writer-v1"]
    )
    assert rows[0]["lag"] == 0


def test_raises_when_broker_unreachable():
    admin = _FakeAdmin({}, reachable=False)
    consumer = _FakeConsumer({})
    with pytest.raises(ConsumerLagUnavailable):
        fetch_consumer_lag(admin=admin, consumer=consumer, groups=["cdc-bronze-writer-v1"])
