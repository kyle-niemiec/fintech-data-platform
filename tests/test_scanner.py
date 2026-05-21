"""Unit coverage for the Excel scanner.

Pure helpers (parse_minio_record, check_size, check_mime, interpret_clamd_result)
are exercised directly. The end-to-end handle_record flow is tested with stubs
for the object store, clamd, producer, and event-store helpers — this keeps
slice 2 fast and isolates scanner behavior from the event-store SQL, which
earns its own integration test against testcontainers in a later slice.
"""

from __future__ import annotations

import io
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from meridian.libs.redpanda_events.envelope import Envelope
from workers.excel_scanner import scanner as scanner_mod
from workers.excel_scanner.scanner import (
    DEFAULT_ALLOWED_CONTENT_TYPES,
    ExcelScanner,
    ScannerConfig,
    TOPIC_SCAN_FAIL,
    TOPIC_SCAN_PASS,
    TOPIC_UPLOADED,
    UploadedObject,
    XLSX_MAGIC,
    check_mime,
    check_size,
    interpret_clamd_result,
    parse_minio_record,
)

XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _minio_record(
    *,
    bucket: str = "fintech-lakehouse",
    key: str = "landing/source=excel/year=2026/month=04/day=13/payroll.xlsx",
    size: int = 4096,
    etag: str = "etag-abc123",
    content_type: str = XLSX_CT,
    uploader: str = "minio_ingest",
    event_time: str = "2026-04-13T12:00:00Z",
) -> dict[str, Any]:
    return {
        "eventVersion": "2.0",
        "eventSource": "minio:s3",
        "eventName": "s3:ObjectCreated:Put",
        "eventTime": event_time,
        "userIdentity": {"principalId": uploader},
        "s3": {
            "bucket": {"name": bucket},
            "object": {
                "key": key,
                "size": size,
                "eTag": etag,
                "contentType": content_type,
            },
        },
    }


class _ResettableStream(io.BytesIO):
    """Stream that the scanner can close and the store can hand out again."""


class FakeObjectStore:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.calls = 0

    def stat(self, bucket: str, key: str) -> dict[str, Any]:
        return {"size": len(self.payload), "etag": "etag-abc123", "content_type": XLSX_CT}

    def get_stream(self, bucket: str, key: str):
        self.calls += 1
        return _ResettableStream(self.payload)


class FakeObjectStoreWithUploader(FakeObjectStore):
    """Stat exposes the canonical uploader-principal metadata key."""

    def __init__(self, payload: bytes, uploader: str):
        super().__init__(payload)
        self._uploader = uploader

    def stat(self, bucket: str, key: str) -> dict[str, Any]:
        return {
            "size": len(self.payload),
            "etag": "etag-abc123",
            "content_type": XLSX_CT,
            "metadata": {"uploader-principal": self._uploader},
        }


class FakeClamd:
    def __init__(self, *, verdict: tuple[str, Any]):
        self.verdict = verdict
        self.invocations = 0

    def instream(self, stream) -> dict[str, tuple[str, Any]]:
        self.invocations += 1
        stream.read()
        return {"stream": self.verdict}

    def version(self) -> str:
        return "ClamAV 1.0 / fake"


@dataclass
class ProducedEvent:
    topic: str
    envelope: Envelope
    key: str


class FakeProducer:
    def __init__(self):
        self.produced: list[ProducedEvent] = []

    def produce(self, topic: str, envelope: Envelope, *, key: str) -> tuple[int, int]:
        self.produced.append(ProducedEvent(topic=topic, envelope=envelope, key=key))
        return (0, len(self.produced) - 1)


@dataclass
class RecordedCall:
    name: str
    args: tuple
    kwargs: dict[str, Any]


@dataclass
class FakeConn:
    calls: list[RecordedCall] = field(default_factory=list)

    @contextmanager
    def session(self):
        yield self

    @contextmanager
    def begin(self):
        yield self

    @contextmanager
    def transaction(self):
        yield from self.begin()


@pytest.fixture
def fake_event_store(monkeypatch):
    """Patch the event-store helpers imported into scanner_mod."""
    calls: list[RecordedCall] = []
    fixed_run_id = uuid4()

    def fake_open_run(conn, **kwargs):
        calls.append(RecordedCall("open_run", (), kwargs))
        return kwargs.get("run_id") or fixed_run_id

    def fake_append_event(conn, envelope, **kwargs):
        calls.append(RecordedCall("append_event", (envelope,), kwargs))
        return True

    def fake_close_run(conn, run_id, **kwargs):
        calls.append(RecordedCall("close_run", (run_id,), kwargs))

    def fake_raise_alert(conn, **kwargs):
        calls.append(RecordedCall("raise_alert", (), kwargs))

    monkeypatch.setattr(scanner_mod.PgEventStore, "open_run", fake_open_run)
    monkeypatch.setattr(scanner_mod.PgEventStore, "append_event", fake_append_event)
    monkeypatch.setattr(scanner_mod.PgEventStore, "close_run", fake_close_run)
    monkeypatch.setattr(scanner_mod.PgEventStore, "raise_alert", fake_raise_alert)
    return calls


