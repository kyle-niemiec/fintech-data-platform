"""Unit coverage for shared MinIO object-store adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from meridian.libs.minio_store import MinioObjectStore


class _FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.closed = False
        self.released = False

    def read(self) -> bytes:
        return self.payload

    def close(self) -> None:
        self.closed = True

    def release_conn(self) -> None:
        self.released = True


@dataclass
class _FakeStat:
    size: int
    etag: str
    content_type: str
    metadata: Any


class _FakeMinio:
    def __init__(self):
        self.response = _FakeResponse(b"payload")
        self.put_calls: list[dict[str, Any]] = []

    def get_object(self, bucket: str, key: str):
        self.last_get = (bucket, key)
        return self.response

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)

    def stat_object(self, bucket: str, key: str):
        self.last_stat = (bucket, key)
        return _FakeStat(
            size=42,
            etag="etag-123",
            content_type="application/octet-stream",
            metadata={"x-amz-meta-uploader": "user"},
        )


def test_read_uri_closes_and_releases_response() -> None:
    client = _FakeMinio()
    store = MinioObjectStore(client)

    data = store.read_uri("s3://fintech-lakehouse/raw/source=excel/file.xlsx")

    assert data == b"payload"
    assert client.last_get == ("fintech-lakehouse", "raw/source=excel/file.xlsx")
    assert client.response.closed is True
    assert client.response.released is True


def test_write_uri_uses_sse_kms_and_expected_bucket_key() -> None:
    client = _FakeMinio()
    store = MinioObjectStore(client)

    store.write_uri(
        "s3://fintech-lakehouse/bronze/source=excel/file.parquet",
        b"parquet-bytes",
        content_type="application/octet-stream",
        kms_key_id="kms-key",
    )

    assert len(client.put_calls) == 1
    call = client.put_calls[0]
    assert call["bucket_name"] == "fintech-lakehouse"
    assert call["object_name"] == "bronze/source=excel/file.parquet"
    assert call["length"] == len(b"parquet-bytes")
    assert call["content_type"] == "application/octet-stream"
    assert call["sse"].__class__.__name__ == "SseKMS"


def test_stat_normalizes_metadata_to_plain_dict() -> None:
    client = _FakeMinio()
    store = MinioObjectStore(client)

    result = store.stat("fintech-lakehouse", "landing/source=excel/file.xlsx")

    assert client.last_stat == ("fintech-lakehouse", "landing/source=excel/file.xlsx")
    assert result["size"] == 42
    assert result["etag"] == "etag-123"
    assert result["content_type"] == "application/octet-stream"
    assert isinstance(result["metadata"], dict)


def test_read_uri_rejects_non_s3_uri() -> None:
    store = MinioObjectStore(_FakeMinio())

    with pytest.raises(ValueError, match="invalid s3 uri"):
        store.read_uri("http://example.com/file")
