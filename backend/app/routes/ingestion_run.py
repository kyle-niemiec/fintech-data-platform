import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.ingestion_run import IngestionRun
from app.schemas.ingestion_run import IngestionRunCreate, IngestionRunRead

"""
Create a router for handling run-related requests
"""
router = APIRouter(prefix="/runs", tags=["runs"])

"""
Create a route that can handle creating a new ingestion run
"""
@router.post(
    "/",
    response_model=IngestionRunRead,
    status_code=status.HTTP_201_CREATED
)
def create_run(payload: IngestionRunCreate, db: Session = Depends(get_db)):
    run = IngestionRun(
        source_type=payload.source_type,
        triggered_by=payload.triggered_by,
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    return run


"""
Return all ingestion runs ordered by most recent first
"""
@router.get(
    "/",
    response_model=list[IngestionRunRead],
    status_code=status.HTTP_200_OK,
)
def list_runs(db: Session = Depends(get_db)):
    return db.query(IngestionRun).order_by(IngestionRun.started_at.desc()).all()


"""
Return a single ingestion run by ID
"""
@router.get(
    "/{run_id}",
    response_model=IngestionRunRead,
    status_code=status.HTTP_200_OK,
)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(IngestionRun, run_id)

    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    return run
