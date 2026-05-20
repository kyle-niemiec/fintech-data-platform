from __future__ import annotations

import os
from typing import Any

from dag_runtime import build_minio_client

from excel_validation.common import _quarantine_key


def write_quarantine(validated: dict[str, Any]) -> dict[str, Any]:
    """
    Write the original object to the quarantine location in MinIO with server-side
    encryption and return the updated metadata for downstream tasks.
    """
    client = build_minio_client(
        access_key_var="MINIO_VALIDATION_USER",
        secret_key_var="MINIO_VALIDATION_SECRET",
    )

    dest_key = _quarantine_key(validated["object_key"], validated["run_id"])

    from minio.commonconfig import CopySource
    from minio.sse import SseKMS

    client.copy_object(
        bucket_name=validated["bucket"],
        object_name=dest_key,
        source=CopySource(validated["bucket"], validated["object_key"]),
        sse=SseKMS(os.environ["MINIO_KMS_KEY_ID"], {}),
    )

    return {
        **validated,
        "stage": "quarantine",
        "output_key": dest_key,
    }
