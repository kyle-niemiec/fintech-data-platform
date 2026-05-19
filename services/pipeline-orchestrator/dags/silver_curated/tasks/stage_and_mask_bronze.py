from __future__ import annotations

import io
import json
import os
from datetime import timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from airflow.exceptions import AirflowException
from dag_runtime import build_minio_client, now_utc

from curated_specs import resolve_silver_spec
from silver_curated.common import STAGING_PREFIX


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_iso_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # CDC source_ts_ms values are epoch milliseconds.
        if value > 1_000_000_000:
            from datetime import datetime

            return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc).isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()  # datetime/date from pyarrow/pandas
    return str(value)


def _extract_rows_for_domain(*, domain: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from meridian.libs.masking import tokenize

    if domain == "salesforce_opportunity":
        out: list[dict[str, Any]] = []
        for row in rows:
            account_id = row.get("AccountId")
            out.append(
                {
                    "opportunity_id": row.get("Id"),
                    "account_id_token": tokenize(str(account_id), scope="salesforce_account_id") if account_id is not None else None,
                    "name": row.get("Name"),
                    "stage_name": row.get("StageName"),
                    "amount": _to_float(row.get("Amount")),
                    "close_date": _to_iso_date(row.get("CloseDate")),
                    "is_won": row.get("IsWon"),
                    "is_closed": row.get("IsClosed"),
                    "source_system_mod": _to_iso_date(row.get("SystemModstamp")),
                }
            )
        return out

    if domain == "salesforce_account":
        out = []
        for row in rows:
            account_id = row.get("Id")
            out.append(
                {
                    "account_id_token": tokenize(str(account_id), scope="salesforce_account_id") if account_id is not None else None,
                    "name": row.get("Name"),
                    "industry": row.get("Industry"),
                    "annual_revenue": _to_float(row.get("AnnualRevenue")),
                    "number_of_employees": _to_int(row.get("NumberOfEmployees")),
                    "source_system_mod": _to_iso_date(row.get("SystemModstamp")),
                }
            )
        return out

    if domain in {"loan", "loan_payment", "loan_status_history"}:
        out = []
        for row in rows:
            payload_json = row.get("assessed_payload")
            payload = {}
            if isinstance(payload_json, str):
                try:
                    payload = json.loads(payload_json)
                except json.JSONDecodeError:
                    payload = {}

            out.append(
                {
                    "loan_id": row.get("loan_id") or payload.get("loan_id"),
                    "account_id": row.get("account_id") or payload.get("account_id"),
                    "status_code": row.get("status_code") or payload.get("status_code"),
                    "principal_balance": _to_float(row.get("principal_balance") or payload.get("principal_balance")),
                    "days_past_due": _to_int(row.get("days_past_due") or payload.get("days_past_due")),
                    "payment_amount": _to_float(row.get("payment_amount") or payload.get("payment_amount")),
                    "payment_due_date": _to_iso_date(row.get("payment_due_date") or payload.get("payment_due_date")),
                    "payment_posted_at": _to_iso_date(row.get("payment_posted_at") or payload.get("payment_posted_at")),
                    "status_at": _to_iso_date(row.get("status_at") or payload.get("status_at")),
                    "source_lsn": row.get("source_lsn"),
                    "source_system_mod": _to_iso_date(row.get("source_ts_ms") or payload.get("source_system_mod")),
                }
            )
        return out

    if domain == "commission_adjustment":
        out = []
        for row in rows:
            advisor_id = row.get("advisor_id") or row.get("employee_id")
            adjustment_amount = row.get("adjustment_amount")
            if adjustment_amount is None:
                gross = _to_float(row.get("gross_amount")) or 0.0
                net = _to_float(row.get("net_amount")) or 0.0
                adjustment_amount = gross - net
            out.append(
                {
                    "advisor_id": advisor_id,
                    "adjustment_amount": _to_float(adjustment_amount),
                    "adjustment_reason": row.get("adjustment_reason") or "payroll_delta",
                    "adjustment_date": _to_iso_date(row.get("adjustment_date") or row.get("pay_period_end")),
                    "currency": row.get("currency") or "USD",
                }
            )
        return out

    raise AirflowException(f"unsupported silver domain {domain!r}")


def stage_and_mask_bronze(state: dict[str, Any]) -> dict[str, Any]:
    import pyarrow as pa
    import pyarrow.parquet as pq
    from minio.sse import SseKMS

    silver_domain = str(state.get("silver_domain") or "")
    if not silver_domain:
        raise AirflowException("silver domain missing in state")

    # Keep this call for defensive parity with listener/open-run routing.
    bronze_envelope = state.get("bronze_envelope") or {}
    if bronze_envelope:
        _ = resolve_silver_spec(bronze_envelope)

    curated_run_id = state["curated_run_id"]
    bucket = os.environ["MINIO_BUCKET_NAME"]
    kms_key = os.environ["MINIO_KMS_KEY_ID"]

    minio_client = build_minio_client(
        access_key_var="MINIO_TRINO_WRITE_USER",
        secret_key_var="MINIO_TRINO_WRITE_SECRET",
    )
    bronze_tables: list[pa.Table] = []

    for uri in state["bronze_uris"]:
        parsed = urlparse(uri)
        if parsed.scheme != "s3":
            raise AirflowException(f"unexpected bronze uri scheme: {uri}")

        object_key = parsed.path.lstrip("/")
        response = minio_client.get_object(bucket, object_key)
        try:
            body = response.read()
        finally:
            response.close()
            response.release_conn()

        bronze_tables.append(pq.read_table(io.BytesIO(body)))

    if not bronze_tables:
        raise AirflowException("no bronze rows to promote")

    table = pa.concat_tables(bronze_tables, promote=True)
    source_rows = table.to_pylist()
    silver_rows = _extract_rows_for_domain(domain=silver_domain, rows=source_rows)

    staged_table = pa.Table.from_pylist(silver_rows)
    buffer = io.BytesIO()
    pq.write_table(staged_table, buffer, compression="snappy")
    body = buffer.getvalue()
    now = now_utc().astimezone(timezone.utc)

    staged_key = (
        f"{STAGING_PREFIX}/domain={silver_domain}/year={now:%Y}/month={now:%m}/day={now:%d}/"
        f"run_id={curated_run_id}/part-0.parquet"
    )

    minio_client.put_object(
        bucket_name=bucket,
        object_name=staged_key,
        data=io.BytesIO(body),
        length=len(body),
        content_type="application/octet-stream",
        sse=SseKMS(kms_key, {}),
    )

    staged_uri = f"s3://{bucket}/{staged_key}"

    return {
        **state,
        "staged_uri": staged_uri,
        "staged_row_count": len(silver_rows),
        "masked_rows": silver_rows,
    }
