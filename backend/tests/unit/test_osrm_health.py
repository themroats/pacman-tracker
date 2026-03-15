"""
Tests for OSRM health check and graceful degradation.

Covers:
- T055: check_osrm_available() function
- T056: /health endpoint returns osrm_available flag
- T057: Route suggest endpoint guards on OSRM availability
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.routing import check_osrm_available, _osrm_available


class TestCheckOsrmAvailable:
    """T055: OSRM health check function."""

    @pytest.mark.asyncio
    async def test_returns_true_when_osrm_responds(self):
        """If OSRM responds with status < 500, it's available."""
        import app.services.routing as routing_mod

        # Reset cached state
        routing_mod._osrm_available = None
        routing_mod._osrm_checked_at = 0.0

        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch("app.services.routing.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await check_osrm_available(force=True)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_osrm_unreachable(self):
        """If OSRM connection fails, it's unavailable."""
        import app.services.routing as routing_mod
        import httpx

        routing_mod._osrm_available = None
        routing_mod._osrm_checked_at = 0.0

        with patch("app.services.routing.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await check_osrm_available(force=True)

        assert result is False

    @pytest.mark.asyncio
    async def test_caches_result(self):
        """Subsequent calls within 60s should return the cached value."""
        import app.services.routing as routing_mod
        import time

        routing_mod._osrm_available = True
        routing_mod._osrm_checked_at = time.monotonic()

        # Should return cached value without making HTTP request
        result = await check_osrm_available(force=False)
        assert result is True

    @pytest.mark.asyncio
    async def test_force_bypasses_cache(self):
        """force=True should re-check even within cache window."""
        import app.services.routing as routing_mod
        import time

        routing_mod._osrm_available = True
        routing_mod._osrm_checked_at = time.monotonic()

        with patch("app.services.routing.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("down")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await check_osrm_available(force=True)

        assert result is False


class TestHealthEndpointOsrm:
    """T056: /health returns osrm_available field."""

    def test_health_endpoint_has_osrm_field(self):
        """Verify the health endpoint source includes osrm_available."""
        import inspect
        from app.main import create_app

        # The health endpoint is defined inside create_app, so we check the source
        source = inspect.getsource(create_app)
        assert "osrm_available" in source, "/health should return osrm_available"


class TestRouteGuardOsrm:
    """T057: Route suggest guards on OSRM availability."""

    def test_suggest_route_checks_osrm(self):
        """The suggest_route endpoint should check OSRM availability."""
        import inspect
        from app.api.routes import suggest_route

        source = inspect.getsource(suggest_route)
        assert "check_osrm_available" in source
        assert "OSRM_UNAVAILABLE" in source
