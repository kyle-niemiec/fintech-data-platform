"""Shared MinIO object store adapter used by workers."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from minio import Minio  # type: ignore[import-untyped]


def split_s3_uri(uri: str) -> tuple[str, str]:
    """
    Parse an s3:// URI into bucket and key components, validating the format.
    """
    parsed = urlparse(uri)

    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"invalid s3 uri: {uri}")

    return parsed.netloc, parsed.path.lstrip("/")


class MinioObjectStore:
    """
    Minimal adapter over the MinIO client to provide a simple object store API for
    workers. This is not intended to be a full abstraction layer, just a shared
    helper for common patterns.
    """
    
    
    def __init__(self, client: "Minio"):
        """
        Initialize the MinioObjectStore with a MinIO client.
        """
        self._client = client


    def stat(self, bucket: str, key: str) -> dict[str, Any]:
        """
        Get metadata for an object, including size, etag, content type, and user
        metadata.
        """
        obj = self._client.stat_object(bucket, key)
        raw_metadata = getattr(obj, "metadata", None) or {}
        metadata = {k: v for k, v in raw_metadata.items()}

        return {
            "size": obj.size,
            "etag": obj.etag,
            "content_type": obj.content_type,
            "metadata": metadata,
        }


    def get_stream(self, bucket: str, key: str):
        """
        Get a streaming object for the given bucket and key. Caller is responsible
        for closing the stream when done.
        """
        return self._client.get_object(bucket, key)


    def read_uri(self, uri: str) -> bytes:
        """
        Read the full contents of an object specified by an s3:// URI. Caller is not
        responsible for closing any resources.
        """
        bucket, key = split_s3_uri(uri)
        obj = self._client.get_object(bucket, key)

        try:
            return obj.read()
        finally:
            obj.close()
            obj.release_conn()


    def write_uri(self, uri: str, data: bytes, *, content_type: str, kms_key_id: str) -> None:
        """
        Write data to an object specified by an s3:// URI, with the given content type
        and KMS key for server-side encryption. Caller is responsible for ensuring the
        bucket already exists.
        """
        try:
            from minio.sse import SseKMS  # type: ignore[import-untyped]
        except ModuleNotFoundError:
            class SseKMS:  # type: ignore[too-many-ancestors]
                def __init__(self, key_id: str, _context: dict[str, str]):
                    self.key_id = key_id

        bucket, key = split_s3_uri(uri)

        self._client.put_object(
            bucket_name=bucket,
            object_name=key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
            sse=SseKMS(kms_key_id, {}),
        )
