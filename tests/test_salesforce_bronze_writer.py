"""Unit tests for the Salesforce bronze writer."""

from __future__ import annotations

import io
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pyarrow.parquet as pq

from workers.salesforce_bronze_writer.writer import (
    RawReadyMessage,
    SalesforceBronzeWriter,
    TOPIC_BRONZE_READY,
    raw_uri_to_bronze_uri,
    records_to_parquet,
)


def _raw_ready_envelope(
    *,
    sobject: str = "Account",
    run_id: str | None = None,
    row_count: int = 2,
    output_uris: list[str] | None = None,
) -> dict[str, Any]:
    run_id = run_id or str(uuid4())
    output_uris = output_uris or [
        f"s3://fintech-lakehouse/raw/source=salesforce/object={sobject}/year=2026/month=04/day=15/run_id={run_id}/page-0000.json"
    ]
    return {
        "event_id": str(uuid4()),
        "event_type": "ingest.salesforce.raw.ready.v1",
        "run_id": run_id,
        "trace_id": str(uuid4()),
        "trigger_event_ref": f"salesforce_incremental_pull__2026-04-15T00:00:00+00:00__{sobject}",
        "occurred_at": "2026-04-15T01:00:00Z",
        "schema_version": "v1",
        "payload_hash": "sha256-irrelevant",
        "payload": {
            "stage": "raw",
            "sobject": sobject,
            "row_count": row_count,
            "page_count": len(output_uris),
            "output_uris": output_uris,
            "transform_id": "salesforce_incremental_pull",
            "transform_version": "v1",
        },
    }


@dataclass
class _FakeStore:
    pages: list[dict[str, Any]] = field(default_factory=list)
    writes: list[tuple[str, bytes, str, str]] = field(default_factory=list)

    def read_uri(self, uri: str) -> bytes:
        idx = int(uri.rsplit("page-", 1)[1].split(".", 1)[0])
        return json.dumps(self.pages[idx]).encode()

    def write_uri(self, uri: str, data: bytes, *, content_type: str, kms_key_id: str) -> None:
        self.writes.append((uri, data, content_type, kms_key_id))


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
            _Produced(topic=topic, key=key, event_type=envelope.event_type, payload=envelope.payload)
        )
        return (3, 77)


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


def _sf_record(idx: int, *, sobject: str = "Account", ts: str | None = None) -> dict[str, Any]:
    return {
        "attributes": {"type": sobject, "url": f"/services/data/v59.0/sobjects/{sobject}/001abc{idx}"},
        "Id": f"001abc{idx:03d}",
        "Name": f"Acme Co {idx}",
        "SystemModstamp": ts or f"2026-04-15T01:00:{idx:02d}.000Z",
    }


def test_raw_uri_to_bronze_uri_transforms_path() -> None:
    raw = (
        "s3://fintech-lakehouse/raw/source=salesforce/object=Account/"
        "year=2026/month=04/day=15/run_id=abc/page-0000.json"
    )
    bronze = raw_uri_to_bronze_uri(raw)
    assert bronze == (
        "s3://fintech-lakehouse/bronze/source=salesforce/object=Account/"
        "year=2026/month=04/day=15/run_id=abc/part-0.parquet"
    )


def test_records_to_parquet_flattens_nested_attributes() -> None:
    records = [_sf_record(1), _sf_record(2)]
    data, fingerprint = records_to_parquet(records)
    table = pq.read_table(io.BytesIO(data))
    assert table.num_rows == 2
    assert {"Id", "Name", "SystemModstamp", "attributes"}.issubset(set(table.column_names))
    attrs_col = table.column("attributes").to_pylist()
    assert json.loads(attrs_col[0])["type"] == "Account"
    assert fingerprint.startswith("sha256-")


