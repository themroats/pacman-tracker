"""Shared fixtures for integration tests — provides PostgreSQL-backed test sessions."""

import datetime
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.api.deps import get_current_user


@asynccontextmanager
async def _noop_lifespan(app):
    """No-op lifespan that skips real startup (engine init, bootstrap, etc.)."""
    yield


def _make_test_session():
    """Return a sessionmaker bound to the session-scoped PostGIS testcontainer engine.

    Each call creates all tables (idempotent) and truncates all data so
    integration tests start with a clean slate.
    """
    from tests.conftest import _pg_engine

    Base.metadata.create_all(bind=_pg_engine)

    # Truncate all tables to avoid UniqueViolation between test functions
    with _pg_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
        conn.commit()

    return sessionmaker(bind=_pg_engine, expire_on_commit=False)


def _create_test_user(session):
    """Create a default test user and return it."""
    from app.models.user import User

    user = User(
        strava_athlete_id=99999,
        display_name="Integration Test User",
        access_token_encrypted="enc_test",
        access_token_hash="testhash",
        refresh_token_encrypted="ref_test",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _get_test_app(*, with_auth=True):
    """Create a FastAPI app with noop lifespan, DB overridden, and optional auth bypass.

    Args:
        with_auth: If True (default), override get_current_user to return a test user.

    Returns:
        (app, TestSession, test_user) tuple. test_user is None if with_auth=False.
    """
    from app.main import create_app
    test_app = create_app(custom_lifespan=_noop_lifespan)

    TestSession = _make_test_session()

    # Create a test user for auth if requested
    _test_user = None
    if with_auth:
        _session = TestSession()
        _test_user = _create_test_user(_session)
        _session.close()

    def override_get_db():
        session = TestSession()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    test_app.dependency_overrides[get_db] = override_get_db

    if with_auth and _test_user is not None:
        test_app.dependency_overrides[get_current_user] = lambda: _test_user

    return test_app, TestSession, _test_user
