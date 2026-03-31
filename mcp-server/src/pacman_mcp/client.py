"""HTTP client wrapper for the Pacman Tracker backend API."""

from __future__ import annotations

import httpx

from pacman_mcp.config import get_api_url


class PacmanClient:
    """Async HTTP client for the Pacman Tracker backend."""

    def __init__(self, access_token: str) -> None:
        self._base = get_api_url().rstrip("/")
        self._token = access_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self._base}/api/v1{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers(), params=params)
        if resp.status_code == 401:
            raise PermissionError("Authentication failed — token may have expired. Please re-authenticate.")
        if resp.status_code == 404:
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            msg = data.get("detail", {}).get("message", f"Not found: {path}")
            raise LookupError(msg)
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, json_body: dict) -> dict:
        url = f"{self._base}/api/v1{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=self._headers(), json=json_body)
        if resp.status_code == 401:
            raise PermissionError("Authentication failed — token may have expired. Please re-authenticate.")
        resp.raise_for_status()
        return resp.json()

    # --- Cities & Neighborhoods ---

    async def list_cities(self) -> dict:
        return await self._get("/cities")

    async def list_neighborhoods(self, city_id: int) -> dict:
        return await self._get(f"/cities/{city_id}/neighborhoods")

    # --- Coverage ---

    async def city_coverage(self, city_id: int) -> dict:
        return await self._get(f"/coverage/city/{city_id}")

    async def neighborhood_coverage(self, neighborhood_id: int) -> dict:
        return await self._get(f"/coverage/neighborhood/{neighborhood_id}")

    async def city_streets(self, city_id: int, neighborhood_id: int | None = None, status: str | None = None) -> dict:
        params = {}
        if neighborhood_id:
            params["neighborhood_id"] = neighborhood_id
        if status:
            params["status"] = status
        return await self._get(f"/coverage/city/{city_id}/streets", params=params or None)

    # --- Progress ---

    async def overall_stats(self) -> dict:
        return await self._get("/progress/stats")

    async def city_progress(self, city_id: int) -> dict:
        return await self._get(f"/progress/city/{city_id}")

    # --- Health ---

    async def health(self) -> dict:
        """Lightweight call to verify backend is reachable and token is valid."""
        return await self._get("/progress/stats")
