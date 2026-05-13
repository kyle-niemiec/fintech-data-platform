"""POST /ui/demo/upload — generate a valid payroll xlsx and upload it to MinIO."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.services.demo_xlsx import (
    generate_commission_adjustment_xlsx,
    generate_payroll_xlsx,
)
from app.services.minio_upload import MinioUploadError, put_xlsx

router = APIRouter(prefix="/ui/demo", tags=["ui-demo"])


class DemoUploadRequest(BaseModel):
    rows: int = Field(default=25, ge=1, le=500)
    dataset: Literal["payroll", "commission_adjustment"] = "payroll"


class DemoUploadResponse(BaseModel):
    run_trigger_ref: str
    object_key: str
    bucket: str
    demo_user: str
    rows: int
    size_bytes: int
    generated_at: datetime
    schema_contract_id: str


def _local_part(email: str) -> str:
    return email.split("@", 1)[0]


@router.post("/upload", response_model=DemoUploadResponse, status_code=status.HTTP_200_OK)
def post_demo_upload(payload: DemoUploadRequest | None = None) -> DemoUploadResponse:
    req = payload or DemoUploadRequest()

    users = settings.demo_finance_users_list
    if not users:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No demo finance users configured",
        )
    demo_user = random.choice(users)

    if req.dataset == "commission_adjustment":
        xlsx_bytes, rows = generate_commission_adjustment_xlsx(req.rows)
        contract_id = "commission_adjustment_v1"
        file_prefix = "commission_adjustment"
    else:
        xlsx_bytes, rows = generate_payroll_xlsx(req.rows)
        contract_id = "payroll_v1"
        file_prefix = "payroll"

    now = datetime.now(timezone.utc)
    uploader_segment = _local_part(demo_user)
    object_run_id = uuid4()
    key = (
        f"landing/source=excel/year={now:%Y}/month={now:%m}/day={now:%d}/"
        f"run_id={object_run_id}/{file_prefix}_{uploader_segment}_{now:%Y%m%d}_{object_run_id}.xlsx"
    )

    try:
        result = put_xlsx(key=key, body=xlsx_bytes, demo_uploader=demo_user)
    except MinioUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"MinIO upload failed: {exc}",
        ) from exc

    trigger_ref = f"minio:{result.bucket}:{result.key}:{result.etag}"

    return DemoUploadResponse(
        run_trigger_ref=trigger_ref,
        object_key=result.key,
        bucket=result.bucket,
        demo_user=demo_user,
        rows=rows,
        size_bytes=result.size_bytes,
        generated_at=now,
        schema_contract_id=contract_id,
    )
