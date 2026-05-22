"""Thin boto3 wrapper for uploading demo artifacts to MinIO."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from config import settings

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


@dataclass(frozen=True)
class UploadResult:
    bucket: str
    key: str
    etag: str
    size_bytes: int


class MinioUploadError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_ingest_user,
        aws_secret_access_key=settings.minio_ingest_secret,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def split_s3_uri(uri: str) -> tuple[str, str]:
    """Split an ``s3://bucket/key`` URI into ``(bucket, key)``."""
    if not uri.startswith("s3://"):
        raise MinioUploadError(f"not an s3 uri: {uri!r}")
    bucket, _, key = uri[len("s3://"):].partition("/")
    if not bucket or not key:
        raise MinioUploadError(f"malformed s3 uri: {uri!r}")
    return bucket, key


def read_object(*, bucket: str, key: str) -> bytes:
    """Read an object's bytes from MinIO. SSE-KMS decryption is server-side, so
    the client receives plaintext. Used by the read-only run-preview endpoint."""
    try:
        response = _client().get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    except (BotoCoreError, ClientError) as exc:
        raise MinioUploadError(str(exc)) from exc


def put_xlsx(
    *,
    key: str,
    body: bytes,
    demo_uploader: str,
) -> UploadResult:
    try:
        response = _client().put_object(
            Bucket=settings.minio_landing_bucket,
            Key=key,
            Body=body,
            ContentType=XLSX_CONTENT_TYPE,
            # Canonical well-known key the excel_scanner reads to attribute the
            # business uploader (UPLOADER_PRINCIPAL_METADATA_KEY in the scanner).
            Metadata={
                "uploader-principal": demo_uploader,
            },
        )
    except (BotoCoreError, ClientError) as exc:
        raise MinioUploadError(str(exc)) from exc

    etag = (response.get("ETag") or "").strip('"')
    return UploadResult(
        bucket=settings.minio_landing_bucket,
        key=key,
        etag=etag,
        size_bytes=len(body),
    )
