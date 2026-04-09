import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_observer, require_writer
from app.db import get_observer_db
from app.dependencies import get_write_db
from app.models.artifact import Artifact
from app.models.ingestion_run import IngestionRun
from app.schemas.artifact import ArtifactCreate, ArtifactRead

router = APIRouter(prefix="/artifacts", tags=["artifacts"])

"""
Register a new artifact for an existing run. Requires operator or pipeline role.
"""
@router.post(
    "/",
    response_model=ArtifactRead,
    status_code=status.HTTP_201_CREATED,
)
def create_artifact(
    payload: ArtifactCreate,
    user: dict = Depends(require_writer),
    db: Session = Depends(get_write_db),
):
    if db.get(IngestionRun, payload.run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    artifact = Artifact(
        run_id=payload.run_id,
        stage=payload.stage,
        format=payload.format,
        storage_path=payload.storage_path,
        actor_sub=user["sub"],
        actor_role=user["role"],
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact

"""
Return all artifacts for a given run, ordered by creation time. Requires observer role or higher.
"""
@router.get(
    "/",
    response_model=list[ArtifactRead],
    status_code=status.HTTP_200_OK,
)
def list_artifacts(
    run_id: uuid.UUID,
    _: dict = Depends(require_observer),
    db: Session = Depends(get_observer_db),
):
    return (
        db.query(Artifact)
        .filter(Artifact.run_id == run_id)
        .order_by(Artifact.created_at.asc())
        .all()
    )

"""
Return a single artifact by ID. Requires observer role or higher.
"""
@router.get(
    "/{artifact_id}",
    response_model=ArtifactRead,
    status_code=status.HTTP_200_OK,
)
def get_artifact(
    artifact_id: uuid.UUID,
    _: dict = Depends(require_observer),
    db: Session = Depends(get_observer_db),
):
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return artifact
