import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_observer
from app.db import get_observer_db
from app.dependencies import get_write_db
from app.models.artifact import Artifact
from app.models.ingestion_run import IngestionRun
from app.models.lineage_record import LineageRecord
from app.schemas.lineage_record import LineageRecordCreate, LineageRecordRead

router = APIRouter(prefix="/lineage", tags=["lineage"])

"""
Register a lineage relationship between two artifacts within a run. Requires operator or pipeline role.

Validates that the run and both artifacts exist, that both artifacts belong to the stated
run, and that the input and output artifacts are distinct.
"""
@router.post(
    "/",
    response_model=LineageRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def create_lineage_record(
    payload: LineageRecordCreate,
    db: Session = Depends(get_write_db),
):
    if db.get(IngestionRun, payload.run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    input_artifact = db.get(Artifact, payload.input_artifact_id)
    if input_artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input artifact not found")

    output_artifact = db.get(Artifact, payload.output_artifact_id)
    if output_artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output artifact not found")

    if payload.input_artifact_id == payload.output_artifact_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Input and output artifacts must differ",
        )

    if input_artifact.run_id != payload.run_id or output_artifact.run_id != payload.run_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Both artifacts must belong to the stated run",
        )

    record = LineageRecord(
        run_id=payload.run_id,
        input_artifact_id=payload.input_artifact_id,
        output_artifact_id=payload.output_artifact_id,
        transformation=payload.transformation,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

"""
Return all lineage records for a given run, ordered by creation time. Requires observer role or higher.
"""
@router.get(
    "/",
    response_model=list[LineageRecordRead],
    status_code=status.HTTP_200_OK,
)
def list_lineage(
    run_id: uuid.UUID,
    _: dict = Depends(require_observer),
    db: Session = Depends(get_observer_db),
):
    return (
        db.query(LineageRecord)
        .filter(LineageRecord.run_id == run_id)
        .order_by(LineageRecord.created_at.asc())
        .all()
    )
