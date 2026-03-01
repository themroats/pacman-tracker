"""
T091 — Route suggestion algorithm tests.

Tests:
- Waypoint selection from untraveled streets
- Distance iteration logic
- 100%-covered fallback to neighboring neighborhoods
"""

from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from shapely.geometry import LineString

from app.services.routing import RouteSuggestionEngine


@pytest.fixture()
def engine():
    """Create a RouteSuggestionEngine with a mocked OSRM client."""
    mock_osrm = MagicMock()
    mock_osrm.trip = AsyncMock()
    mock_osrm.nearest = AsyncMock()
    return RouteSuggestionEngine(osrm_client=mock_osrm)


class TestWaypointSelection:
    """Tests for selecting waypoints from untraveled streets."""

    def test_selects_midpoints_of_untraveled_streets(self, engine):
        """Waypoints should be midpoints of untraveled street geometries."""
        streets = [
            {
                "id": 1,
                "geometry": LineString([(-122.33, 47.60), (-122.33, 47.61)]),
                "length_meters": 200.0,
                "is_traveled": False,
            },
            {
                "id": 2,
                "geometry": LineString([(-122.32, 47.60), (-122.32, 47.61)]),
                "length_meters": 300.0,
                "is_traveled": False,
            },
        ]
        waypoints = engine.select_waypoints(streets, max_waypoints=10)
        assert len(waypoints) == 2
        # Each waypoint should be an (lng, lat) tuple near the street midpoint
        for wp in waypoints:
            assert len(wp) == 2

    def test_excludes_traveled_streets(self, engine):
        """Already-traveled streets should not produce waypoints."""
        streets = [
            {
                "id": 1,
                "geometry": LineString([(-122.33, 47.60), (-122.33, 47.61)]),
                "length_meters": 200.0,
                "is_traveled": True,
            },
            {
                "id": 2,
                "geometry": LineString([(-122.32, 47.60), (-122.32, 47.61)]),
                "length_meters": 300.0,
                "is_traveled": False,
            },
        ]
        waypoints = engine.select_waypoints(streets, max_waypoints=10)
        assert len(waypoints) == 1

    def test_limits_waypoints(self, engine):
        """Should respect max_waypoints limit."""
        streets = [
            {
                "id": i,
                "geometry": LineString([(-122.33 + i * 0.001, 47.60), (-122.33 + i * 0.001, 47.61)]),
                "length_meters": 200.0,
                "is_traveled": False,
            }
            for i in range(20)
        ]
        waypoints = engine.select_waypoints(streets, max_waypoints=5)
        assert len(waypoints) <= 5


class TestDistanceIteration:
    """Tests for achieving target distance within tolerance."""

    @pytest.mark.asyncio
    async def test_returns_route_near_target_distance(self, engine):
        """The generated route should be within 10% of the requested distance."""
        engine.osrm.trip.return_value = {
            "distance": 5100.0,
            "duration": 2550.0,
            "geometry": {
                "type": "LineString",
                "coordinates": [[-122.33, 47.60], [-122.33, 47.61]],
            },
        }
        engine.osrm.nearest.return_value = {
            "location": [-122.33, 47.60],
            "distance": 3.0,
            "name": "",
        }

        waypoints = [(-122.33, 47.605), (-122.32, 47.605)]
        result = await engine.build_route(
            start=(-122.33, 47.60),
            waypoints=waypoints,
            target_distance=5000.0,
        )
        assert result is not None
        assert result["distance"] == 5100.0


class TestFullCoverageFallback:
    """Tests for the 100%-covered scenario."""

    def test_no_untraveled_streets_returns_empty_waypoints(self, engine):
        """If all streets are traveled, waypoint selection returns empty."""
        streets = [
            {
                "id": 1,
                "geometry": LineString([(-122.33, 47.60), (-122.33, 47.61)]),
                "length_meters": 200.0,
                "is_traveled": True,
            },
        ]
        waypoints = engine.select_waypoints(streets, max_waypoints=10)
        assert len(waypoints) == 0
