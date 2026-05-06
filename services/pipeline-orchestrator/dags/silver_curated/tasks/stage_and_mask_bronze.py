from __future__ import annotations

import io
import os
from typing import Any
from urllib.parse import urlparse

from airflow.exceptions import AirflowException
from dag_runtime import build_minio_client, now_utc

from silver_curated.common import STAGING_PREFIX


def stage_and_mask_bronze(state: dict[str, Any]) -> dict[str, Any]:
    """
    The stage_and_mask_bronze task is responsible for reading the raw "bronze"
    data files containing Salesforce Opportunity records, applying masking to
    sensitive fields, and writing the transformed data back to the data lake in
    a "staged" area for further processing.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq
    from libs.platform_masking import tokenize
    from minio.sse import SseKMS

    # Initialize the MinIO client and read the bronze Parquet files from the URIs provided
    curated_run_id = state["curated_run_id"]
    bucket = os.environ["MINIO_BUCKET_NAME"]
    kms_key = os.environ["MINIO_KMS_KEY_ID"]

    minio_client = build_minio_client(
        access_key_var="MINIO_TRINO_WRITE_USER",
        secret_key_var="MINIO_TRINO_WRITE_SECRET",
    )
    bronze_tables: list[pa.Table] = []

    # Read each bronze Parquet file from the provided URIs into a list of PyArrow tables
    for uri in state["bronze_uris"]:
        parsed = urlparse(uri)

        if parsed.scheme != "s3":
            raise AirflowException(f"unexpected bronze uri scheme: {uri}")

        object_key = parsed.path.lstrip("/")
        response = minio_client.get_object(bucket, object_key)

        # Read the Parquet file contents
        try:
            body = response.read()
        finally:
            response.close()
            response.release_conn()

        # Read the Parquet file content into a PyArrow table and append it to the list
        bronze_tables.append(pq.read_table(io.BytesIO(body)))

    if not bronze_tables:
        raise AirflowException("no bronze rows to promote")

    # Concatenate all the bronze tables into a single PyArrow table for processing
    table = pa.concat_tables(bronze_tables, promote=True)
    records = table.to_pylist()
    masked_rows: list[dict[str, Any]] = []

    # Iterate over each record from the bronze data, apply masking to sensitive fields
    for row in records:
        account_id = row.get("AccountId")

        account_id_token = (
            tokenize(str(account_id), scope="salesforce_account_id")
            if account_id is not None
            else None
        )

        system_mod = row.get("SystemModstamp")

        # Add the masked record to the list of masked rows
        masked_rows.append(
            {
                "opportunity_id": row.get("Id"),
                "account_id_token": account_id_token,
                "name": row.get("Name"),
                "stage_name": row.get("StageName"),
                "amount": row.get("Amount"),
                "close_date": row.get("CloseDate"),
                "is_won": row.get("IsWon"),
                "is_closed": row.get("IsClosed"),
                "source_system_mod": system_mod,
            }
        )

    # Write the masked rows to a Parquet file in memory, and then upload that
    # file to the MinIO bucket.
    staged_table = pa.Table.from_pylist(masked_rows)
    buffer = io.BytesIO()
    pq.write_table(staged_table, buffer, compression="snappy")
    buffer.seek(0)
    body = buffer.getvalue()
    now = now_utc()

    # Construct the S3 key for the staged Parquet file using the current date and run ID
    staged_key = (
        f"{STAGING_PREFIX}/year={now:%Y}/month={now:%m}/day={now:%d}/"
        f"run_id={curated_run_id}/_staging/part-0.parquet"
    )

    # Upload the Parquet file containing the masked rows to the MinIO bucket
    minio_client.put_object(
        bucket_name=bucket,
        object_name=staged_key,
        data=io.BytesIO(body),
        length=len(body),
        content_type="application/octet-stream",
        sse=SseKMS(kms_key, {}),
    )

    staged_uri = f"s3://{bucket}/{staged_key}"

    # Return the updated state for downstream processing
    return {
        **state,
        "staged_uri": staged_uri,
        "staged_row_count": len(masked_rows),
        "masked_rows": masked_rows,
    }
