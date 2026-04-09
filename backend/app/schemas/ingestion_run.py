import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.authz import ApiRole
from app.domain.enums import IngestionSource, IngestionStatus

"""
Define the minimum data schema to create an ingestion run
"""
class IngestionRunCreate(BaseModel):
    source_type: IngestionSource
    model_config = ConfigDict(extra="forbid")

"""
Define the expected data schema for reading an ingestion run
"""
class IngestionRunRead(BaseModel):
    run_id: uuid.UUID
    source_type: IngestionSource
    status: IngestionStatus
    actor_sub: str
    actor_role: ApiRole
    started_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True, extra="forbid")
