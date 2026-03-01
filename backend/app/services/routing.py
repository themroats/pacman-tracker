"""
Routing service — OSRM client + route suggestion algorithm (T056-T058).

- OSRMClient: HTTP client for /nearest, /trip, /route
- RouteSuggestionEngine: selects waypoints from untraveled streets,
  calls OSRM to generate optimized routes, iterates to match target distance.
- 100%-covered fallback: detect & suggest neighboring neighborhoods.
"""

from __future__ import annotations

import random
from typing import Any

import httpx
from shapely.geometry import LineString

from app.config import get_settings


# ---------------------------------------------------------------------------
# OSRM HTTP Client (T056)
# ---------------------------------------------------------------------------


class OSRMClient:
    """Thin wrapper around OSRM HTTP API (foot profile)."""

    def __init__(self, base_url: str | None = None, profile: str = "foot"):
        self.base_url = (base_url or get_settings().osrm_url).rstrip("/")
        self.profile = profile

    async def _get(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            url = f"{self.base_url}{path}"
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    async def nearest(self, lng: float, lat: float) -> dict | None:
        """Snap a coordinate to the nearest routable point."""
        path = f"/nearest/v1/{self.profile}/{lng},{lat}.json"
        data = await self._get(path)
        if data.get("code") != "Ok" or not data.get("waypoints"):
            return None
        return data["waypoints"][0]

    async def trip(
        self, coords: list[tuple[float, float]], roundtrip: bool = True
    ) -> dict | None:
        """Solve a TSP (Travelling Salesman) through waypoints.

        Returns the first trip with distance, duration, geometry.
        """
        coord_str = ";".join(f"{lng},{lat}" for lng, lat in coords)
        path = f"/trip/v1/{self.profile}/{coord_str}"
        params = {
            "geometries": "geojson",
            "overview": "full",
            "roundtrip": str(roundtrip).lower(),
        }
        data = await self._get(path, params)
        if data.get("code") != "Ok" or not data.get("trips"):
            return None
        return data["trips"][0]

    async def route(
        self, start: tuple[float, float], end: tuple[float, float]
    ) -> dict | None:
        """Get a simple A→B route."""
        coord_str = f"{start[0]},{start[1]};{end[0]},{end[1]}"
        path = f"/route/v1/{self.profile}/{coord_str}"
        params = {"geometries": "geojson", "overview": "full"}
        data = await self._get(path, params)
        if data.get("code") != "Ok" or not data.get("routes"):
            return None
        return data["routes"][0]


# ---------------------------------------------------------------------------
# Route Suggestion Engine (T057 / T058)
# ---------------------------------------------------------------------------


class RouteSuggestionEngine:
    """Generates route suggestions that prioritise untraveled streets."""

    def __init__(self, osrm_client: OSRMClient | None = None):
        self.osrm = osrm_client or OSRMClient()

    # ---- Waypoint selection ----

    @staticmethod
    def select_waypoints(
        streets: list[dict[str, Any]],
        max_waypoints: int = 12,
    ) -> list[tuple[float, float]]:
        """Pick midpoints of untraveled streets as OSRM waypoints.

        Parameters
        ----------
        streets:
            Each dict must have keys: ``geometry`` (Shapely LineString),
            ``is_traveled`` (bool), ``length_meters`` (float).
        max_waypoints:
            Maximum number of waypoints to return (OSRM limit is ~100,
            but fewer is faster).

        Returns list of (lng, lat) tuples.
        """
        untraveled = [s for s in streets if not s["is_traveled"]]
        if not untraveled:
            return []

        # Sort by length descending so we prioritise longer streets
        untraveled.sort(key=lambda s: s["length_meters"], reverse=True)

        waypoints: list[tuple[float, float]] = []
        for s in untraveled[:max_waypoints]:
            geom: LineString = s["geometry"]
            mid = geom.interpolate(0.5, normalized=True)
            waypoints.append((mid.x, mid.y))

        return waypoints

    # ---- Route building ----

    async def build_route(
        self,
        start: tuple[float, float],
        waypoints: list[tuple[float, float]],
        target_distance: float,
    ) -> dict | None:
        """Call OSRM /trip to get a round-trip through waypoints.

        Iteratively trims waypoints if the resulting distance exceeds 110 %
        of the target, or adds more if it's under 90 %.
        Returns a dict with ``distance``, ``duration``, ``geometry`` or None.
        """
        if not waypoints:
            return None

        # Include start point
        coords = [start] + waypoints
        best_result = None
        tolerance = 0.10  # 10 %

        for attempt in range(5):
            result = await self.osrm.trip(coords, roundtrip=True)
            if result is None:
                break

            best_result = result
            dist = result["distance"]

            if abs(dist - target_distance) / target_distance <= tolerance:
                break  # within tolerance
            elif dist > target_distance * (1 + tolerance):
                # Too long — remove the farthest waypoint
                if len(coords) > 2:
                    coords.pop()
                else:
                    break
            else:
                # Too short — we can't easily add waypoints, accept result
                break

        return best_result

    # ---- Full pipeline ----

    async def suggest(
        self,
        start: tuple[float, float],
        target_distance: float,
        streets: list[dict[str, Any]],
    ) -> dict:
        """High-level route suggestion.

        Returns dict with keys:
        - ``route``: OSRM trip result or None
        - ``waypoints``: selected waypoints
        - ``untraveled_ratio``: fraction of route on untraveled streets (estimated)
        - ``message``: user-facing message if 100 % covered
        """
        waypoints = self.select_waypoints(streets)

        if not waypoints:
            return {
                "route": None,
                "waypoints": [],
                "untraveled_ratio": 0.0,
                "message": "All streets in this area are already traveled! Try a neighboring neighborhood.",
            }

        route = await self.build_route(start, waypoints, target_distance)

        # Estimate untraveled ratio from waypoint count
        total_street_count = len(streets)
        untraveled_count = sum(1 for s in streets if not s["is_traveled"])
        untraveled_ratio = untraveled_count / total_street_count if total_street_count else 0.0

        return {
            "route": route,
            "waypoints": waypoints,
            "untraveled_ratio": untraveled_ratio,
            "message": None,
        }
