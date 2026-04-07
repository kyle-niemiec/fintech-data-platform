import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

"""
Define the enum for `ingestion_source` fields
"""
class IngestionSource(str, Enum):
    EXCEL_UPLOAD = "excel_upload"
    SALESFORCE_CRM = "salesforce_crm"
    TRANSACTION_CDC = "transaction_cdc"

"""
Define the enum for `ingestion_status` fields
"""
class IngestionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


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