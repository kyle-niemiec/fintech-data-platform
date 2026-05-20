"""Unit tests for CDC bronze writer batching and flush output."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

import pyarrow.parquet as pq

from workers.cdc_bronze_writer.writer import (
    AssessedRecord,
    CdcBronzeWriter,
    SOURCE_SYSTEM,
    TOPIC_BRONZE_READY,
    bronze_object_key,
    rows_to_parquet_bytes,
    assessed_record_to_row,
)


def _assessed(lsn: str, offset: int, risk_flags: list[str] | None = None) -> AssessedRecord:
    payload = {
        "risk_score": 0.9 if risk_flags else 0.0,
        "risk_flags": risk_flags or [],
        "transaction_id": f"txn-{offset}",
        "op": "c",
        "source_table": "trading.transaction",
        "original_topic_metadata": {
            "topic": "cdc.oltp.raw.v1",
            "partition": 0,
            "offset": offset,
            "lsn": lsn,
            "source_ts_ms": 1700000000000 + offset,
        },
    }
    env = {
        "event_id": f"00000000-0000-0000-0000-{offset:012d}",
        "event_type": "cdc.oltp.assessed.v1",
        "payload": payload,
    }
    return AssessedRecord(
        envelope=env,
        kafka_topic="cdc.oltp.assessed.v1",
        kafka_partition=0,
        kafka_offset=offset,
    )


@dataclass
class _FakeStore:
    writes: list[tuple[str, bytes, str, str]] = field(default_factory=list)

    def write_uri(self, uri: str, data: bytes, *, content_type: str, kms_key_id: str) -> None:
        self.writes.append((uri, data, content_type, kms_key_id))


def test_bronze_object_key_template() -> None:
    key = bronze_object_key(
        bucket="fintech-lakehouse",
        source_table="trading.transaction",
        run_id=UUID("11111111-1111-1111-1111-111111111111"),
        written_at=datetime(2026, 4, 14, 15, 30, tzinfo=timezone.utc),
    )
    assert key == (
        "bronze/source=cdc/table=trading.transaction/"
        "year=2026/month=04/day=14/hour=15/"
        "run_id=11111111-1111-1111-1111-111111111111/part-0.parquet"
    )


def test_flush_sorts_by_lsn_and_preserves_record_count() -> None:
    store = _FakeStore()
    writer = CdcBronzeWriter(
        store=store,
        kms_key_id="k", bucket="fintech-lakehouse",
    )

    records = [
        _assessed("0/16B5C30", offset=2),
        _assessed("0/16B5C10", offset=0, risk_flags=["risk_threshold_exceeded"]),
        _assessed("0/16B5C20", offset=1),
    ]
    flush = writer.build_flush(records)
    assert list(flush.by_table.keys()) == ["trading.transaction"]
    rows = flush.by_table["trading.transaction"]
    assert [r.source_lsn for r in rows] == ["0/16B5C10", "0/16B5C20", "0/16B5C30"]

    prepared = writer.write_batches(flush, now=datetime(2026, 4, 14, 15, 30, tzinfo=timezone.utc))
    assert len(prepared) == 1
    batch = prepared[0]
    assert batch.record_count == 3
    assert batch.first_lsn == "0/16B5C10"
    assert batch.last_lsn == "0/16B5C30"
    assert batch.offset_start == 0 and batch.offset_end == 2
    assert batch.envelope.event_type == TOPIC_BRONZE_READY
    assert batch.envelope.payload["record_count"] == 3
    assert batch.envelope.payload["first_lsn"] == "0/16B5C10"
    assert batch.envelope.payload["last_lsn"] == "0/16B5C30"
    assert len(store.writes) == 1
    assert store.writes[0][3] == "k"


def test_parquet_columns_cover_contract_fields() -> None:
    rows = [assessed_record_to_row(_assessed("0/16B5C10", offset=0, risk_flags=["risk_threshold_exceeded"]))]
    data = rows_to_parquet_bytes(rows)
    table = pq.read_table(io.BytesIO(data))
    expected_cols = {
        "op", "transaction_id", "source_table", "source_lsn", "source_ts_ms",
        "kafka_topic", "kafka_partition", "kafka_offset", "event_id",
        "risk_score", "risk_flags", "assessed_payload",
    }
    assert expected_cols.issubset(set(table.column_names))
    assert table.num_rows == 1


def test_cdc_bronze_source_system_matches_event_store_domain_contract() -> None:
    assert SOURCE_SYSTEM == "cdc"
