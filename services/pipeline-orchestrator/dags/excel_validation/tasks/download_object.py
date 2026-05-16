"""Task callable for excel_validation.download_object."""

from __future__ import annotations

from typing import Any

from dag_runtime import build_minio_client

from excel_validation.common import _b64


def download_object(parsed: dict[str, Any]) -> dict[str, Any]:
    """
    Download the object from MinIO and return its payload as bytes along with
    the original parsed conf.
    """
    client = build_minio_client(
        access_key_var="MINIO_VALIDATION_USER",
        secret_key_var="MINIO_VALIDATION_SECRET",
    )

    response = client.get_object(parsed["bucket"], parsed["object_key"])

    # Read the entire payload into memory and close MinIO
    try:
        payload_bytes = response.read()
    finally:
        response.close()
        response.release_conn()

    # Return the original parsed conf along with the payload size and the payload for downstream tasks
    return {
        **parsed,
        "payload_size_bytes": len(payload_bytes),
        "_payload_b64": _b64(payload_bytes),
    }
