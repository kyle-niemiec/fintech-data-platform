from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

"Import connection strings from the settings"
operator_engine = create_engine(settings.operator_db_url, future=True)
observer_engine = create_engine(settings.observer_db_url, future=True)
pipeline_engine = create_engine(settings.pipeline_db_url, future=True)
auth_engine = create_engine(settings.auth_db_url, future=True)

"Create DB sessions for each role independently"
OperatorSession = sessionmaker(bind=operator_engine, autoflush=False, autocommit=False, future=True)
ObserverSession = sessionmaker(bind=observer_engine, autoflush=False, autocommit=False, future=True)
PipelineSession = sessionmaker(bind=pipeline_engine, autoflush=False, autocommit=False, future=True)
AuthSession = sessionmaker(bind=auth_engine, autoflush=False, autocommit=False, future=True)

"""
Base is bound to the operator engine as the authoritative schema reflection source.
"""
class Base(DeclarativeBase):
    pass

"""
DB session for write operations (control_plane_writer / api_runtime login user).
"""
def get_operator_db():
    db = OperatorSession()

    try:
        yield db
    finally:
        db.close()

"""
DB session for read operations (control_plane_reader / audit_runtime login user).
"""
def get_observer_db():
    db = ObserverSession()

    try:
        yield db
    finally:
        db.close()

"""
DB session for pipeline write operations (ingestion_writer / api_pipeline login user).
"""
def get_pipeline_db():
    db = PipelineSession()

    try:
        yield db
    finally:
        db.close()

"""
DB session for authentication queries (auth_reader / api_auth login user).
SELECT-only access to the principal table.
"""
def get_auth_db():
    db = AuthSession()

    try:
        yield db
    finally:
        db.close()
