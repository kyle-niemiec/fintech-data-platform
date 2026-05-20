"""Run-loop behavior tests for non-Excel workers."""

from __future__ import annotations

import json
import signal
from dataclasses import dataclass
from typing import Any, Callable

from workers.cdc_bronze_writer import main as cdc_main
from workers.fraud_worker import main as fraud_main
from workers.salesforce_bronze_writer import main as salesforce_main
from workers.salesforce_bronze_writer.writer import RetryableFinalizationError


@dataclass
class _FakeMsg:
    payload: bytes
    _topic: str
    _partition: int
    _offset: int
    _key: bytes | None = None

    def error(self):
        return None

    def value(self):
        return self.payload

    def topic(self):
        return self._topic

    def partition(self):
        return self._partition

    def offset(self):
        return self._offset

    def key(self):
        return self._key


class _FakeConsumer:
    def __init__(self, msg: _FakeMsg, stop: Callable[[], None]):
        self._msg = msg
        self._stop = stop
        self._polls = 0
        self.commit_calls = 0

    def poll(self, _timeout: float):
        if self._polls == 0:
            self._polls += 1
            return self._msg

        self._stop()
        return None

    def commit(self, *, message: _FakeMsg, asynchronous: bool):
        del message, asynchronous
        self.commit_calls += 1

    def close(self):
        return None

    def subscribe(self, _topics):
        return None


class _FakeProducer:
    def close(self):
        return None


class _FakeConn:
    def close(self):
        return None


def _install_signal_capture(monkeypatch):
    handlers: dict[int, Callable[..., Any]] = {}

    def _capture(signum: int, handler):  # noqa: ANN001
        handlers[signum] = handler
        return None

    monkeypatch.setattr(signal, "signal", _capture)
    return handlers


def test_salesforce_run_skips_commit_on_retryable_finalization_error(monkeypatch):
    handlers = _install_signal_capture(monkeypatch)

    class _RetryableWriter:
        def handle_raw_ready(self, _raw):
            raise RetryableFinalizationError("finalize failed")

    msg = _FakeMsg(
        payload=json.dumps({"run_id": "11111111-1111-1111-1111-111111111111", "payload": {"sobject": "Account"}}).encode("utf-8"),
        _topic="ingest.salesforce.raw.ready.v1",
        _partition=0,
        _offset=12,
    )
    consumer_ref: dict[str, _FakeConsumer] = {}

    def _stop():
        handler = handlers.get(signal.SIGTERM)
        assert handler is not None
        handler(signal.SIGTERM, None)

    def _fake_build_writer():
        consumer = _FakeConsumer(msg, _stop)
        consumer_ref["consumer"] = consumer
        return _RetryableWriter(), consumer, _FakeProducer()

    monkeypatch.setattr(salesforce_main, "build_writer", _fake_build_writer)
    salesforce_main.run()
    assert consumer_ref["consumer"].commit_calls == 0


def test_salesforce_run_commits_on_terminal_handled_failure(monkeypatch):
    handlers = _install_signal_capture(monkeypatch)

    class _TerminalWriter:
        def handle_raw_ready(self, _raw):
            return False

    msg = _FakeMsg(
        payload=json.dumps({"run_id": "11111111-1111-1111-1111-111111111111", "payload": {"sobject": "Account"}}).encode("utf-8"),
        _topic="ingest.salesforce.raw.ready.v1",
        _partition=0,
        _offset=13,
    )
    consumer_ref: dict[str, _FakeConsumer] = {}

    def _stop():
        handler = handlers.get(signal.SIGTERM)
        assert handler is not None
        handler(signal.SIGTERM, None)

    def _fake_build_writer():
        consumer = _FakeConsumer(msg, _stop)
        consumer_ref["consumer"] = consumer
        return _TerminalWriter(), consumer, _FakeProducer()

    monkeypatch.setattr(salesforce_main, "build_writer", _fake_build_writer)
    salesforce_main.run()
    assert consumer_ref["consumer"].commit_calls == 1


def test_cdc_run_flush_failure_leaves_offset_uncommitted(monkeypatch):
    handlers = _install_signal_capture(monkeypatch)
    monkeypatch.setenv("CDC_BATCH_MAX_RECORDS", "1")
    monkeypatch.setenv("CDC_BATCH_MAX_SECONDS", "30")

    class _FakeWriter:
        def build_flush(self, _pending):
            return object()

        def write_batches(self, _flush):
            return [object()]

    msg = _FakeMsg(
        payload=json.dumps({"event_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "payload": {}}).encode("utf-8"),
        _topic="cdc.oltp.assessed.v1",
        _partition=1,
        _offset=99,
    )
    consumer_ref: dict[str, _FakeConsumer] = {}

    def _stop():
        handler = handlers.get(signal.SIGTERM)
        assert handler is not None
        handler(signal.SIGTERM, None)

    def _fake_build():
        consumer = _FakeConsumer(msg, _stop)
        consumer_ref["consumer"] = consumer
        return _FakeWriter(), consumer, _FakeProducer()

    def _fail_prepare(_factory, _prepared):
        raise RuntimeError("event-store unavailable")

    monkeypatch.setattr(cdc_main, "_build", _fake_build)
    monkeypatch.setattr(cdc_main, "_prepare_batch_run", _fail_prepare)
    cdc_main.run()
    assert consumer_ref["consumer"].commit_calls == 0


def test_fraud_run_handler_failure_leaves_offset_uncommitted(monkeypatch):
    handlers = _install_signal_capture(monkeypatch)

    class _FailingHandler:
        oltp_conn = _FakeConn()

        def handle(self, _raw):
            raise RuntimeError("event-store unavailable")

    msg = _FakeMsg(
        payload=json.dumps({"payload": {"op": "c"}}).encode("utf-8"),
        _topic="cdc.oltp.raw.v1",
        _partition=2,
        _offset=17,
    )
    consumer_ref: dict[str, _FakeConsumer] = {}

    def _stop():
        handler = handlers.get(signal.SIGTERM)
        assert handler is not None
        handler(signal.SIGTERM, None)

    def _fake_build_handler():
        consumer = _FakeConsumer(msg, _stop)
        consumer_ref["consumer"] = consumer
        return _FailingHandler(), consumer, _FakeProducer()

    monkeypatch.setattr(fraud_main, "_build_handler", _fake_build_handler)
    fraud_main.run()
    assert consumer_ref["consumer"].commit_calls == 0
