# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        db_url = os.environ.get("DATABASE_URL")
        print(f"Using database URL: {db_url}")
        if not db_url:
            raise RuntimeError("DATABASE_URL not set")
        _engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False}
        )
    return _engine


def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine()
        )
    return _SessionLocal()
