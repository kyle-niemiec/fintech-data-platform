"""Task callable for excel_validation.write_raw."""

from __future__ import annotations

from typing import Any

from dag_runtime import build_minio_client

from excel_validation.common import _raw_key


def write_raw(validated: dict[str, Any]) -> dict[str, Any]:
    """
    Write the original object to the raw location in MinIO and return the updated
    metadata for downstream tasks.
    """
    from minio.commonconfig import CopySource

    client = build_minio_client(
        access_key_var="MINIO_VALIDATION_USER",
        secret_key_var="MINIO_VALIDATION_SECRET",
    )

    dest_key = _raw_key(validated["object_key"], validated["run_id"])

    client.copy_object(
        bucket_name=validated["bucket"],
        object_name=dest_key,
        source=CopySource(validated["bucket"], validated["object_key"]),
    )

    return {
        **validated,
        "stage": "raw",
        "output_key": dest_key,
    }
