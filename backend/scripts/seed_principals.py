"""
Seed initial API principals.

Usage: make seed-principals
Reads passwords from environment (OPERATOR_PASSWORD, OBSERVER_PASSWORD, PIPELINE_PASSWORD).
Inserts or updates principal rows. Safe to run multiple times.
"""
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.auth import hash_password
from app.models.principal import Principal

PRINCIPALS = [
    {"username": "operator", "role": "operator", "env_key": "OPERATOR_PASSWORD"},
    {"username": "observer", "role": "observer", "env_key": "OBSERVER_PASSWORD"},
    {"username": "pipeline", "role": "pipeline", "env_key": "PIPELINE_PASSWORD"},
]


def main():
    db_url = URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["OPERATOR_DB_USER"],
        password=os.environ["OPERATOR_DB_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        database=os.environ["POSTGRES_DB"],
    )

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        for p in PRINCIPALS:
            password = os.environ.get(p["env_key"])
            if not password:
                print(f"  SKIP {p['username']} — {p['env_key']} not set")
                continue

            existing = db.query(Principal).filter(Principal.username == p["username"]).first()
            if existing:
                existing.password_hash = hash_password(password)
                existing.role = p["role"]
                print(f"  UPDATE {p['username']} (role={p['role']})")
            else:
                db.add(Principal(
                    username=p["username"],
                    password_hash=hash_password(password),
                    role=p["role"],
                ))
                print(f"  INSERT {p['username']} (role={p['role']})")

        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
