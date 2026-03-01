"""
Contract tests for Strava OAuth integration.

Tests cover:
- Authorization URL generation
- Token exchange (code → tokens)
- Token refresh
"""

import datetime
from unittest.mock import AsyncMock, patch

import pytest

# These tests will fail until the strava service is implemented (Red phase).


class TestStravaOAuthAuthorizeURL:
    """T083: Test authorization URL generation."""

    @pytest.mark.asyncio
    async def test_authorize_url_contains_required_params(self):
        """Authorize URL must include client_id, redirect_uri, scope, state, and response_type."""
        from app.services.strava import StravaOAuthService

        service = StravaOAuthService()
        url, state = service.get_authorization_url()

        assert "https://www.strava.com/oauth/authorize" in url
        assert "client_id=" in url
        assert "redirect_uri=" in url
        assert "scope=activity%3Aread_all" in url or "scope=activity:read_all" in url
        assert "response_type=code" in url
        assert f"state={state}" in url
        assert len(state) >= 16  # CSRF token should be non-trivial

    @pytest.mark.asyncio
    async def test_authorize_url_state_is_unique(self):
        """Each call should produce a unique CSRF state token."""
        from app.services.strava import StravaOAuthService

        service = StravaOAuthService()
        _, state1 = service.get_authorization_url()
        _, state2 = service.get_authorization_url()
        assert state1 != state2


class TestStravaTokenExchange:
    """T083: Test token exchange with recorded responses."""

    MOCK_TOKEN_RESPONSE = {
        "token_type": "Bearer",
        "access_token": "mock_access_token_abc123",
        "refresh_token": "mock_refresh_token_xyz789",
        "expires_at": 1709251200,  # some future timestamp
        "expires_in": 21600,
        "athlete": {
            "id": 12345678,
            "firstname": "Jane",
            "lastname": "Runner",
            "profile": "https://example.com/avatar.jpg",
        },
    }

    @pytest.mark.asyncio
    async def test_exchange_code_returns_user_data(self):
        """Token exchange should return athlete info and encrypted tokens."""
        from app.services.strava import StravaOAuthService

        service = StravaOAuthService()

        with patch.object(
            service, "_post_token_exchange", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = self.MOCK_TOKEN_RESPONSE

            result = await service.exchange_code("test_auth_code")

            assert result["athlete_id"] == 12345678
            assert result["display_name"] == "Jane Runner"
            assert result["access_token"] == "mock_access_token_abc123"
            assert result["refresh_token"] == "mock_refresh_token_xyz789"
            assert "expires_at" in result

    @pytest.mark.asyncio
    async def test_exchange_code_calls_strava_api(self):
        """Token exchange should POST to Strava's token endpoint."""
        from app.services.strava import StravaOAuthService

        service = StravaOAuthService()

        with patch.object(
            service, "_post_token_exchange", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = self.MOCK_TOKEN_RESPONSE

            await service.exchange_code("test_auth_code")

            mock_post.assert_called_once_with("test_auth_code")


class TestStravaTokenRefresh:
    """T083: Test token refresh with recorded responses."""

    MOCK_REFRESH_RESPONSE = {
        "token_type": "Bearer",
        "access_token": "new_access_token_def456",
        "refresh_token": "new_refresh_token_uvw321",
        "expires_at": 1709337600,
        "expires_in": 21600,
    }

    @pytest.mark.asyncio
    async def test_refresh_returns_new_tokens(self):
        """Token refresh should return updated access/refresh tokens."""
        from app.services.strava import StravaOAuthService

        service = StravaOAuthService()

        with patch.object(
            service, "_post_token_refresh", new_callable=AsyncMock
        ) as mock_refresh:
            mock_refresh.return_value = self.MOCK_REFRESH_RESPONSE

            result = await service.refresh_tokens("old_refresh_token")

            assert result["access_token"] == "new_access_token_def456"
            assert result["refresh_token"] == "new_refresh_token_uvw321"
            assert "expires_at" in result
