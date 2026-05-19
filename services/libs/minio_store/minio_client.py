from __future__ import annotations

import os


def build_minio_client(*, access_key_var: str, secret_key_var: str):
    """
    Build a Minio client, using credentials from env vars.
    """
    from minio import Minio  # type: ignore[import-untyped]

    return Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ[access_key_var],
        secret_key=os.environ[secret_key_var],
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
        region=os.environ.get("MINIO_REGION", "us-east-1"),
    )