# --- parse_minio_record ----------------------------------------------------


def test_parse_minio_record_happy():
    obj = parse_minio_record(_minio_record())
    assert obj.bucket == "fintech-lakehouse"
    assert obj.object_key.endswith("payroll.xlsx")
    assert obj.size_bytes == 4096
    assert obj.etag == "etag-abc123"
    assert obj.content_type == XLSX_CT
    assert obj.uploader_principal == "minio_ingest"
    assert obj.trigger_event_ref == f"minio:fintech-lakehouse:{obj.object_key}:etag-abc123"
    assert obj.event_time.tzinfo is not None


def test_parse_minio_record_requires_etag():
    record = _minio_record()
    record["s3"]["object"]["eTag"] = ""
    with pytest.raises(ValueError, match="missing eTag"):
        parse_minio_record(record)


def test_parse_minio_record_missing_field():
    record = _minio_record()
    del record["s3"]["bucket"]
    with pytest.raises(ValueError, match="missing"):
        parse_minio_record(record)


# --- gates -----------------------------------------------------------------


def _obj(**overrides) -> UploadedObject:
    base = dict(
        bucket="b",
        object_key="k.xlsx",
        etag="e",
        size_bytes=100,
        content_type=XLSX_CT,
        uploader_principal="u",
        event_time=datetime(2026, 4, 13, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return UploadedObject(**base)


def test_check_size_rejects_oversize():
    v = check_size(_obj(size_bytes=200), max_bytes=100)
    assert not v.passed and v.reason == "size_exceeded"


def test_check_size_rejects_zero():
    v = check_size(_obj(size_bytes=0), max_bytes=100)
    assert not v.passed and v.reason == "size_invalid"


def test_check_size_pass():
    assert check_size(_obj(size_bytes=50), max_bytes=100).passed


def test_check_mime_rejects_wrong_ct():
    v = check_mime(_obj(content_type="text/plain"), DEFAULT_ALLOWED_CONTENT_TYPES, magic_probe=XLSX_MAGIC)
    assert not v.passed and v.reason == "content_type_rejected"


def test_check_mime_rejects_wrong_magic():
    v = check_mime(_obj(), DEFAULT_ALLOWED_CONTENT_TYPES, magic_probe=b"%PDF")
    assert not v.passed and v.reason == "magic_bytes_mismatch"


def test_check_mime_pass():
    assert check_mime(_obj(), DEFAULT_ALLOWED_CONTENT_TYPES, magic_probe=XLSX_MAGIC + b"more").passed


def test_interpret_clamd_results():
    assert interpret_clamd_result({"stream": ("OK", None)}).passed
    fail = interpret_clamd_result({"stream": ("FOUND", "Eicar-Test-Signature")})
    assert not fail.passed and fail.reason == "malware"
    err = interpret_clamd_result({"stream": ("ERROR", "boom")})
    assert not err.passed and err.reason == "scan_error"


# --- handle_record end-to-end (stubbed side-effects) -----------------------


def _build_scanner(
    *,
    payload: bytes,
    clamd_verdict: tuple[str, Any],
    config: ScannerConfig | None = None,
):
    store = FakeObjectStore(payload)
    clamd_client = FakeClamd(verdict=clamd_verdict)
    producer = FakeProducer()
    db = FakeConn()
    scanner = ExcelScanner(
        object_store=store,
        clamd_client=clamd_client,
        producer=producer,
        db_connection_factory=db.session,
        config=config or ScannerConfig(scan_engine_version="1.0/fake"),
    )
    return scanner, store, clamd_client, producer


def test_handle_record_pass_path(fake_event_store):
    scanner, store, clamd_client, producer = _build_scanner(
        payload=XLSX_MAGIC + b"rest of xlsx", clamd_verdict=("OK", None)
    )

    scanner.handle_record(
        _minio_record(),
        source_topic=TOPIC_UPLOADED,
        source_partition=2,
        source_offset=17,
    )

    names = [c.name for c in fake_event_store]
    assert names == ["open_run", "append_event", "append_event"]
    assert store.calls == 2
    assert clamd_client.invocations == 1

    assert [p.topic for p in producer.produced] == [TOPIC_SCAN_PASS]
    pass_env = producer.produced[0].envelope
    assert pass_env.payload["scan_result"] == "pass"
    assert pass_env.payload["failure_reason"] is None

    # First append_event is the `uploaded` envelope carrying the consumed offset
    uploaded_call = fake_event_store[1]
    assert uploaded_call.kwargs["topic"] == TOPIC_UPLOADED
    assert uploaded_call.kwargs["partition"] == 2
    assert uploaded_call.kwargs["kafka_offset"] == 17


def test_handle_record_oversize_rejects_before_scan(fake_event_store):
    scanner, store, clamd_client, producer = _build_scanner(
        payload=b"", clamd_verdict=("OK", None), config=ScannerConfig(max_bytes=10),
    )
    rec = _minio_record(size=1024)

    scanner.handle_record(rec, source_topic=TOPIC_UPLOADED, source_partition=0, source_offset=5)

    assert store.calls == 0
    assert clamd_client.invocations == 0
    fail_env = producer.produced[0]
    assert fail_env.topic == TOPIC_SCAN_FAIL
    assert fail_env.envelope.payload["failure_reason"] == "size_exceeded"

    names = [c.name for c in fake_event_store]
    assert "raise_alert" in names
    assert "close_run" in names


def test_handle_record_wrong_mime_fails_before_scan(fake_event_store):
    scanner, store, clamd_client, producer = _build_scanner(
        payload=b"not-xlsx-bytes", clamd_verdict=("OK", None),
    )
    rec = _minio_record(content_type="text/csv")

    scanner.handle_record(rec, source_topic=TOPIC_UPLOADED, source_partition=0, source_offset=1)

    assert clamd_client.invocations == 0
    fail_env = producer.produced[0]
    assert fail_env.topic == TOPIC_SCAN_FAIL
    assert fail_env.envelope.payload["failure_reason"] == "content_type_rejected"


def test_handle_record_malware_raises_alert(fake_event_store):
    scanner, _store, clamd_client, producer = _build_scanner(
        payload=XLSX_MAGIC + b"infected",
        clamd_verdict=("FOUND", "Eicar-Test-Signature"),
    )

    scanner.handle_record(_minio_record(), source_topic=TOPIC_UPLOADED, source_partition=0, source_offset=3)

    assert clamd_client.invocations == 1
    fail_env = producer.produced[0]
    assert fail_env.topic == TOPIC_SCAN_FAIL
    assert fail_env.envelope.payload["failure_reason"] == "malware"

    alert_calls = [c for c in fake_event_store if c.name == "raise_alert"]
    assert len(alert_calls) == 1
    assert alert_calls[0].kwargs["severity"] == "high"
    assert alert_calls[0].kwargs["category"] == "excel_scan_failed"

    close_calls = [c for c in fake_event_store if c.name == "close_run"]
    assert close_calls[0].kwargs["status"] == "scan_failed"


def test_handle_record_uses_canonical_metadata_uploader(fake_event_store):
    # The ingress access-key principal ("minio_ingest") is overridden by the
    # business uploader read from the canonical uploader-principal metadata key.
    store = FakeObjectStoreWithUploader(
        XLSX_MAGIC + b"ok", uploader="alex.ortiz@meridian.example.com"
    )
    scanner = ExcelScanner(
        object_store=store,
        clamd_client=FakeClamd(verdict=("OK", None)),
        producer=FakeProducer(),
        db_connection_factory=FakeConn().session,
        config=ScannerConfig(scan_engine_version="1.0/fake"),
    )

    scanner.handle_record(
        _minio_record(uploader="minio_ingest"),
        source_topic=TOPIC_UPLOADED,
        source_partition=0,
        source_offset=1,
    )

    open_call = [c for c in fake_event_store if c.name == "open_run"][0]
    assert open_call.kwargs["initiator"] == "alex.ortiz@meridian.example.com"

    uploaded_env = [c for c in fake_event_store if c.name == "append_event"][0].args[0]
    assert uploaded_env.payload["uploader_principal"] == "alex.ortiz@meridian.example.com"


def test_handle_record_run_id_returned_by_open_run_is_used(monkeypatch, fake_event_store):
    forced_run_id = UUID("11111111-1111-1111-1111-111111111111")

    def forced_open_run(conn, **kwargs):
        fake_event_store.append(RecordedCall("open_run", (), kwargs))
        return forced_run_id

    monkeypatch.setattr(scanner_mod.PgEventStore, "open_run", forced_open_run)

    scanner, _store, _clamd, producer = _build_scanner(
        payload=XLSX_MAGIC + b"ok", clamd_verdict=("OK", None)
    )
    scanner.handle_record(_minio_record(), source_topic=TOPIC_UPLOADED, source_partition=0, source_offset=7)

    pass_env = producer.produced[0].envelope
    assert pass_env.run_id == forced_run_id
