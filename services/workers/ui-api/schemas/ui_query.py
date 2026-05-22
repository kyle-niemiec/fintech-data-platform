from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Envelope for a single page of a list endpoint.

    `total` is the count of rows matching the filters before `limit`/`offset`,
    so the UI can render page controls without a second request.
    """

    items: list[T]
    total: int
    limit: int
    offset: int


class RunSummary(BaseModel):
    run_id: UUID
    pipeline_class: str
    pipeline_name: str
    source_system: str
    status: str
    latest_stage: str | None
    started_at: datetime
    completed_at: datetime | None
    is_backfill: bool = False


class RunDetail(BaseModel):
    run_id: UUID
    pipeline_class: str
    pipeline_name: str
    source_system: str
    trigger_type: str
    trigger_event_ref: str
    status: str
    initiator: str
    parent_run_id: UUID | None
    started_at: datetime
    completed_at: datetime | None
    latest_stage: str | None
    is_backfill: bool = False


class ArtifactTrailItem(BaseModel):
    event_id: UUID
    occurred_at: datetime
    stage: str | None
    artifact_role: str
    format: str | None
    uri: str
    event_type: str


class LineageTrailItem(BaseModel):
    event_id: UUID
    occurred_at: datetime
    stage: str | None
    input_uris: list[str]
    output_uris: list[str]
    transform_id: str | None
    transform_version: str | None
    event_type: str


class RunEventItem(BaseModel):
    occurred_at: datetime
    event_type: str
    source: str
    run_id: UUID
    trace_id: UUID | None
    message: str | None


class RecentTransactionItem(BaseModel):
    transaction_id: UUID
    account_id: UUID
    instrument: str
    amount: Decimal
    executed_at: datetime
    risk_score: Decimal | None
    risk_flags: list[str] | None


class AlertItem(BaseModel):
    alert_id: UUID
    run_id: UUID
    severity: str
    category: str
    summary: str
    details: dict[str, Any]
    occurred_at: datetime
