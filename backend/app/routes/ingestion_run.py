import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_observer, require_writer
from app.db import get_observer_db
from app.dependencies import get_write_db
from app.models.ingestion_run import IngestionRun
from app.schemas.ingestion_run import IngestionRunCreate, IngestionRunRead

router = APIRouter(prefix="/runs", tags=["runs"])

"""
Create a new ingestion run. Requires operator or pipeline role.
"""
@router.post(
    "/",
    response_model=IngestionRunRead,
    status_code=status.HTTP_201_CREATED,
)
def create_run(
    payload: IngestionRunCreate,
    user: dict = Depends(require_writer),
    db: Session = Depends(get_write_db),
):
    run = IngestionRun(
        source_type=payload.source_type,
        actor_sub=user["sub"],
        actor_role=user["role"],
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    return run

"""
Return all ingestion runs ordered by most recent first. Requires observer role or higher.
"""
@router.get(
    "/",
    response_model=list[IngestionRunRead],
    status_code=status.HTTP_200_OK,
)
def list_runs(
    _: dict = Depends(require_observer),
    db: Session = Depends(get_observer_db),
):
    return db.query(IngestionRun).order_by(IngestionRun.started_at.desc()).all()

"""
Return a single ingestion run by ID. Requires observer role or higher.
"""
@router.get(
    "/{run_id}",
    response_model=IngestionRunRead,
    status_code=status.HTTP_200_OK,
)
def get_run(
    run_id: uuid.UUID,
    _: dict = Depends(require_observer),
    db: Session = Depends(get_observer_db),
):
    run = db.get(IngestionRun, run_id)

    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    return run
