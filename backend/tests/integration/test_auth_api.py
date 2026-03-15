"""Integration tests for auth callback endpoint."""

import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.user import User


def _make_test_session():
    """Create an in-memory SQLite session with SpatiaLite for integration tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    spatialite_loaded = False

    @event.listens_for(engine, "connect")
    def _load_spatialite(dbapi_conn, connection_record):
        nonlocal spatialite_loaded
        dbapi_conn.enable_load_extension(True)
        for lib_name in ("mod_spatialite", "libspatialite"):
            try:
                dbapi_conn.load_extension(lib_name)
                spatialite_loaded = True
                break
            except Exception:
                continue
        dbapi_conn.enable_load_extension(False)

    with engine.connect() as conn:
        try:
            conn.execute(text("SELECT InitSpatialMetaData(1)"))
            conn.commit()
        except Exception:
            pytest.skip("SpatiaLite extension not available")

    if not spatialite_loaded:
        pytest.skip("SpatiaLite extension not available")

    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _get_test_app():
    """Create the FastAPI app with test DB override."""
    from app.main import create_app

    test_app = create_app()
    TestSession = _make_test_session()

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
    return test_app, TestSession


def test_auth_callback_returns_session_and_persists_user():
    """Successful callback should return JSON and create the user record."""
    app, TestSession = _get_test_app()
    token_data = {
        "athlete_id": 424242,
        "display_name": "Otis Runner",
        "profile_image_url": "https://example.com/avatar.png",
        "access_token": "access-token-123",
        "refresh_token": "refresh-token-456",
        "expires_at": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
    }

    with patch("app.api.auth._validate_state_token", return_value=True), patch(
        "app.api.auth.StravaOAuthService.exchange_code", new=AsyncMock(return_value=token_data)
    ), patch("app.api.auth._run_background_import", new=AsyncMock(return_value=None)):
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/auth/strava/callback",
                params={
                    "code": "valid-code",
                    "scope": "activity:read_all",
                    "state": "test-state",
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Otis Runner"
    assert body["access_token"] == "access-token-123"
    assert body["sync_status"] == "importing"

    session = TestSession()
    try:
        user = session.query(User).filter_by(strava_athlete_id=424242).first()
        assert user is not None
        assert user.display_name == "Otis Runner"
        assert user.sync_status == "importing"
    finally:
        session.close()