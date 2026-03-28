"""Integration tests for auth callback endpoint."""

import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models.user import User
from tests.integration.conftest import _make_test_session, _get_test_app as _get_base_app


def _get_test_app():
    """Create the FastAPI app with test DB override, returns (app, SessionFactory)."""
    app, TestSession, _ = _get_base_app(with_auth=False)
    return app, TestSession


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