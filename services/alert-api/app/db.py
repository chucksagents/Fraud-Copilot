"""
SQLAlchemy engine/session setup. Talks to ALERT_API_DB_URL (sqlite by
default, per infra/.env.example).
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DB_URL

# check_same_thread=False: the Kafka consumer background thread and FastAPI's
# request-handling threads each open their own Session (never share one
# across threads), but SQLite's default driver forbids using a *connection*
# from a different thread than the one that created it unless this is set.
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields one Session per request, always closed
    afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (ensures models are registered on Base)

    Base.metadata.create_all(bind=engine)
