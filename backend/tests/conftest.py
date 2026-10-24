"""
conftest.py — pytest fixtures shared across all tests.

Strategy for integration tests:
  - Create a separate in-memory SQLite engine per test function.
  - Patch the module-level `engine` and `SessionLocal` in session.py so ALL
    internal services (scheduler, cleanup, etc.) use the test database.
  - Override the FastAPI `get_db` dependency with the same session.
"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="function")
def test_engine():
    """Fresh in-memory SQLite engine for each test."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _pragmas(conn, _):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    # Import models and create all tables
    from backend.app.database.session import Base
    import backend.app.models  # register all models  # noqa: F401
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(autouse=True)
def isolate_generated_images(monkeypatch, tmp_path):
    """Keep every image-generation test away from the user's generated assets."""
    from backend.app.core.config import settings

    monkeypatch.setattr(settings, "GENERATED_IMAGES_PATH", str(tmp_path / "generated"))
    monkeypatch.setattr(settings, "FACEBOOK_PAGE_ID", "")
    monkeypatch.setattr(settings, "FACEBOOK_PAGE_ACCESS_TOKEN", "")


@pytest.fixture(scope="function")
def db(test_engine):
    """Transactional test database session."""
    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(test_engine, db, monkeypatch):
    """
    FastAPI TestClient that uses the in-memory test database.
    Patches the module-level engine and SessionLocal so all internal
    services also use the test database.
    """
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from backend.app.database import session as session_module
    from sqlalchemy.orm import sessionmaker

    TestSession = sessionmaker(bind=test_engine)

    def override_db():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    from backend.app.api import auth as auth_api
    from backend.app.core import logging_config
    with patch.object(logging_config, "setup_logging"):
        from backend.app.main import app

    auth_api._login_attempts.clear()

    app.dependency_overrides[session_module.get_db] = override_db

    from backend.app.jobs import scheduler

    with patch.object(session_module, "engine", test_engine), \
         patch.object(session_module, "SessionLocal", TestSession), \
         patch.object(test_engine, "dispose"), \
         patch.object(scheduler, "start_scheduler"), \
         patch.object(scheduler, "stop_scheduler"):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

    auth_api._login_attempts.clear()
    app.dependency_overrides.clear()
