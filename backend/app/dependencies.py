from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth import require_writer
from app.db import OperatorSession, ObserverSession, PipelineSession

ROLE_SESSION_MAP = {
    "operator": OperatorSession,
    "observer": ObserverSession,
    "pipeline": PipelineSession,
}

"""
Combined auth + session dependency for write endpoints.

Selects the appropriate DB session based on the caller's role:
  - operator → OperatorSession (control_plane_writer)
  - pipeline → PipelineSession (ingestion_writer)

Auth is enforced implicitly via require_writer. Routes that use this
dependency do not need a separate auth dependency.
"""
def get_write_db(user: dict = Depends(require_writer)) -> Session:
    session_cls = ROLE_SESSION_MAP[user["role"]]
    db = session_cls()

    try:
        yield db
    finally:
        db.close()
