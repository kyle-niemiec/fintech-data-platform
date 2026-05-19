"""Unit coverage for Excel bronze writer."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from workers.excel_bronze_writer.writer import (
    TOPIC_BRONZE_READY,
    ExcelBronzeWriter,
    raw_uri_to_bronze_uri,
)


def _raw_ready_envelope() -> dict[str, Any]:
    run_id = "11111111-1111-1111-1111-111111111111"
    return {
        "event_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "event_type": "ingest.excel.raw.ready.v1",
        "source": "excel",
        "run_id": run_id,
        "pipeline_class": "ingestion",
        "pipeline_name": "excel_ingestion",
        "parent_run_id": None,
        "trigger_event_ref": "minio:fintech-lakehouse:landing/source=excel/...:etag-1",
        "trace_id": "22222222-2222-2222-2222-222222222222",
        "occurred_at": "2026-04-14T00:00:00Z",
        "schema_version": "v1",
        "payload_hash": "sha256-" + ("0" * 64),
        "payload": {
            "message": "raw ready",
            "stage": "raw",
            "input_uris": [
                "s3://fintech-lakehouse/landing/source=excel/year=2026/month=04/day=14/run_id=11111111-1111-1111-1111-111111111111/payroll.xlsx"
            ],
            "output_uris": [
                "s3://fintech-lakehouse/raw/source=excel/year=2026/month=04/day=14/run_id=11111111-1111-1111-1111-111111111111/payroll.xlsx"
            ],
            "row_count": 2,
            "schema_contract_id": "payroll_v1",
            "transform_id": "excel_schema_validate",
            "transform_version": "v1",
        },
    }


@dataclass
class _FakeStore:
    source_bytes: bytes = b"xlsx-bytes"
    writes: list[tuple[str, bytes, str, str]] = field(default_factory=list)

    def read_uri(self, uri: str) -> bytes:
        return self.source_bytes

    def write_uri(self, uri: str, data: bytes, *, content_type: str, kms_key_id: str) -> None:
        self.writes.append((uri, data, content_type, kms_key_id))


@dataclass
class _FakeConverter:
    output_bytes: bytes = b"parquet-bytes"
    row_count: int = 2
    schema_fingerprint: str = "sha256-schema-fp"

    def to_parquet(self, xlsx_bytes: bytes) -> tuple[bytes, int, str]:
        return self.output_bytes, self.row_count, self.schema_fingerprint


@dataclass
class _Produced:
    topic: str
    key: str
    event_type: str
    payload: dict[str, Any]


class _FakeProducer:
    def __init__(self) -> None:
        self.produced: list[_Produced] = []

    def produce(self, topic: str, envelope, *, key: str):  # noqa: ANN001
        self.produced.append(
            _Produced(
                topic=topic,
                key=key,
                event_type=envelope.event_type,
                payload=envelope.payload,
            )
        )
        return (1, 42)


@dataclass
class _Call:
    name: str
    kwargs: dict[str, Any]


@dataclass
class _FakeConn:
    calls: list[_Call] = field(default_factory=list)

    @contextmanager
    def transaction(self):
        yield self


def test_raw_uri_to_bronze_uri():
    raw_uri = "s3://fintech-lakehouse/raw/source=excel/year=2026/month=04/day=14/run_id=abc/payroll.xlsx"
    bronze_uri = raw_uri_to_bronze_uri(raw_uri)
    assert bronze_uri == "s3://fintech-lakehouse/bronze/source=excel/year=2026/month=04/day=14/run_id=abc/payroll.parquet"


def test_handle_raw_ready_success(monkeypatch):
    calls: list[_Call] = []

    def _append_event(conn, envelope, **kwargs):  # noqa: ANN001
        calls.append(_Call("append_event", kwargs))
        return True

    def _close_run(conn, run_id, **kwargs):  # noqa: ANN001
        calls.append(_Call("close_run", {"run_id": str(run_id), **kwargs}))

    def _raise_alert(conn, **kwargs):  # noqa: ANN001
        calls.append(_Call("raise_alert", kwargs))

    monkeypatch.setattr("workers.excel_bronze_writer.writer.PgEventStore.append_event", _append_event)
    monkeypatch.setattr("workers.excel_bronze_writer.writer.PgEventStore.close_run", _close_run)
    monkeypatch.setattr("workers.excel_bronze_writer.writer.PgEventStore.raise_alert", _raise_alert)

    store = _FakeStore()
    converter = _FakeConverter()
    producer = _FakeProducer()
    conn = _FakeConn()
    writer = ExcelBronzeWriter(store=store, converter=converter, producer=producer, db=conn, kms_key_id="fintech-lakehouse-kms-key")

    ok = writer.handle_raw_ready(_raw_ready_envelope())
    assert ok is True
    assert len(store.writes) == 1
    assert producer.produced[0].topic == TOPIC_BRONZE_READY
    assert producer.produced[0].payload["stage"] == "bronze"
    assert producer.produced[0].payload["format"] == "parquet"
    assert producer.produced[0].payload["record_count"] == 2
    assert producer.produced[0].payload["transform_id"] == "excel_to_parquet"
    assert producer.produced[0].payload["transform_version"] == "v1"
    assert any(c.name == "append_event" for c in calls)
    assert any(c.name == "close_run" and c.kwargs["status"] == "completed" for c in calls)
    assert not any(c.name == "raise_alert" for c in calls)


def test_handle_raw_ready_failure_closes_failed_and_alerts(monkeypatch):
    calls: list[_Call] = []

    def _append_event(conn, envelope, **kwargs):  # noqa: ANN001
        calls.append(_Call("append_event", kwargs))
        return True

    def _close_run(conn, run_id, **kwargs):  # noqa: ANN001
        calls.append(_Call("close_run", {"run_id": str(run_id), **kwargs}))

    def _raise_alert(conn, **kwargs):  # noqa: ANN001
        calls.append(_Call("raise_alert", kwargs))

    class _FailingConverter(_FakeConverter):
        def to_parquet(self, xlsx_bytes: bytes):  # type: ignore[override]
            raise RuntimeError("bad sheet")

    monkeypatch.setattr("workers.excel_bronze_writer.writer.PgEventStore.append_event", _append_event)
    monkeypatch.setattr("workers.excel_bronze_writer.writer.PgEventStore.close_run", _close_run)
    monkeypatch.setattr("workers.excel_bronze_writer.writer.PgEventStore.raise_alert", _raise_alert)

    writer = ExcelBronzeWriter(
        store=_FakeStore(),
        converter=_FailingConverter(),
        producer=_FakeProducer(),
        db=_FakeConn(),
        kms_key_id="fintech-lakehouse-kms-key",
    )

    ok = writer.handle_raw_ready(_raw_ready_envelope())
    assert ok is False
    assert any(c.name == "raise_alert" for c in calls)
    assert any(c.name == "close_run" and c.kwargs["status"] == "failed" for c in calls)
