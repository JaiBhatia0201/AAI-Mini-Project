"""Shared pytest fixtures for backend unit and integration tests."""

import sys
from collections.abc import Generator
from pathlib import Path
import pytest
from sqlalchemy.orm import Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base, build_sqlite_engine  # noqa: E402
import app.models  # noqa: E402, F401 — ensure all 13 ORM tables register on Base


@pytest.fixture()
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    """Provide an isolated temporary SQLite session with PRAGMA foreign_keys=ON."""
    db_file = tmp_path / "test_adaptive_tutor.db"
    test_engine = build_sqlite_engine(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(bind=test_engine)

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
        class_=Session,
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        test_engine.dispose()

