import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from app.domain.enums import IngestionSource, IngestionStatus

"""
Define the minimum data schema to create an ingestion run
"""
class IngestionRunCreate(BaseModel):
    source_type: IngestionSource
    triggered_by: str

"""
Define the expected data schema for reading an ingestion run
"""
class IngestionRunRead(BaseModel):
    run_id: uuid.UUID
    source_type: IngestionSource
    status: IngestionStatus
    triggered_by: str
    started_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
