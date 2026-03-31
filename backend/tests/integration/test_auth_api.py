"""Integration tests for auth callback endpoint."""

import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models.user import User
from app.models.user_token import UserToken
from app.services.crypto import compute_token_hash
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


def test_auth_callback_creates_user_token():
    """Callback should create a UserToken row with client_name='frontend'."""
    app, TestSession = _get_test_app()
    token_data = {
        "athlete_id": 555555,
        "display_name": "Token Tester",
        "profile_image_url": None,
        "access_token": "frontend-token-abc",
        "refresh_token": "refresh-xyz",
        "expires_at": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
    }

    with patch("app.api.auth._validate_state_token", return_value=True), patch(
        "app.api.auth.StravaOAuthService.exchange_code", new=AsyncMock(return_value=token_data)
    ), patch("app.api.auth._run_background_import", new=AsyncMock(return_value=None)):
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/auth/strava/callback",
                params={"code": "valid-code", "scope": "activity:read_all", "state": "test-state"},
            )

    assert response.status_code == 200

    session = TestSession()
    try:
        user = session.query(User).filter_by(strava_athlete_id=555555).first()
        token = session.query(UserToken).filter_by(user_id=user.id).first()
        assert token is not None
        assert token.client_name == "frontend"
        assert token.token_hash == compute_token_hash("frontend-token-abc")
    finally:
        session.close()


def test_mcp_register_creates_token():
    """POST /auth/mcp/register should create a UserToken with client_name='mcp'."""
    app, TestSession = _get_test_app()

    # Pre-create a user (simulating prior frontend login)
    session = TestSession()
    user = User(
        strava_athlete_id=777777,
        display_name="MCP Tester",
        access_token_encrypted="enc",
        refresh_token_encrypted="ref",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    session.add(user)
    session.commit()
    user_id = user.id
    session.close()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/mcp/register",
            json={"access_token": "mcp-token-xyz", "strava_athlete_id": 777777},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == user_id
    assert body["display_name"] == "MCP Tester"
    assert body["access_token"] == "mcp-token-xyz"

    session = TestSession()
    try:
        token = session.query(UserToken).filter_by(user_id=user_id, client_name="mcp").first()
        assert token is not None
        assert token.token_hash == compute_token_hash("mcp-token-xyz")
    finally:
        session.close()


def test_mcp_register_replaces_old_mcp_token():
    """Registering a new MCP token should remove old MCP tokens for the same user."""
    app, TestSession = _get_test_app()

    session = TestSession()
    user = User(
        strava_athlete_id=888888,
        display_name="Re-auth Tester",
        access_token_encrypted="enc",
        refresh_token_encrypted="ref",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    session.add(user)
    session.commit()
    # Add an existing MCP token
    session.add(UserToken(user_id=user.id, token_hash=compute_token_hash("old-mcp-token"), client_name="mcp"))
    session.commit()
    user_id = user.id
    session.close()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/mcp/register",
            json={"access_token": "new-mcp-token", "strava_athlete_id": 888888},
        )

    assert response.status_code == 200

    session = TestSession()
    try:
        mcp_tokens = session.query(UserToken).filter_by(user_id=user_id, client_name="mcp").all()
        assert len(mcp_tokens) == 1
        assert mcp_tokens[0].token_hash == compute_token_hash("new-mcp-token")
    finally:
        session.close()


def test_mcp_register_unknown_athlete_returns_404():
    """MCP register with unknown strava_athlete_id should return 404."""
    app, TestSession = _get_test_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/mcp/register",
            json={"access_token": "whatever", "strava_athlete_id": 999},
        )

    assert response.status_code == 404


def test_logout_deletes_only_current_token():
    """Logout should delete only the token used in the request, not all tokens."""
    app, TestSession = _get_test_app()

    session = TestSession()
    user = User(
        strava_athlete_id=666666,
        display_name="Logout Tester",
        access_token_encrypted="enc",
        refresh_token_encrypted="ref",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    session.add(user)
    session.commit()
    # Two tokens: frontend and MCP
    session.add(UserToken(user_id=user.id, token_hash=compute_token_hash("frontend-tok"), client_name="frontend"))
    session.add(UserToken(user_id=user.id, token_hash=compute_token_hash("mcp-tok"), client_name="mcp"))
    session.commit()
    user_id = user.id
    session.close()

    with TestClient(app) as client:
        # Logout with the frontend token
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer frontend-tok"},
        )

    assert response.status_code == 200

    session = TestSession()
    try:
        remaining = session.query(UserToken).filter_by(user_id=user_id).all()
        assert len(remaining) == 1
        assert remaining[0].client_name == "mcp"
        assert remaining[0].token_hash == compute_token_hash("mcp-tok")
    finally:
        session.close()


def test_concurrent_frontend_and_mcp_tokens():
    """Both frontend and MCP tokens should authenticate successfully at the same time."""
    app, TestSession = _get_test_app()

    session = TestSession()
    user = User(
        strava_athlete_id=111111,
        display_name="Multi-Token User",
        access_token_encrypted="enc",
        refresh_token_encrypted="ref",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    session.add(user)
    session.commit()
    session.add(UserToken(user_id=user.id, token_hash=compute_token_hash("fe-token"), client_name="frontend"))
    session.add(UserToken(user_id=user.id, token_hash=compute_token_hash("mcp-token"), client_name="mcp"))
    session.commit()
    session.close()

    # Remove the auth override so get_current_user actually queries UserToken
    from app.api.deps import get_current_user
    app.dependency_overrides.pop(get_current_user, None)

    with TestClient(app) as client:
        # Both tokens should work for an authenticated endpoint
        r1 = client.get("/api/v1/cities", headers={"Authorization": "Bearer fe-token"})
        r2 = client.get("/api/v1/cities", headers={"Authorization": "Bearer mcp-token"})

    assert r1.status_code == 200
    assert r2.status_code == 200