"""
SQLAlchemy engine/session setup.

Uses DATABASE_URL from config (Render Postgres in production, sqlite locally
if unset, so devs can run the app without needing Postgres installed).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a DB session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables if they don't exist yet. Called on app startup for MVP
    simplicity; swap for Alembic migrations once the schema stabilizes."""
    from models import schema  # noqa: F401  (ensures models are registered)

    Base.metadata.create_all(bind=engine)
