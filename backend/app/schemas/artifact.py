import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.authz import ApiRole
from app.domain.enums import ArtifactFormat, ArtifactStage

"""
Define the minimum data schema to create an artifact.
"""
class ArtifactCreate(BaseModel):
    run_id: uuid.UUID
    stage: ArtifactStage
    format: ArtifactFormat
    storage_path: str

    model_config = ConfigDict(extra="forbid")

"""
Define the expected data schema for reading an artifact.
"""
class ArtifactRead(BaseModel):
    artifact_id: uuid.UUID
    run_id: uuid.UUID
    stage: ArtifactStage
    format: ArtifactFormat
    storage_path: str
    actor_sub: str
    actor_role: ApiRole
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")
