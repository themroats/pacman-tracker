"""
Unit tests for CoveragePlannerService.

Tests:
- Greedy walk: nearest-neighbor street selection with distance budget
- Orient street: endpoint selection based on approach direction
- OSRM route single: fallback chain (route_through → trip → halved)
- Get route geometry: chunking for large waypoint lists
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shapely.geometry import LineString

from app.services.planner import CoveragePlannerService
from app.services.routing import RouteSuggestionEngine


def _make_street(id: int, lng: float, lat: float, *, traveled: bool = False, length: float = 200.0):
    """Build a minimal street dict for the planner helpers."""
    return {
        "id": id,
        "geometry": LineString([(lng, lat), (lng + 0.001, lat + 0.001)]),
        "length_meters": length,
        "is_traveled": traveled,
        "name": f"Street {id}",
        "highway_type": "residential",
    }


class TestGreedyWalk:
    """Tests for CoveragePlannerService._greedy_walk."""

    def test_picks_nearest_street_first(self):
        s1 = _make_street(1, -122.33, 47.60, length=100)
        s2 = _make_street(2, -122.40, 47.70, length=100)
        s3 = _make_street(3, -122.331, 47.601, length=100)
        streets_by_id = {1: s1, 2: s2, 3: s3}
        remaining = {1, 2, 3}

        selected = CoveragePlannerService._greedy_walk(
            remaining_ids=remaining,
            streets_by_id=streets_by_id,
            start_point=(-122.329, 47.599),
            target_distance_m=5000,
            deg_to_m=85_000,
        )
        assert len(selected) >= 2
        assert selected[0]["id"] == 1  # closest to start

    def test_respects_distance_budget(self):
        # Many streets, small budget — should stop early
        streets_by_id = {}
        remaining = set()
        for i in range(50):
            s = _make_street(i + 1, -122.33 + i * 0.001, 47.60, length=200)
            streets_by_id[i + 1] = s
            remaining.add(i + 1)

        selected = CoveragePlannerService._greedy_walk(
            remaining_ids=remaining,
            streets_by_id=streets_by_id,
            start_point=(-122.33, 47.60),
            target_distance_m=1000,
            deg_to_m=85_000,
        )
        # Should pick some streets, not all 50
        assert 1 < len(selected) < 50

    def test_empty_remaining_returns_empty(self):
        selected = CoveragePlannerService._greedy_walk(
            remaining_ids=set(),
            streets_by_id={},
            start_point=(-122.33, 47.60),
            target_distance_m=5000,
            deg_to_m=85_000,
        )
        assert selected == []


class TestOrientStreet:
    """Tests for CoveragePlannerService._orient_street."""

    def test_entry_closer_to_approaching(self):
        coords = [(-122.33, 47.60), (-122.34, 47.61)]
        entry, exit_ = CoveragePlannerService._orient_street(coords, (-122.329, 47.599))
        assert entry == (-122.33, 47.60)  # closer
        assert exit_ == (-122.34, 47.61)

    def test_reversed_when_far_end_closer(self):
        coords = [(-122.33, 47.60), (-122.34, 47.61)]
        entry, exit_ = CoveragePlannerService._orient_street(coords, (-122.341, 47.611))
        assert entry == (-122.34, 47.61)  # now this end is closer
        assert exit_ == (-122.33, 47.60)


# ------------------------------------------------------------------ #
# Helpers for OSRM mock responses
# ------------------------------------------------------------------ #

def _osrm_route_response(distance: float, coords: list[list[float]]) -> dict:
    """Build a minimal OSRM route response dict."""
    return {
        "distance": distance,
        "duration": distance / 2,
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def _make_planner_with_mock_osrm():
    """Create a CoveragePlannerService with a mocked OSRM client."""
    engine = RouteSuggestionEngine(osrm_client=MagicMock())
    planner = CoveragePlannerService(db=None, engine=engine)
    return planner, engine.osrm


class TestOsrmRouteSingle:
    """Tests for CoveragePlannerService._osrm_route_single — fallback chain."""

    @pytest.mark.asyncio
    async def test_returns_route_through_when_available(self):
        planner, osrm = _make_planner_with_mock_osrm()
        osrm.route_through = AsyncMock(return_value=_osrm_route_response(
            5000.0, [[-122.33, 47.60], [-122.34, 47.61]],
        ))

        result = await planner._osrm_route_single([(-122.33, 47.60), (-122.34, 47.61)])
        assert result is not None
        geom, data = result
        assert data["distance"] == 5000.0
        assert len(list(geom.coords)) == 2
        osrm.trip.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_trip_when_route_fails(self):
        planner, osrm = _make_planner_with_mock_osrm()
        osrm.route_through = AsyncMock(return_value=None)
        osrm.trip = AsyncMock(return_value=_osrm_route_response(
            4000.0, [[-122.33, 47.60], [-122.34, 47.61]],
        ))

        result = await planner._osrm_route_single([(-122.33, 47.60), (-122.34, 47.61)])
        assert result is not None
        _, data = result
        assert data["distance"] == 4000.0
        osrm.trip.assert_called_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_halved_route(self):
        planner, osrm = _make_planner_with_mock_osrm()
        # Both route_through and trip fail first time
        osrm.route_through = AsyncMock(side_effect=[
            None,  # Full waypoints fail
            _osrm_route_response(3000.0, [[-122.33, 47.60], [-122.34, 47.61]]),  # Halved succeeds
        ])
        osrm.trip = AsyncMock(return_value=None)

        # Need > 10 waypoints for halved fallback to trigger
        waypoints = [(-122.33 + i * 0.001, 47.60) for i in range(20)]
        result = await planner._osrm_route_single(waypoints)
        assert result is not None
        _, data = result
        assert data["distance"] == 3000.0
        assert osrm.route_through.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_when_all_fail(self):
        planner, osrm = _make_planner_with_mock_osrm()
        osrm.route_through = AsyncMock(return_value=None)
        osrm.trip = AsyncMock(return_value=None)

        waypoints = [(-122.33 + i * 0.001, 47.60) for i in range(20)]
        result = await planner._osrm_route_single(waypoints)
        assert result is None

    @pytest.mark.asyncio
    async def test_skips_halved_fallback_for_few_waypoints(self):
        planner, osrm = _make_planner_with_mock_osrm()
        osrm.route_through = AsyncMock(return_value=None)
        osrm.trip = AsyncMock(return_value=None)

        # Only 5 waypoints — should NOT try halved fallback
        waypoints = [(-122.33 + i * 0.001, 47.60) for i in range(5)]
        result = await planner._osrm_route_single(waypoints)
        assert result is None
        # route_through called once (not twice for halved)
        assert osrm.route_through.call_count == 1


class TestGetRouteGeometry:
    """Tests for CoveragePlannerService._get_route_geometry — chunking."""

    @pytest.mark.asyncio
    async def test_small_list_delegates_to_single(self):
        planner, _ = _make_planner_with_mock_osrm()
        mock_geom = LineString([(-122.33, 47.60), (-122.34, 47.61)])
        mock_data = {"distance": 5000.0, "duration": 2500.0}

        with patch.object(planner, "_osrm_route_single", new_callable=AsyncMock, return_value=(mock_geom, mock_data)):
            result = await planner._get_route_geometry([(-122.33, 47.60), (-122.34, 47.61)])
            assert result is not None
            geom, data = result
            assert data["distance"] == 5000.0
            planner._osrm_route_single.assert_called_once()

    @pytest.mark.asyncio
    async def test_chunks_large_waypoint_list(self):
        planner, _ = _make_planner_with_mock_osrm()

        # 150 waypoints → should be split into 2 chunks
        waypoints = [(-122.33 + i * 0.0001, 47.60) for i in range(150)]

        chunk_geom = LineString([(-122.33, 47.60), (-122.335, 47.605), (-122.34, 47.61)])
        chunk_data = {"distance": 3000.0, "duration": 1500.0}

        with patch.object(planner, "_osrm_route_single", new_callable=AsyncMock, return_value=(chunk_geom, chunk_data)):
            result = await planner._get_route_geometry(waypoints)
            assert result is not None
            geom, data = result
            # 2 chunks → distances summed
            assert data["distance"] == 6000.0
            assert data["duration"] == 3000.0
            assert planner._osrm_route_single.call_count == 2

    @pytest.mark.asyncio
    async def test_chunk_failure_returns_none(self):
        planner, _ = _make_planner_with_mock_osrm()

        waypoints = [(-122.33 + i * 0.0001, 47.60) for i in range(150)]

        chunk_geom = LineString([(-122.33, 47.60), (-122.34, 47.61)])
        chunk_data = {"distance": 3000.0, "duration": 1500.0}

        # First chunk succeeds, second fails
        with patch.object(planner, "_osrm_route_single", new_callable=AsyncMock, side_effect=[
            (chunk_geom, chunk_data),
            None,
        ]):
            result = await planner._get_route_geometry(waypoints)
            assert result is None

    @pytest.mark.asyncio
    async def test_stitches_chunk_geometries(self):
        planner, _ = _make_planner_with_mock_osrm()

        waypoints = [(-122.33 + i * 0.0001, 47.60) for i in range(150)]

        geom1 = LineString([(-122.33, 47.60), (-122.335, 47.605)])
        data1 = {"distance": 2000.0, "duration": 1000.0}
        geom2 = LineString([(-122.335, 47.605), (-122.34, 47.61)])
        data2 = {"distance": 2000.0, "duration": 1000.0}

        with patch.object(planner, "_osrm_route_single", new_callable=AsyncMock, side_effect=[
            (geom1, data1),
            (geom2, data2),
        ]):
            result = await planner._get_route_geometry(waypoints)
            assert result is not None
            geom, data = result
            coords = list(geom.coords)
            # 2 coords from geom1 + 1 new from geom2 (first deduped) = 3
            assert len(coords) == 3
            assert coords[0] == (-122.33, 47.60)
            assert coords[-1] == (-122.34, 47.61)
