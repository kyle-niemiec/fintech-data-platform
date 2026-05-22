"""POST /ui/demo/backfill/* — synthetic historical data for backfill demos.

Excel backfill scenario (Meridian):
  Compensation Operations discovered that a commission adjustment file was
  submitted with incorrect currency codes due to a template error. The
  corrected file must be ingested with the original effective dates so that
  kpi_commission_economics reflects accurate Q1 figures. The backfill endpoint
  generates a workbook anchored to the given target_date and uploads it through
  the same landing path as a normal upload — so the full scan → validate →
  bronze pipeline runs unchanged, and the resulting run is traceable in the
  Runs Explorer.

CDC backfill scenario (Meridian):
  A batch of loan disbursements settled yesterday but was delayed in reaching
  the OLTP database due to a core-banking maintenance window. Inserting with
  the original executed_at timestamp lets the fraud scorer process the
  transaction with the correct settlement date, keeping daily metrics and
  loan_status_history lineage accurate.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from db import get_demo_oltp_engine
from services.cdc_demo import create_demo_transaction
from services.demo_finance import local_part, resolve_demo_user
from services.demo_xlsx import (
    generate_commission_adjustment_xlsx,
    generate_payroll_xlsx,
)
from services.keycloak_users import KeycloakError
from services.minio_upload import MinioUploadError, put_xlsx

router = APIRouter(prefix="/ui/demo/backfill", tags=["ui-demo"])

_BACKFILL_MAX_YEARS = 2


def _validate_backfill_date(target: date) -> None:
    today = datetime.now(timezone.utc).date()
    if target >= today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="target_date must be before today",
        )
    earliest = today - timedelta(days=365 * _BACKFILL_MAX_YEARS)
    if target < earliest:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"target_date cannot be more than {_BACKFILL_MAX_YEARS} years in the past",
        )


def _validate_backfill_datetime(target: datetime) -> None:
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if target >= now:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="target_date must be before the current time",
        )
    earliest = now - timedelta(days=365 * _BACKFILL_MAX_YEARS)
    if target < earliest:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"target_date cannot be more than {_BACKFILL_MAX_YEARS} years in the past",
        )


class ExcelBackfillRequest(BaseModel):
    target_date: date
    rows: int = Field(default=25, ge=1, le=500)
    dataset: Literal["payroll", "commission_adjustment"] = "commission_adjustment"


class ExcelBackfillResponse(BaseModel):
    run_trigger_ref: str
    object_key: str
    bucket: str
    demo_user: str
    rows: int
    size_bytes: int
    target_date: date
    dataset: str
    generated_at: datetime


class CdcBackfillRequest(BaseModel):
    target_date: datetime
    high_risk: bool = Field(default=False)


class CdcBackfillResponse(BaseModel):
    transaction_id: UUID
    account_id: UUID
    instrument: str
    amount: Decimal
    executed_at: datetime
    high_risk: bool
    target_date: datetime


@router.post("/excel", response_model=ExcelBackfillResponse, status_code=status.HTTP_200_OK)
def post_backfill_excel(payload: ExcelBackfillRequest) -> ExcelBackfillResponse:
    _validate_backfill_date(payload.target_date)

    try:
        demo_user = resolve_demo_user()
    except KeycloakError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not resolve finance users from Keycloak: {exc}",
        ) from exc

    if payload.dataset == "commission_adjustment":
        xlsx_bytes, rows = generate_commission_adjustment_xlsx(
            payload.rows, target_date=payload.target_date
        )
        file_prefix = "commission_adjustment"
    else:
        xlsx_bytes, rows = generate_payroll_xlsx(
            payload.rows, target_date=payload.target_date
        )
        file_prefix = "payroll"

    now = datetime.now(timezone.utc)
    uploader_segment = local_part(demo_user)
    object_run_id = uuid4()
    # Upload to the same landing/source=excel/ path so the MinIO bucket
    # notification fires and the full scanner → trigger → DAG chain runs.
    # The backfill_ filename prefix is what allows the UI to badge the run.
    key = (
        f"landing/source=excel/"
        f"year={payload.target_date:%Y}/month={payload.target_date:%m}/day={payload.target_date:%d}/"
        f"run_id={object_run_id}/"
        f"backfill_{payload.target_date}_{file_prefix}_{uploader_segment}_{now:%Y%m%d}_{object_run_id}.xlsx"
    )

    try:
        result = put_xlsx(key=key, body=xlsx_bytes, demo_uploader=demo_user)
    except MinioUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"MinIO upload failed: {exc}",
        ) from exc

    return ExcelBackfillResponse(
        run_trigger_ref=f"minio:{result.bucket}:{result.key}:{result.etag}",
        object_key=result.key,
        bucket=result.bucket,
        demo_user=demo_user,
        rows=rows,
        size_bytes=result.size_bytes,
        target_date=payload.target_date,
        dataset=payload.dataset,
        generated_at=now,
    )


@router.post("/cdc", response_model=CdcBackfillResponse, status_code=status.HTTP_201_CREATED)
def post_backfill_cdc(payload: CdcBackfillRequest) -> CdcBackfillResponse:
    target_dt = payload.target_date
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)
    _validate_backfill_datetime(target_dt)

    try:
        txn = create_demo_transaction(
            get_demo_oltp_engine(),
            high_risk=payload.high_risk,
            now=target_dt,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OLTP write failed: {exc}",
        ) from exc

    return CdcBackfillResponse(
        transaction_id=txn.transaction_id,
        account_id=txn.account_id,
        instrument=txn.instrument,
        amount=txn.amount,
        executed_at=txn.executed_at,
        high_risk=txn.high_risk,
        target_date=target_dt,
    )
