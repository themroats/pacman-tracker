"""Tests for PacmanClient HTTP error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from pacman_mcp.client import PacmanClient


def _make_response(status_code: int, json_data: dict | None = None, content_type: str = "application/json") -> httpx.Response:
    """Create a fake httpx.Response."""
    headers = {"content-type": content_type}
    if json_data is not None:
        return httpx.Response(status_code, json=json_data, headers=headers)
    return httpx.Response(status_code, text="error", headers={"content-type": "text/plain"})


class TestClientErrorHandling:
    def setup_method(self):
        self.client = PacmanClient("test-token")

    async def test_401_raises_permission_error(self):
        mock_resp = _make_response(401)
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(PermissionError, match="expired"):
                await self.client.list_cities()

    async def test_404_raises_lookup_error_with_message(self):
        mock_resp = _make_response(404, {"detail": {"message": "City 999 not found"}})
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(LookupError, match="City 999 not found"):
                await self.client.city_coverage(999)

    async def test_404_without_json_body(self):
        mock_resp = _make_response(404, content_type="text/plain")
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(LookupError, match="Not found"):
                await self.client.city_coverage(999)

    async def test_500_raises_http_error(self):
        mock_resp = _make_response(500)
        mock_resp._request = httpx.Request("GET", "http://localhost:8000/api/v1/cities")
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(httpx.HTTPStatusError):
                await self.client.list_cities()

    async def test_post_401_raises_permission_error(self):
        mock_resp = _make_response(401)
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(PermissionError, match="expired"):
                await self.client._post("/test", {"key": "val"})


class TestClientHeaders:
    def test_bearer_token_header(self):
        client = PacmanClient("my-secret-tok")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer my-secret-tok"


class TestClientURLConstruction:
    def test_trailing_slash_stripped(self):
        import os
        with patch.dict(os.environ, {"PACMAN_API_URL": "http://example.com/"}):
            client = PacmanClient("tok")
            assert client._base == "http://example.com"
