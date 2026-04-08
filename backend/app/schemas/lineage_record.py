import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

"""
Define the minimum data schema to create a lineage record.
"""
class LineageRecordCreate(BaseModel):
    run_id: uuid.UUID
    input_artifact_id: uuid.UUID
    output_artifact_id: uuid.UUID
    transformation: str

"""
Define the expected data schema for reading a lineage record.
"""
class LineageRecordRead(BaseModel):
    lineage_id: uuid.UUID
    run_id: uuid.UUID
    input_artifact_id: uuid.UUID
    output_artifact_id: uuid.UUID
    transformation: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
