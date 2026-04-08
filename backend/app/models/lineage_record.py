import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

"""
Define the model for the `lineage_record` table.
"""
class LineageRecord(Base):
    __tablename__ = "lineage_record"

    lineage_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    input_artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    output_artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    transformation: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __init__(
        self,
        run_id: uuid.UUID,
        input_artifact_id: uuid.UUID,
        output_artifact_id: uuid.UUID,
        transformation: str,
    ):
        self.lineage_id = uuid.uuid4()
        self.run_id = run_id
        self.input_artifact_id = input_artifact_id
        self.output_artifact_id = output_artifact_id
        self.transformation = transformation
