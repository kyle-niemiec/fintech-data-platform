from fastapi import APIRouter, Depends, status
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