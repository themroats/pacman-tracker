"""
Strava API client and OAuth service.

Covers:
- Authorization URL generation
- Token exchange + refresh
- Activity fetching (list, detail, streams)
"""

import datetime
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import get_settings

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"


class RateLimitError(Exception):
    """Raised when Strava returns HTTP 429."""

    def __init__(self, retry_after: int = 900):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s")


class StravaAPIError(Exception):
    """Generic Strava API error."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Strava API error {status_code}: {message}")


class TokenRevokedError(Exception):
    """Raised when Strava returns 401 during sync, indicating token revocation."""

    pass


class StravaOAuthService:
    """Handles Strava OAuth2 flow and API calls."""

    def __init__(self):
        settings = get_settings()
        self.client_id = settings.strava_client_id
        self.client_secret = settings.strava_client_secret
        self.redirect_uri = settings.strava_redirect_uri

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------

    def get_authorization_url(self) -> tuple[str, str]:
        """
        Generate Strava OAuth authorization URL with CSRF state token.

        Returns (url, state) tuple.
        """
        state = secrets.token_urlsafe(32)
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "activity:read_all",
            "state": state,
        }
        url = f"{STRAVA_AUTH_URL}?{urlencode(params)}"
        return url, state

    async def exchange_code(self, code: str) -> dict[str, Any]:
        """
        Exchange authorization code for access/refresh tokens.

        Returns dict with athlete_id, display_name, access_token, refresh_token, expires_at.
        """
        data = await self._post_token_exchange(code)
        athlete = data.get("athlete", {})
        return {
            "athlete_id": athlete.get("id"),
            "display_name": f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
            "profile_image_url": athlete.get("profile"),
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_at": datetime.datetime.fromtimestamp(
                data["expires_at"], tz=datetime.UTC
            ),
        }

    async def refresh_tokens(self, refresh_token: str) -> dict[str, Any]:
        """
        Refresh expired access token.

        Returns dict with access_token, refresh_token, expires_at.
        """
        data = await self._post_token_refresh(refresh_token)
        return {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_at": datetime.datetime.fromtimestamp(
                data["expires_at"], tz=datetime.UTC
            ),
        }

    async def _post_token_exchange(self, code: str) -> dict[str, Any]:
        """POST to Strava token endpoint for code exchange."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                STRAVA_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                },
            )
            self._check_response(resp)
            return resp.json()

    async def _post_token_refresh(self, refresh_token: str) -> dict[str, Any]:
        """POST to Strava token endpoint for token refresh."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                STRAVA_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            self._check_response(resp)
            return resp.json()

    # ------------------------------------------------------------------
    # Activity fetching
    # ------------------------------------------------------------------

    async def fetch_activity_list(
        self,
        access_token: str,
        page: int = 1,
        per_page: int = 200,
        after: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch paginated list of athlete's activities.

        Args:
            access_token: Valid Strava access token
            page: Page number (1-indexed)
            per_page: Items per page (max 200)
            after: Only return activities after this epoch timestamp
        """
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if after:
            params["after"] = after

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{STRAVA_API_BASE}/athlete/activities",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            self._check_response(resp)
            return resp.json()

    async def fetch_activity_detail(
        self, access_token: str, activity_id: int
    ) -> dict[str, Any]:
        """Fetch detailed activity data including polyline."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{STRAVA_API_BASE}/activities/{activity_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            self._check_response(resp)
            return resp.json()

    async def fetch_activity_streams(
        self,
        access_token: str,
        activity_id: int,
        stream_types: str = "latlng,altitude",
    ) -> dict[str, Any]:
        """Fetch GPS streams for an activity."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{STRAVA_API_BASE}/activities/{activity_id}/streams",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"keys": stream_types, "key_by_type": "true"},
            )
            self._check_response(resp)
            return resp.json()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_response(resp: httpx.Response) -> None:
        """Check HTTP response and raise appropriate errors."""
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 900))
            raise RateLimitError(retry_after=retry_after)
        if resp.status_code == 401:
            raise TokenRevokedError("Unauthorized — token may be expired or revoked")
        if resp.status_code >= 400:
            raise StravaAPIError(resp.status_code, resp.text)

    async def ensure_valid_token(
        self,
        access_token: str,
        refresh_token: str,
        expires_at: datetime.datetime,
    ) -> dict[str, Any] | None:
        """Check token expiry and refresh if needed (T075).

        Returns a dict with new token data if refreshed, or None if still valid.
        Raises TokenRevokedError if refresh is rejected (T097).
        """
        now = datetime.datetime.now(datetime.UTC)
        # Add 60s buffer to avoid race conditions
        if expires_at > now + datetime.timedelta(seconds=60):
            return None  # Token still valid

        try:
            return await self.refresh_tokens(refresh_token)
        except TokenRevokedError:
            raise
        except StravaAPIError as e:
            if e.status_code == 401:
                raise TokenRevokedError("Refresh token rejected — user may have revoked access")
            raise
