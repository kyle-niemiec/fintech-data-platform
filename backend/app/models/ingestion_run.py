import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.schemas.ingestion_run import IngestionSource, IngestionStatus

"""
Define the model for the `ingestion_run` table.
"""
class IngestionRun(Base):
    __tablename__ = "ingestion_run"

    "Create a unique run ID for each ingestion"
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    "Map the model enums to the apropriate columns"
    source_type: Mapped[IngestionSource] = mapped_column(
        Enum(IngestionSource, name="ingestion_source", create_type=False),
        nullable=False,
    )

    status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus, name="ingestion_status", create_type=False),
        nullable=False,
    )

    "Store up basic run info for user and time"
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __init__(self, source_type: IngestionSource, triggered_by: str):
        self.run_id = uuid.uuid4()
        self.source_type = source_type
        self.status = IngestionStatus.PENDING
        self.triggered_by = triggered_by