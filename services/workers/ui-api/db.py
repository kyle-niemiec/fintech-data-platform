from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings

query_engine = create_engine(settings.event_query_db_url, future=True)
QuerySession = sessionmaker(bind=query_engine, autoflush=False, autocommit=False, future=True)

"""
Create a DB session for the event-query system.
"""
def get_query_db():
    db = QuerySession()

    try:
        yield db
    finally:
        db.close()


# OLTP read-only engine (oltp_ui_reader role). Lazily constructed so that
# the Excel-only stack does not require OLTP credentials at startup.
_oltp_engine = None
_OltpSession = None


def _ensure_oltp_engine():
    global _oltp_engine, _OltpSession
    if _oltp_engine is None:
        _oltp_engine = create_engine(settings.oltp_query_db_url, future=True)
        _OltpSession = sessionmaker(
            bind=_oltp_engine, autoflush=False, autocommit=False, future=True
        )
    return _OltpSession


def get_oltp_db():
    session_cls = _ensure_oltp_engine()
    db = session_cls()
    try:
        yield db
    finally:
        db.close()


# OLTP demo-writer engine (oltp_demo_writer role, INSERT on trading.transaction
# only). Lazily constructed so the read-only stacks need no write credentials.
_demo_oltp_engine = None


def get_demo_oltp_engine():
    global _demo_oltp_engine
    if _demo_oltp_engine is None:
        _demo_oltp_engine = create_engine(settings.oltp_demo_writer_db_url, future=True)
    return _demo_oltp_engine
