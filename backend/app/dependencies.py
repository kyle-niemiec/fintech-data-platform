from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth import require_writer
from app.db import OperatorSession, ObserverSession, PipelineSession
from app.domain.authz import ApiRole

ROLE_SESSION_MAP = {
    ApiRole.operator.value: OperatorSession,
    ApiRole.observer.value: ObserverSession,
    ApiRole.pipeline.value: PipelineSession,
}

"""
Create a DB session to use based on the user role.
"""
def get_write_db(user: dict = Depends(require_writer)) -> Session:
    session_cls = ROLE_SESSION_MAP[user["role"]]
    db = session_cls()

    try:
        yield db
    finally:
        db.close()
