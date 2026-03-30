"""
Coverage planner service — multi-route plan generation (Features 4 & 5).

- CoveragePlannerService: generates a series of routes to cover all
  untraveled streets in a neighborhood, or across multiple neighborhoods
  to reach a city-level coverage goal.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import LineString, Point
from sqlalchemy.orm import Session

from app.models.coverage import UserStreetCoverage
from app.models.neighborhood import Neighborhood
from app.models.plan import CoverageGoal, CoveragePlan, CoveragePlanRoute
from app.models.route import RouteSuggestion, RouteSuggestionSegment
from app.models.street import StreetSegment
from app.services.coverage import compute_coverage_ratio, COVERAGE_THRESHOLD, _approx_buffer_degrees, DEFAULT_BUFFER_METERS
from app.services.routing import OSRMUnavailableError, RouteSuggestionEngine

_logger = logging.getLogger(__name__)


class CoveragePlannerService:
    """Generates multi-route coverage plans for neighborhoods and cities."""

    def __init__(self, db: Session, engine: RouteSuggestionEngine | None = None):
        self.db = db
        self.engine = engine or RouteSuggestionEngine()

    # ------------------------------------------------------------------ #
    # Feature 4: Neighborhood coverage plan
    # ------------------------------------------------------------------ #

    async def create_neighborhood_plan(
        self,
        *,
        user_id: int,
        city_id: int,
        neighborhood_id: int,
        preferred_distance_m: float,
        start_lng: float | None = None,
        start_lat: float | None = None,
    ) -> CoveragePlan:
        """Generate a multi-route plan covering a neighborhood's untraveled streets."""
        neighborhood = self.db.get(Neighborhood, neighborhood_id)
        if not neighborhood:
            raise ValueError(f"Neighborhood {neighborhood_id} not found")

        # Compute current coverage
        initial_pct = self._neighborhood_coverage_pct(user_id, neighborhood)

        plan = CoveragePlan(
            user_id=user_id,
            city_id=city_id,
            neighborhood_id=neighborhood_id,
            status="generating",
            preferred_route_distance_m=preferred_distance_m,
            initial_coverage_pct=initial_pct,
            target_coverage_pct=100.0,
        )
        self.db.add(plan)
        self.db.flush()

        try:
            await self._generate_plan_routes(
                plan=plan,
                user_id=user_id,
                neighborhood=neighborhood,
                preferred_distance_m=preferred_distance_m,
                start_lng=start_lng,
                start_lat=start_lat,
            )
            plan.status = "ready"
        except OSRMUnavailableError as exc:
            plan.status = "failed"
            plan.error_message = str(exc)
            _logger.error("Plan generation failed (OSRM): %s", exc)
        except Exception as exc:
            plan.status = "failed"
            plan.error_message = f"Generation error: {exc}"
            _logger.exception("Plan generation failed")

        self.db.flush()
        return plan

    async def _generate_plan_routes(
        self,
        *,
        plan: CoveragePlan,
        user_id: int,
        neighborhood: Neighborhood,
        preferred_distance_m: float,
        start_lng: float | None,
        start_lat: float | None,
    ) -> None:
        """Generate routes using a greedy nearest-untraveled-street walk.

        For each route:
        1. Start at home.
        2. Pick the nearest untraveled street, walk to its entry, traverse it.
        3. Repeat until estimated distance reaches the target.
        4. Route home.
        5. Make one OSRM call to get the real geometry.
        6. Credit streets using coverage-ratio matching.
        """
        streets, cov_set = self._query_untraveled_streets(user_id, neighborhood.id)

        if not streets:
            plan.total_routes = 0
            plan.total_distance_m = 0.0
            return

        if start_lng is None or start_lat is None:
            centroid = to_shape(neighborhood.boundary).centroid
            start_lng, start_lat = centroid.x, centroid.y

        start_point = (start_lng, start_lat)
        streets_by_id = {s["id"]: s for s in streets}

        total_distance = 0.0
        route_order = 0
        remaining_ids: set[int] = {s["id"] for s in streets if not s["is_traveled"]}
        max_routes = 200

        # Degrees-to-meters factor for distance estimation
        deg_to_m = 111_000 * math.cos(math.radians(start_lat))

        while remaining_ids and route_order < max_routes:
            # --- Build one route via greedy walk ---
            walk_streets = self._greedy_walk(
                remaining_ids=remaining_ids,
                streets_by_id=streets_by_id,
                start_point=start_point,
                target_distance_m=preferred_distance_m,
                deg_to_m=deg_to_m,
            )

            if not walk_streets:
                break

            # Build waypoint list: home → (entry, exit) per street → home
            waypoints: list[tuple[float, float]] = [start_point]
            for s in walk_streets:
                coords = list(s["geometry"].coords)
                entry, exit_ = self._orient_street(coords, waypoints[-1])
                waypoints.append(entry)
                waypoints.append(exit_)
            waypoints.append(start_point)

            # Get real route geometry from OSRM (handles chunking internally)
            route_result = await self._get_route_geometry(waypoints)
            if route_result is None:
                # Mark these streets as problematic and try others
                for s in walk_streets:
                    remaining_ids.discard(s["id"])
                continue

            route_geom, route_data = route_result

            # Credit streets using coverage-ratio matching (same as activity matching)
            buf_deg = _approx_buffer_degrees(DEFAULT_BUFFER_METERS, route_geom.centroid.y)
            route_buffer = route_geom.buffer(buf_deg)
            matched_ids: list[int] = []
            for sid in list(remaining_ids):
                s = streets_by_id[sid]
                ratio = compute_coverage_ratio(
                    s["geometry"], route_geom,
                    gps_buffer=route_buffer,
                )
                if ratio >= COVERAGE_THRESHOLD:
                    matched_ids.append(sid)

            if not matched_ids:
                # Route didn't actually cover anything — remove walk streets to avoid loop
                for s in walk_streets:
                    remaining_ids.discard(s["id"])
                continue

            # Persist the route
            untraveled_ratio = len(matched_ids) / max(len(walk_streets), 1)
            suggestion = RouteSuggestion(
                user_id=user_id,
                city_id=plan.city_id,
                neighborhood_id=neighborhood.id,
                start_point=from_shape(Point(start_point[0], start_point[1]), srid=4326),
                route_geometry=from_shape(route_geom, srid=4326),
                distance_meters=route_data["distance"],
                estimated_duration_seconds=int(route_data["duration"]),
                requested_distance_meters=preferred_distance_m,
                untraveled_distance_meters=route_data["distance"] * min(untraveled_ratio, 1.0),
                untraveled_ratio=min(untraveled_ratio, 1.0),
            )
            self.db.add(suggestion)
            self.db.flush()

            for order_idx, sid in enumerate(matched_ids, 1):
                seg = RouteSuggestionSegment(
                    route_suggestion_id=suggestion.id,
                    street_segment_id=sid,
                    sequence_order=order_idx,
                    is_untraveled=True,
                )
                self.db.add(seg)

            remaining_ids -= set(matched_ids)

            route_order += 1
            plan_route = CoveragePlanRoute(
                plan_id=plan.id,
                route_suggestion_id=suggestion.id,
                sequence_order=route_order,
                status="pending",
                streets_targeted=len(matched_ids),
            )
            self.db.add(plan_route)
            total_distance += route_data["distance"]

        plan.total_routes = route_order
        plan.total_distance_m = total_distance
        self.db.flush()

    # ------------------------------------------------------------------ #
    # Greedy walk helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _greedy_walk(
        *,
        remaining_ids: set[int],
        streets_by_id: dict[int, dict[str, Any]],
        start_point: tuple[float, float],
        target_distance_m: float,
        deg_to_m: float,
    ) -> list[dict[str, Any]]:
        """Pick streets greedily by nearest-neighbor until target distance.

        Uses Euclidean distance in degrees * deg_to_m for fast estimation.
        """
        if not remaining_ids:
            return []

        current = Point(start_point[0], start_point[1])
        estimated_distance = 0.0
        selected: list[dict[str, Any]] = []
        used_ids: set[int] = set()

        # Budget: target minus estimated return-home distance.
        # We'll use 80% of target for outbound, leaving room for the return.
        outbound_budget = target_distance_m * 0.8

        while estimated_distance < outbound_budget and len(used_ids) < len(remaining_ids):
            # Find nearest untraveled street
            best_id: int | None = None
            best_dist = float("inf")
            best_entry: Point | None = None

            for sid in remaining_ids:
                if sid in used_ids:
                    continue
                s = streets_by_id[sid]
                coords = list(s["geometry"].coords)
                # Check distance to both endpoints
                p0 = Point(coords[0][0], coords[0][1])
                p1 = Point(coords[-1][0], coords[-1][1])
                d0 = current.distance(p0) * deg_to_m
                d1 = current.distance(p1) * deg_to_m
                d = min(d0, d1)
                if d < best_dist:
                    best_dist = d
                    best_id = sid
                    best_entry = p0 if d0 <= d1 else p1

            if best_id is None:
                break

            s = streets_by_id[best_id]
            # Connector distance + street length
            leg_distance = best_dist + s["length_meters"]

            # Check if adding this street would overshoot too much
            if selected and estimated_distance + leg_distance > target_distance_m * 1.2:
                break

            selected.append(s)
            used_ids.add(best_id)
            estimated_distance += leg_distance

            # Move current to the far end of the street
            coords = list(s["geometry"].coords)
            if best_entry and best_entry.distance(Point(coords[0])) < best_entry.distance(Point(coords[-1])):
                current = Point(coords[-1][0], coords[-1][1])
            else:
                current = Point(coords[0][0], coords[0][1])

        return selected

    @staticmethod
    def _orient_street(
        coords: list[tuple[float, ...]],
        approaching_from: tuple[float, float],
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        """Return (entry, exit) endpoints oriented so entry is closer to approaching_from."""
        p0 = (coords[0][0], coords[0][1])
        p1 = (coords[-1][0], coords[-1][1])
        d0 = (p0[0] - approaching_from[0]) ** 2 + (p0[1] - approaching_from[1]) ** 2
        d1 = (p1[0] - approaching_from[0]) ** 2 + (p1[1] - approaching_from[1]) ** 2
        if d0 <= d1:
            return p0, p1
        return p1, p0

    async def _get_route_geometry(
        self,
        waypoints: list[tuple[float, float]],
    ) -> tuple[LineString, dict] | None:
        """Get route geometry from OSRM, chunking if > 100 waypoints.

        Splits into chunks of up to 95 waypoints (overlapping by 1 so
        chunks stitch together), calls OSRM for each, then concatenates
        the resulting geometries and sums distance/duration.
        """
        CHUNK_SIZE = 95

        if len(waypoints) <= 100:
            return await self._osrm_route_single(waypoints)

        # Split into chunks that share boundary points
        all_coords: list[tuple[float, float]] = []
        total_distance = 0.0
        total_duration = 0.0

        for chunk_start in range(0, len(waypoints), CHUNK_SIZE - 1):
            chunk = waypoints[chunk_start : chunk_start + CHUNK_SIZE]
            if len(chunk) < 2:
                break

            result = await self._osrm_route_single(chunk)
            if result is None:
                _logger.warning(
                    "OSRM chunk failed (waypoints %d–%d of %d)",
                    chunk_start, chunk_start + len(chunk), len(waypoints),
                )
                return None

            geom, data = result
            coords = list(geom.coords)
            # Skip first coord of subsequent chunks (duplicate of previous chunk's last)
            if all_coords:
                coords = coords[1:]
            all_coords.extend(coords)
            total_distance += data["distance"]
            total_duration += data["duration"]

        if len(all_coords) < 2:
            return None

        combined_geom = LineString(all_coords)
        combined_data = {"distance": total_distance, "duration": total_duration}
        return combined_geom, combined_data

    async def _osrm_route_single(
        self,
        waypoints: list[tuple[float, float]],
    ) -> tuple[LineString, dict] | None:
        """Single OSRM call with /route → /trip → halved fallback."""
        data = await self.engine.osrm.route_through(waypoints)
        if data is not None:
            geom = LineString([(c[0], c[1]) for c in data["geometry"]["coordinates"]])
            return geom, data

        data = await self.engine.osrm.trip(waypoints, roundtrip=False)
        if data is not None:
            geom = LineString([(c[0], c[1]) for c in data["geometry"]["coordinates"]])
            return geom, data

        if len(waypoints) > 10:
            half = len(waypoints) // 2
            data = await self.engine.osrm.route_through(waypoints[:half] + [waypoints[-1]])
            if data is not None:
                geom = LineString([(c[0], c[1]) for c in data["geometry"]["coordinates"]])
                return geom, data

        return None

    # ------------------------------------------------------------------ #
    # Feature 5: Optimal coverage planner (city-level)
    # ------------------------------------------------------------------ #

    async def create_coverage_goal(
        self,
        *,
        user_id: int,
        city_id: int,
        target_coverage_pct: float,
        preferred_route_distance_m: float,
    ) -> CoverageGoal:
        """Create a city-level coverage goal and generate plans for optimal neighborhoods."""
        current_pct = self._city_coverage_pct(user_id, city_id)

        if current_pct >= target_coverage_pct:
            goal = CoverageGoal(
                user_id=user_id,
                city_id=city_id,
                target_coverage_pct=target_coverage_pct,
                current_coverage_pct=current_pct,
                preferred_route_distance_m=preferred_route_distance_m,
                status="completed",
            )
            self.db.add(goal)
            self.db.flush()
            return goal

        goal = CoverageGoal(
            user_id=user_id,
            city_id=city_id,
            target_coverage_pct=target_coverage_pct,
            current_coverage_pct=current_pct,
            preferred_route_distance_m=preferred_route_distance_m,
            status="analyzing",
        )
        self.db.add(goal)
        self.db.flush()

        try:
            await self._generate_goal_plans(goal, user_id, city_id, target_coverage_pct, preferred_route_distance_m)
            goal.status = "ready"
        except Exception as exc:
            goal.status = "ready"  # Partial success is still useful
            _logger.exception("Goal generation partially failed: %s", exc)

        self.db.flush()
        return goal

    async def _generate_goal_plans(
        self,
        goal: CoverageGoal,
        user_id: int,
        city_id: int,
        target_pct: float,
        preferred_distance_m: float,
    ) -> None:
        """Select optimal neighborhoods and generate plans for each."""
        neighborhoods = (
            self.db.query(Neighborhood)
            .filter_by(city_id=city_id)
            .all()
        )

        # Rank neighborhoods by coverage opportunity
        ranked = []
        for n in neighborhoods:
            stats = self._neighborhood_stats(user_id, n)
            if stats["untraveled_count"] == 0:
                continue
            # Efficiency = density of untraveled streets
            area = to_shape(n.boundary).area if n.boundary else 1.0
            efficiency = (stats["untraveled_count"] * stats["avg_untraveled_length"]) / max(area, 1e-10)
            ranked.append({
                "neighborhood": n,
                "untraveled_count": stats["untraveled_count"],
                "untraveled_distance": stats["untraveled_distance"],
                "efficiency": efficiency,
            })

        ranked.sort(key=lambda x: x["efficiency"], reverse=True)

        # Compute how many streets we need to cover
        total_streets = sum(n.total_street_segments for n in neighborhoods)
        current_traveled = int(goal.current_coverage_pct / 100 * total_streets)
        target_traveled = int(target_pct / 100 * total_streets)
        streets_needed = target_traveled - current_traveled

        # Greedily select neighborhoods
        streets_accumulated = 0
        for entry in ranked:
            if streets_accumulated >= streets_needed:
                break

            n = entry["neighborhood"]
            plan = await self.create_neighborhood_plan(
                user_id=user_id,
                city_id=city_id,
                neighborhood_id=n.id,
                preferred_distance_m=preferred_distance_m,
            )
            plan.goal_id = goal.id
            streets_accumulated += entry["untraveled_count"]
            self.db.flush()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _query_untraveled_streets(
        self, user_id: int, neighborhood_id: int
    ) -> tuple[list[dict[str, Any]], set[int]]:
        """Query all streets in a neighborhood with coverage status."""
        db_streets = (
            self.db.query(StreetSegment)
            .filter_by(neighborhood_id=neighborhood_id)
            .all()
        )

        cov_rows = (
            self.db.query(UserStreetCoverage.street_segment_id)
            .join(StreetSegment, StreetSegment.id == UserStreetCoverage.street_segment_id)
            .filter(
                UserStreetCoverage.user_id == user_id,
                UserStreetCoverage.is_traveled == True,
                StreetSegment.neighborhood_id == neighborhood_id,
            )
            .all()
        )
        cov_set = {r[0] for r in cov_rows}

        streets = []
        for s in db_streets:
            try:
                geom = to_shape(s.geometry)
            except Exception:
                continue
            streets.append({
                "id": s.id,
                "geometry": geom,
                "length_meters": s.length_meters,
                "is_traveled": s.id in cov_set,
                "name": s.name,
                "highway_type": s.highway_type,
            })

        return streets, cov_set

    def _neighborhood_coverage_pct(self, user_id: int, neighborhood: Neighborhood) -> float:
        """Compute current coverage percentage for a neighborhood."""
        total = neighborhood.total_street_segments
        if total == 0:
            return 100.0

        traveled = (
            self.db.query(UserStreetCoverage)
            .join(StreetSegment, StreetSegment.id == UserStreetCoverage.street_segment_id)
            .filter(
                UserStreetCoverage.user_id == user_id,
                UserStreetCoverage.is_traveled == True,
                StreetSegment.neighborhood_id == neighborhood.id,
            )
            .count()
        )
        return round(traveled / total * 100, 1)

    def _city_coverage_pct(self, user_id: int, city_id: int) -> float:
        """Compute current city-wide coverage percentage."""
        from app.models.city import City
        city = self.db.get(City, city_id)
        if not city or city.total_street_segments == 0:
            return 100.0

        traveled = (
            self.db.query(UserStreetCoverage)
            .join(StreetSegment, StreetSegment.id == UserStreetCoverage.street_segment_id)
            .filter(
                UserStreetCoverage.user_id == user_id,
                UserStreetCoverage.is_traveled == True,
                StreetSegment.city_id == city_id,
            )
            .count()
        )
        return round(traveled / city.total_street_segments * 100, 1)

    def _neighborhood_stats(self, user_id: int, neighborhood: Neighborhood) -> dict:
        """Get untraveled street stats for a neighborhood."""
        streets, cov_set = self._query_untraveled_streets(user_id, neighborhood.id)
        untraveled = [s for s in streets if not s["is_traveled"]]
        untraveled_dist = sum(s["length_meters"] for s in untraveled)
        avg_len = untraveled_dist / len(untraveled) if untraveled else 0.0
        return {
            "untraveled_count": len(untraveled),
            "untraveled_distance": untraveled_dist,
            "avg_untraveled_length": avg_len,
        }
