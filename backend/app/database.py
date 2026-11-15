"""SQLAlchemy engine, SQLite foreign-key enforcement, and session dependency."""

from collections.abc import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Shared SQLAlchemy ORM base class for all database models"""

@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """Enable SQLite foreign key enforcement on every connection, including tests."""
    if type(dbapi_connection).__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def build_sqlite_engine(database_url: str) -> Engine:
    """Create a configured SQLAlchemy Engine for the given database URL."""
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, future=True)


engine = build_sqlite_engine(get_settings().resolved_database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session and closes it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create storage directories and initialize all ORM tables if missing."""
    get_settings().ensure_storage_dirs()
    import app.models # noqa: F401 - ensure all ORM models registered on Base.metadata

    Base.metadata.create_all(bind=engine)