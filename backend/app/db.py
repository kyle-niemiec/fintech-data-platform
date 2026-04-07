from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

"""
Create the base SQL Alchemy DB session
"""
class Base(DeclarativeBase):
    pass

"""
A function for the Fast API to generate DB session instances with.
"""
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
