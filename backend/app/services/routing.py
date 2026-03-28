"""
Routing service — OSRM client + route suggestion algorithm (T056-T058).

- OSRMClient: HTTP client for /nearest, /trip, /route
- RouteSuggestionEngine: selects waypoints from untraveled streets,
  calls OSRM to generate optimized routes, iterates to match target distance.
- RoutePlannerService: orchestrates full route suggestion flow including
  DB queries, coverage lookup, OSRM routing, fallback, and persistence.
- 100%-covered fallback: detect & suggest neighboring neighborhoods.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import LineString, Point
from sqlalchemy.orm import Session

from app.config import get_settings


class OSRMUnavailableError(Exception):
    """Raised when the OSRM server cannot be reached."""


# ---------------------------------------------------------------------------
# OSRM Health Check
# ---------------------------------------------------------------------------

_osrm_available: bool | None = None
_osrm_checked_at: float = 0.0
_OSRM_CHECK_INTERVAL = 60  # seconds

_logger = logging.getLogger(__name__)


async def check_osrm_available(force: bool = False) -> bool:
    """Ping OSRM and cache the result for 60 seconds."""
    global _osrm_available, _osrm_checked_at
    now = time.monotonic()
    if not force and _osrm_available is not None and (now - _osrm_checked_at) < _OSRM_CHECK_INTERVAL:
        return _osrm_available

    try:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.osrm_url.rstrip('/')}/nearest/v1/foot/0,0.json")
            # OSRM returns 200 even for invalid coords; a connection success means it's up
            _osrm_available = resp.status_code < 500
    except Exception:
        _osrm_available = False
        _logger.warning("OSRM health check failed — route suggestions will be unavailable")

    _osrm_checked_at = now
    return _osrm_available


# ---------------------------------------------------------------------------
# OSRM HTTP Client (T056)
# ---------------------------------------------------------------------------


class OSRMClient:
    """Thin wrapper around OSRM HTTP API (foot profile)."""

    def __init__(self, base_url: str | None = None, profile: str = "foot"):
        self.base_url = (base_url or get_settings().osrm_url).rstrip("/")
        self.profile = profile

    async def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = f"{self.base_url}{path}"
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError:
            raise OSRMUnavailableError(
                "OSRM routing server is not reachable. "
                "Start it with: docker compose up osrm -d"
            )
        except httpx.HTTPStatusError as exc:
            raise OSRMUnavailableError(
                f"OSRM returned an error: {exc.response.status_code}"
            )

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


# ---------------------------------------------------------------------------
# Route Planner Service (T103 — extracted from routes.py endpoint)
# ---------------------------------------------------------------------------


class RoutePlannerService:
    """Orchestrates the full route suggestion flow.

    Responsibilities (previously inline in the ``suggest_route`` endpoint):
    - Query street segments and coverage data from the DB
    - Prepare streets for :class:`RouteSuggestionEngine`
    - Call OSRM via the engine to generate a route
    - Handle the 100 %-covered fallback (suggest neighborhoods)
    - Persist :class:`RouteSuggestion` and :class:`RouteSuggestionSegment`
    - Return the API-ready response dict
    """

    def __init__(
        self,
        db: Session,
        engine: RouteSuggestionEngine | None = None,
    ):
        self.db = db
        self.engine = engine or RouteSuggestionEngine()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def suggest(
        self,
        *,
        user_id: int,
        city_id: int,
        neighborhood_id: int | None,
        start_lng: float,
        start_lat: float,
        distance_meters: float,
    ) -> dict:
        """Generate, persist, and return a route suggestion.

        Returns a dict ready to be serialised as the JSON response body.
        """
        from app.models.coverage import UserStreetCoverage
        from app.models.neighborhood import Neighborhood
        from app.models.route import RouteSuggestion, RouteSuggestionSegment
        from app.models.street import StreetSegment

        # 1. Query streets (optionally filtered by neighborhood) ----------
        street_query = self.db.query(StreetSegment).filter_by(city_id=city_id)
        if neighborhood_id:
            street_query = street_query.filter_by(neighborhood_id=neighborhood_id)
        else:
            # Without a neighborhood filter we'd load 300k+ streets which is
            # too many for waypoint selection.  Narrow to a bbox around the
            # start point (~2 km radius) using PostGIS GiST spatial index.
            from geoalchemy2 import functions as gfunc
            from app.services.coverage import _approx_buffer_degrees

            pad = _approx_buffer_degrees(2000)  # ~2 km in degrees
            bbox = gfunc.ST_MakeEnvelope(
                start_lng - pad, start_lat - pad,
                start_lng + pad, start_lat + pad,
                4326,
            )
            street_query = (
                street_query
                .filter(StreetSegment.geometry.intersects(bbox))
            )

        db_streets = street_query.all()

        if not db_streets:
            return {"error": "NOT_FOUND", "message": "No streets found in this area"}

        # 2. Build coverage lookup ----------------------------------------
        #    Use a single query to avoid SQLite variable limits with large
        #    street lists.  Fetch coverage for this user where street is in
        #    the same city (fast index scan).
        cov_id_set: set[int] = set()
        if neighborhood_id:
            cov_rows = (
                self.db.query(UserStreetCoverage.street_segment_id)
                .join(StreetSegment, StreetSegment.id == UserStreetCoverage.street_segment_id)
                .filter(
                    UserStreetCoverage.user_id == user_id,
                    StreetSegment.neighborhood_id == neighborhood_id,
                )
                .all()
            )
            cov_id_set = {r[0] for r in cov_rows}
        else:
            # Use same PostGIS bbox to scope the coverage lookup
            from geoalchemy2 import functions as gfunc2
            from app.services.coverage import _approx_buffer_degrees as _abd2
            pad2 = _abd2(2000)
            bbox2 = gfunc2.ST_MakeEnvelope(
                start_lng - pad2, start_lat - pad2,
                start_lng + pad2, start_lat + pad2,
                4326,
            )
            cov_rows = (
                self.db.query(UserStreetCoverage.street_segment_id)
                .join(StreetSegment, StreetSegment.id == UserStreetCoverage.street_segment_id)
                .filter(
                    UserStreetCoverage.user_id == user_id,
                    StreetSegment.geometry.intersects(bbox2),
                )
                .all()
            )
            cov_id_set = {r[0] for r in cov_rows}
        cov_map = {sid: True for sid in cov_id_set}

        # 3. Prepare streets for the engine -------------------------------
        streets_for_engine: list[dict[str, Any]] = []
        for s in db_streets:
            try:
                geom = to_shape(s.geometry)
            except Exception:
                continue
            streets_for_engine.append(
                {
                    "id": s.id,
                    "geometry": geom,
                    "length_meters": s.length_meters,
                    "is_traveled": cov_map.get(s.id, False),
                    "name": s.name,
                }
            )

        # 4. Call the suggestion engine -----------------------------------
        try:
            result = await self.engine.suggest(
                start=(start_lng, start_lat),
                target_distance=distance_meters,
                streets=streets_for_engine,
            )
        except OSRMUnavailableError as exc:
            return {"error": "OSRM_UNAVAILABLE", "message": str(exc)}

        # 5. 100 %-covered fallback ---------------------------------------
        if result["route"] is None:
            return self._fallback_response(city_id, cov_map, result, Neighborhood)

        # 6. Persist the suggestion ---------------------------------------
        route_data = result["route"]
        route_geom = LineString(
            [(c[0], c[1]) for c in route_data["geometry"]["coordinates"]]
        )
        untraveled_dist = route_data["distance"] * result["untraveled_ratio"]

        suggestion = RouteSuggestion(
            user_id=user_id,
            city_id=city_id,
            neighborhood_id=neighborhood_id,
            start_point=from_shape(Point(start_lng, start_lat), srid=4326),
            route_geometry=from_shape(route_geom, srid=4326),
            distance_meters=route_data["distance"],
            estimated_duration_seconds=int(route_data["duration"]),
            requested_distance_meters=distance_meters,
            untraveled_distance_meters=untraveled_dist,
            untraveled_ratio=result["untraveled_ratio"],
        )
        self.db.add(suggestion)
        self.db.flush()

        # 7. Build & persist segment list ---------------------------------
        segments_info = self._persist_segments(
            suggestion, streets_for_engine, RouteSuggestionSegment,
            route_geom=route_geom,
        )

        return {
            "route": {
                "id": suggestion.id,
                "distance_meters": route_data["distance"],
                "estimated_duration_seconds": int(route_data["duration"]),
                "untraveled_distance_meters": untraveled_dist,
                "untraveled_ratio": result["untraveled_ratio"],
                "geometry": route_data["geometry"],
            },
            "segments": segments_info[:50],
        }

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _fallback_response(
        self,
        city_id: int,
        cov_map: dict[int, bool],
        engine_result: dict,
        NeighborhoodModel: type,
    ) -> dict:
        """Build the response when all streets are 100 % covered."""
        from app.models.street import StreetSegment

        neighborhoods = (
            self.db.query(NeighborhoodModel)
            .filter_by(city_id=city_id)
            .all()
        )
        suggestions: list[dict] = []
        for n in neighborhoods:
            n_streets = [
                s.id
                for s in self.db.query(StreetSegment.id)
                .filter_by(neighborhood_id=n.id)
                .all()
            ]
            if not n_streets:
                continue
            traveled = sum(1 for sid in n_streets if cov_map.get(sid, False))
            pct = traveled / len(n_streets) * 100
            if pct < 100:
                suggestions.append(
                    {"id": n.id, "name": n.name, "coverage_percentage": round(pct, 1)}
                )

        suggestions.sort(key=lambda x: x["coverage_percentage"])

        return {
            "route": None,
            "segments": [],
            "message": engine_result.get("message", "All streets covered."),
            "suggested_neighborhoods": suggestions[:5],
        }

    def _persist_segments(
        self,
        suggestion: Any,
        streets_for_engine: list[dict],
        SegmentModel: type,
        *,
        route_geom: LineString | None = None,
    ) -> list[dict]:
        """Create ``RouteSuggestionSegment`` rows and return segment info.

        Only includes untraveled streets that actually intersect the route
        geometry (buffered by ~30 m) so the map highlights are accurate.
        """
        # Buffer route by ~30 m (~0.0003 degrees) to catch nearby streets
        route_buffer = route_geom.buffer(0.0003) if route_geom else None
        untraveled_ids = {s["id"] for s in streets_for_engine if not s["is_traveled"]}
        segments_info: list[dict] = []

        for i, s in enumerate(streets_for_engine):
            if s["id"] not in untraveled_ids:
                continue
            # Only include streets that intersect the route
            if route_buffer and not s["geometry"].intersects(route_buffer):
                continue
            seg = SegmentModel(
                route_suggestion_id=suggestion.id,
                street_segment_id=s["id"],
                sequence_order=i + 1,
                is_untraveled=not s["is_traveled"],
            )
            self.db.add(seg)
            geom = s["geometry"]
            coords = [[c[0], c[1]] for c in geom.coords]
            segments_info.append(
                {
                    "street_name": s.get("name") or "Unnamed",
                    "is_untraveled": not s["is_traveled"],
                    "length_meters": s["length_meters"],
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coords,
                    },
                }
            )
        self.db.flush()
        return segments_info
