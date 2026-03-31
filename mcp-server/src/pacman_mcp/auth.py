"""OAuth authentication flow for the MCP server.

Handles:
- Credential caching at ~/.pacman-mcp/credentials.json
- Automated Strava OAuth via temp localhost HTTP server on port 8585
- Token registration with the Pacman Tracker backend
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from pacman_mcp.config import get_api_url, get_strava_client_id, get_strava_client_secret

logger = logging.getLogger(__name__)

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
CALLBACK_PORT = 8585
CREDENTIAL_DIR = Path.home() / ".pacman-mcp"
CREDENTIAL_FILE = CREDENTIAL_DIR / "credentials.json"


def _load_cached_credentials() -> dict | None:
    """Load cached credentials from disk, or None if missing/invalid."""
    if not CREDENTIAL_FILE.exists():
        return None
    try:
        data = json.loads(CREDENTIAL_FILE.read_text())
        if data.get("access_token") and data.get("strava_athlete_id"):
            return data
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def _save_credentials(data: dict) -> None:
    """Save credentials to disk."""
    CREDENTIAL_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIAL_FILE.write_text(json.dumps(data, indent=2))
    # Restrict permissions on Unix-like systems
    try:
        CREDENTIAL_FILE.chmod(0o600)
    except OSError:
        pass


async def _validate_token(access_token: str) -> bool:
    """Check if a cached token is still valid by hitting the backend."""
    try:
        url = f"{get_api_url().rstrip('/')}/api/v1/progress/stats"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {access_token}"})
        return resp.status_code == 200
    except Exception:
        return False


async def _exchange_code(code: str) -> dict:
    """Exchange Strava authorization code for tokens."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": get_strava_client_id(),
                "client_secret": get_strava_client_secret(),
                "code": code,
                "grant_type": "authorization_code",
            },
        )
    resp.raise_for_status()
    return resp.json()


async def _register_with_backend(access_token: str, athlete_id: int) -> dict:
    """Register the MCP token with the backend."""
    url = f"{get_api_url().rstrip('/')}/api/v1/auth/mcp/register"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url,
            json={"access_token": access_token, "strava_athlete_id": athlete_id},
        )
    if resp.status_code == 404:
        raise RuntimeError(
            "No user found for this Strava account. "
            "Please log in through the web app first to create your account."
        )
    resp.raise_for_status()
    return resp.json()


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth callback code."""

    auth_code: str | None = None
    error: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "error" in params:
            _CallbackHandler.error = params["error"][0]
            self._respond("Authentication denied. You can close this tab.")
            return

        code = params.get("code", [None])[0]
        if code:
            _CallbackHandler.auth_code = code
            self._respond(
                "<h2>Pacman Tracker MCP — Authenticated!</h2>"
                "<p>You can close this browser tab and return to your editor.</p>"
            )
        else:
            _CallbackHandler.error = "No authorization code received"
            self._respond("Error: no authorization code received.")

    def _respond(self, body: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        # Suppress default HTTP server logging
        pass


def _run_oauth_flow() -> str:
    """Run the full browser-based Strava OAuth flow. Returns the auth code."""
    # Reset handler state
    _CallbackHandler.auth_code = None
    _CallbackHandler.error = None

    server = HTTPServer(("127.0.0.1", CALLBACK_PORT), _CallbackHandler)

    # Build Strava authorize URL
    params = {
        "client_id": get_strava_client_id(),
        "redirect_uri": f"http://localhost:{CALLBACK_PORT}/callback",
        "response_type": "code",
        "scope": "activity:read_all",
        "approval_prompt": "auto",
    }
    auth_url = f"{STRAVA_AUTH_URL}?{urlencode(params)}"

    logger.info("Opening browser for Strava authentication...")
    webbrowser.open(auth_url)

    # Serve exactly one request (the callback)
    server.handle_request()
    server.server_close()

    if _CallbackHandler.error:
        raise RuntimeError(f"OAuth failed: {_CallbackHandler.error}")
    if not _CallbackHandler.auth_code:
        raise RuntimeError("OAuth failed: no code received")

    return _CallbackHandler.auth_code


async def authenticate() -> str:
    """Authenticate and return a valid access token.

    1. Check cached credentials
    2. Validate cached token against backend
    3. If invalid or missing, run browser OAuth flow
    4. Register token with backend
    5. Cache credentials

    Returns the access_token string.
    """
    # Try cached credentials
    cached = _load_cached_credentials()
    if cached:
        token = cached["access_token"]
        if await _validate_token(token):
            logger.info("Using cached credentials")
            return token
        logger.info("Cached token expired, re-authenticating...")

    # Run browser OAuth flow (blocking HTTP server runs in thread)
    loop = asyncio.get_event_loop()
    code = await loop.run_in_executor(None, _run_oauth_flow)

    # Exchange code for tokens
    token_data = await _exchange_code(code)
    access_token = token_data["access_token"]
    athlete_id = token_data["athlete"]["id"]

    # Register with backend
    registration = await _register_with_backend(access_token, athlete_id)

    # Cache
    _save_credentials({
        "access_token": access_token,
        "strava_athlete_id": athlete_id,
        "user_id": registration.get("user_id"),
        "display_name": registration.get("display_name"),
    })

    logger.info("Authentication successful for %s", registration.get("display_name", "unknown"))
    return access_token
