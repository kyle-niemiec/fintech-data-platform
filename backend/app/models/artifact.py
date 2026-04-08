import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.domain.enums import ArtifactFormat, ArtifactStage

"""
Define the model for the `artifact` table.
"""
class Artifact(Base):
    __tablename__ = "artifact"

    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    stage: Mapped[ArtifactStage] = mapped_column(
        Enum(ArtifactStage, name="artifact_stage", create_type=False),
        nullable=False,
    )
    format: Mapped[ArtifactFormat] = mapped_column(
        Enum(ArtifactFormat, name="artifact_format", create_type=False),
        nullable=False,
    )

    storage_path: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __init__(self, run_id: uuid.UUID, stage: ArtifactStage, format: ArtifactFormat, storage_path: str):
        self.artifact_id = uuid.uuid4()
        self.run_id = run_id
        self.stage = stage
        self.format = format
        self.storage_path = storage_path
