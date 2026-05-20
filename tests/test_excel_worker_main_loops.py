"""Run-loop behavior tests for Excel workers."""

from __future__ import annotations

import json
import signal
from dataclasses import dataclass
from typing import Any, Callable

from workers.excel_bronze_writer import main as bronze_main
from workers.excel_bronze_writer.writer import RetryableFinalizationError
from workers.excel_scanner import main as scanner_main


@dataclass
class _FakeMsg:
    payload: bytes
    _topic: str
    _partition: int
    _offset: int

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


class _FakeProducer:
    def close(self):
        return None


def _install_signal_capture(monkeypatch):
    handlers: dict[int, Callable[..., Any]] = {}

    def _capture(signum: int, handler):  # noqa: ANN001
        handlers[signum] = handler
        return None

    monkeypatch.setattr(signal, "signal", _capture)
    return handlers


def test_excel_scanner_run_does_not_commit_on_record_failure(monkeypatch):
    handlers = _install_signal_capture(monkeypatch)

    class _FailingScanner:
        def handle_record(self, *_args, **_kwargs):
            raise RuntimeError("db unavailable")

    msg = _FakeMsg(
        payload=json.dumps({"Records": [{"s3": {"bucket": {"name": "b"}, "object": {"key": "k", "size": 1, "eTag": "e"}}}]}).encode("utf-8"),
        _topic="ingest.excel.uploaded.v1",
        _partition=0,
        _offset=123,
    )

    consumer_ref: dict[str, _FakeConsumer] = {}

    def _stop():
        handler = handlers.get(signal.SIGTERM)
        assert handler is not None
        handler(signal.SIGTERM, None)

    def _fake_build_scanner():
        consumer = _FakeConsumer(msg, _stop)
        consumer_ref["consumer"] = consumer
        return _FailingScanner(), _FakeProducer(), consumer

    monkeypatch.setattr(scanner_main, "build_scanner", _fake_build_scanner)
    scanner_main.run()
    assert consumer_ref["consumer"].commit_calls == 0


def test_excel_bronze_run_skips_commit_on_retryable_finalization_error(monkeypatch):
    handlers = _install_signal_capture(monkeypatch)

    class _RetryableWriter:
        def handle_raw_ready(self, _envelope):
            raise RetryableFinalizationError("finalize failed")

    msg = _FakeMsg(
        payload=json.dumps({"run_id": "11111111-1111-1111-1111-111111111111"}).encode("utf-8"),
        _topic="ingest.excel.raw.ready.v1",
        _partition=1,
        _offset=44,
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

    monkeypatch.setattr(bronze_main, "build_writer", _fake_build_writer)
    bronze_main.run()
    assert consumer_ref["consumer"].commit_calls == 0


def test_excel_bronze_run_commits_on_terminal_failure(monkeypatch):
    handlers = _install_signal_capture(monkeypatch)

    class _TerminalFailWriter:
        def handle_raw_ready(self, _envelope):
            raise RuntimeError("bad payload")

    msg = _FakeMsg(
        payload=json.dumps({"run_id": "11111111-1111-1111-1111-111111111111"}).encode("utf-8"),
        _topic="ingest.excel.raw.ready.v1",
        _partition=1,
        _offset=45,
    )

    consumer_ref: dict[str, _FakeConsumer] = {}

    def _stop():
        handler = handlers.get(signal.SIGTERM)
        assert handler is not None
        handler(signal.SIGTERM, None)

    def _fake_build_writer():
        consumer = _FakeConsumer(msg, _stop)
        consumer_ref["consumer"] = consumer
        return _TerminalFailWriter(), consumer, _FakeProducer()

    monkeypatch.setattr(bronze_main, "build_writer", _fake_build_writer)
    bronze_main.run()
    assert consumer_ref["consumer"].commit_calls == 1