def test_handle_raw_ready_success_writes_bronze_and_advances_cursor(monkeypatch) -> None:
    calls: list[_Call] = []

    def _append_event(conn, envelope, **kwargs):  # noqa: ANN001
        calls.append(_Call("append_event", kwargs))
        return True

    def _append_sf_cursor(conn, **kwargs):  # noqa: ANN001
        calls.append(_Call("append_sf_cursor_checkpoint", kwargs))

    def _close_run(conn, run_id, **kwargs):  # noqa: ANN001
        calls.append(_Call("close_run", {"run_id": str(run_id), **kwargs}))

    def _raise_alert(conn, **kwargs):  # noqa: ANN001
        calls.append(_Call("raise_alert", kwargs))

    monkeypatch.setattr("workers.salesforce_bronze_writer.writer.PgEventStore.append_event", _append_event)
    monkeypatch.setattr("workers.salesforce_bronze_writer.writer.PgEventStore.append_sf_cursor_checkpoint", _append_sf_cursor)
    monkeypatch.setattr("workers.salesforce_bronze_writer.writer.PgEventStore.close_run", _close_run)
    monkeypatch.setattr("workers.salesforce_bronze_writer.writer.PgEventStore.raise_alert", _raise_alert)

    run_id = str(uuid4())
    envelope = _raw_ready_envelope(sobject="Account", run_id=run_id, row_count=2)
    store = _FakeStore()
    store.pages = [{"records": [_sf_record(1), _sf_record(2, ts="2026-04-15T01:00:05.000Z")]}]
    producer = _FakeProducer()
    conn = _FakeConn()
    writer = SalesforceBronzeWriter(store=store, producer=producer, db=conn, kms_key_id="kms-1")

    msg = RawReadyMessage(envelope=envelope, kafka_topic="ingest.salesforce.raw.ready.v1", kafka_partition=0, kafka_offset=42)
    ok = writer.handle_raw_ready(msg)

    assert ok is True
    assert len(store.writes) == 1
    assert store.writes[0][0].startswith("s3://fintech-lakehouse/bronze/source=salesforce/object=Account/")
    assert producer.produced[0].topic == TOPIC_BRONZE_READY
    assert producer.produced[0].payload["stage"] == "bronze"
    assert producer.produced[0].payload["sobject"] == "Account"
    assert producer.produced[0].payload["record_count"] == 2
    assert producer.produced[0].payload["advanced_cursor_id"] == "001abc002"
    cursor_call = next(c for c in calls if c.name == "append_sf_cursor_checkpoint")
    assert cursor_call.kwargs["sobject"] == "Account"
    assert cursor_call.kwargs["cursor_id"] == "001abc002"
    assert cursor_call.kwargs["record_count"] == 2
    assert cursor_call.kwargs["offset_start"] == 42 and cursor_call.kwargs["offset_end"] == 42
    assert any(c.name == "close_run" and c.kwargs["status"] == "completed" for c in calls)
    assert not any(c.name == "raise_alert" for c in calls)


def test_handle_raw_ready_zero_rows_closes_without_checkpoint(monkeypatch) -> None:
    calls: list[_Call] = []

    def _append_event(conn, envelope, **kwargs):  # noqa: ANN001
        calls.append(_Call("append_event", kwargs))

    def _append_sf_cursor(conn, **kwargs):  # noqa: ANN001
        calls.append(_Call("append_sf_cursor_checkpoint", kwargs))

    def _close_run(conn, run_id, **kwargs):  # noqa: ANN001
        calls.append(_Call("close_run", {"run_id": str(run_id), **kwargs}))

    monkeypatch.setattr("workers.salesforce_bronze_writer.writer.PgEventStore.append_event", _append_event)
    monkeypatch.setattr("workers.salesforce_bronze_writer.writer.PgEventStore.append_sf_cursor_checkpoint", _append_sf_cursor)
    monkeypatch.setattr("workers.salesforce_bronze_writer.writer.PgEventStore.close_run", _close_run)

    envelope = _raw_ready_envelope(row_count=0, output_uris=[])
    writer = SalesforceBronzeWriter(store=_FakeStore(), producer=_FakeProducer(), db=_FakeConn(), kms_key_id="k")
    msg = RawReadyMessage(envelope=envelope, kafka_topic="ingest.salesforce.raw.ready.v1", kafka_partition=0, kafka_offset=1)

    assert writer.handle_raw_ready(msg) is True
    assert not any(c.name == "append_sf_cursor_checkpoint" for c in calls)
    assert not any(c.name == "append_event" for c in calls)
    assert any(c.name == "close_run" and c.kwargs["status"] == "completed" for c in calls)


def test_handle_raw_ready_failure_alerts_and_closes_failed(monkeypatch) -> None:
    calls: list[_Call] = []

    def _append_event(conn, envelope, **kwargs):  # noqa: ANN001
        calls.append(_Call("append_event", kwargs))

    def _append_sf_cursor(conn, **kwargs):  # noqa: ANN001
        calls.append(_Call("append_sf_cursor_checkpoint", kwargs))

    def _close_run(conn, run_id, **kwargs):  # noqa: ANN001
        calls.append(_Call("close_run", {"run_id": str(run_id), **kwargs}))

    def _raise_alert(conn, **kwargs):  # noqa: ANN001
        calls.append(_Call("raise_alert", kwargs))

    monkeypatch.setattr("workers.salesforce_bronze_writer.writer.PgEventStore.append_event", _append_event)
    monkeypatch.setattr("workers.salesforce_bronze_writer.writer.PgEventStore.append_sf_cursor_checkpoint", _append_sf_cursor)
    monkeypatch.setattr("workers.salesforce_bronze_writer.writer.PgEventStore.close_run", _close_run)
    monkeypatch.setattr("workers.salesforce_bronze_writer.writer.PgEventStore.raise_alert", _raise_alert)

    class _FailingStore(_FakeStore):
        def read_uri(self, uri: str) -> bytes:  # type: ignore[override]
            raise RuntimeError("minio down")

    envelope = _raw_ready_envelope(row_count=5)
    writer = SalesforceBronzeWriter(
        store=_FailingStore(), producer=_FakeProducer(), db=_FakeConn(), kms_key_id="k"
    )
    msg = RawReadyMessage(envelope=envelope, kafka_topic="ingest.salesforce.raw.ready.v1", kafka_partition=0, kafka_offset=9)

    assert writer.handle_raw_ready(msg) is False
    assert any(c.name == "raise_alert" for c in calls)
    assert any(c.name == "close_run" and c.kwargs["status"] == "failed" for c in calls)
    assert not any(c.name == "append_sf_cursor_checkpoint" for c in calls)
