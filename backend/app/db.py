from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

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
