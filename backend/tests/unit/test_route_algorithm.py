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
        """Waypoints should be endpoints of untraveled street geometries."""
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
        # Each street contributes 2 endpoints
        assert len(waypoints) == 4
        # Each waypoint should be an (lng, lat) tuple
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
        # 1 untraveled street × 2 endpoints
        assert len(waypoints) == 2

    def test_limits_waypoints(self, engine):
        """Should respect max_waypoints limit (each street = 2 endpoints)."""
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
        # max_waypoints=5 → 2 streets selected → 4 endpoints
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


class TestPersistSegments:
    """Tests for _persist_segments route-intersection filtering and geometry."""

    @pytest.fixture()
    def planner(self):
        """Create a RoutePlannerService with a mocked DB session."""
        from app.services.routing import RoutePlannerService

        mock_db = MagicMock()
        return RoutePlannerService(db=mock_db)

    def _make_segment_model(self):
        """Return a mock SegmentModel class that records instantiations."""
        return MagicMock

    def test_only_includes_segments_intersecting_route(self, planner):
        """Streets far from the route should be excluded from results."""
        # Route goes along longitude -122.33
        route_geom = LineString([(-122.33, 47.60), (-122.33, 47.62)])

        streets = [
            {
                "id": 1,
                "geometry": LineString([(-122.3301, 47.605), (-122.3299, 47.605)]),
                "length_meters": 50.0,
                "is_traveled": False,
                "name": "Near Street",
            },
            {
                "id": 2,
                "geometry": LineString([(-122.35, 47.605), (-122.35, 47.606)]),
                "length_meters": 100.0,
                "is_traveled": False,
                "name": "Far Street",
            },
        ]

        suggestion = MagicMock(id=1)
        result = planner._persist_segments(
            suggestion, streets, self._make_segment_model(),
            route_geom=route_geom,
        )

        names = [s["street_name"] for s in result]
        assert "Near Street" in names
        assert "Far Street" not in names

    def test_excludes_traveled_streets(self, planner):
        """Traveled streets should never appear in segments."""
        route_geom = LineString([(-122.33, 47.60), (-122.33, 47.62)])

        streets = [
            {
                "id": 1,
                "geometry": LineString([(-122.3301, 47.605), (-122.3299, 47.605)]),
                "length_meters": 50.0,
                "is_traveled": True,
                "name": "Traveled Street",
            },
        ]

        suggestion = MagicMock(id=1)
        result = planner._persist_segments(
            suggestion, streets, self._make_segment_model(),
            route_geom=route_geom,
        )

        assert len(result) == 0

    def test_segments_include_geometry(self, planner):
        """Each returned segment should include a GeoJSON LineString geometry."""
        route_geom = LineString([(-122.33, 47.60), (-122.33, 47.62)])

        streets = [
            {
                "id": 1,
                "geometry": LineString([(-122.3301, 47.605), (-122.3299, 47.605)]),
                "length_meters": 50.0,
                "is_traveled": False,
                "name": "Test Street",
            },
        ]

        suggestion = MagicMock(id=1)
        result = planner._persist_segments(
            suggestion, streets, self._make_segment_model(),
            route_geom=route_geom,
        )

        assert len(result) == 1
        seg = result[0]
        assert seg["geometry"]["type"] == "LineString"
        assert len(seg["geometry"]["coordinates"]) == 2
        assert seg["is_untraveled"] is True
        assert seg["street_name"] == "Test Street"

    def test_no_route_geom_includes_all_untraveled(self, planner):
        """Without a route geometry, all untraveled streets are included."""
        streets = [
            {
                "id": 1,
                "geometry": LineString([(-122.33, 47.605), (-122.33, 47.606)]),
                "length_meters": 50.0,
                "is_traveled": False,
                "name": "Street A",
            },
            {
                "id": 2,
                "geometry": LineString([(-122.35, 47.605), (-122.35, 47.606)]),
                "length_meters": 100.0,
                "is_traveled": False,
                "name": "Street B",
            },
        ]

        suggestion = MagicMock(id=1)
        result = planner._persist_segments(
            suggestion, streets, self._make_segment_model(),
        )

        assert len(result) == 2


# ---------------------------------------------------------------------------
# Variation & Preference Tests (FR-001, FR-002)
# ---------------------------------------------------------------------------


class TestVariationParam:
    """Tests for the variation parameter controlling randomness."""

    def _make_streets(self, n=10):
        return [
            {
                "id": i,
                "geometry": LineString([(-122.33 + i * 0.001, 47.60), (-122.33 + i * 0.001, 47.61)]),
                "length_meters": (i + 1) * 100.0,
                "is_traveled": False,
                "highway_type": "residential",
            }
            for i in range(n)
        ]

    def test_variation_zero_is_deterministic(self, engine):
        """variation=0 should always return the same waypoints (longest first)."""
        streets = self._make_streets(10)
        wp1 = engine.select_waypoints(streets, max_waypoints=3, variation=0.0)
        wp2 = engine.select_waypoints(streets, max_waypoints=3, variation=0.0)
        assert wp1 == wp2
        # max_waypoints=3 → 1 street selected → 2 endpoints
        assert len(wp1) == 2

    def test_variation_one_uses_all_streets(self, engine):
        """variation=1.0 should still return valid waypoints."""
        streets = self._make_streets(10)
        wp = engine.select_waypoints(streets, max_waypoints=5, variation=1.0)
        # max_waypoints=5 → 2 streets → 4 endpoints; may get fewer from dedup
        assert 1 <= len(wp) <= 5
        for lng, lat in wp:
            assert isinstance(lng, float)
            assert isinstance(lat, float)

    def test_variation_respects_max_waypoints(self, engine):
        """Even with high variation, must respect the limit."""
        streets = self._make_streets(20)
        wp = engine.select_waypoints(streets, max_waypoints=3, variation=0.8)
        assert len(wp) <= 3

    def test_default_variation_produces_waypoints(self, engine):
        """Default variation (0.5) should work without explicit argument."""
        streets = self._make_streets(10)
        wp = engine.select_waypoints(streets, max_waypoints=5)
        assert 1 <= len(wp) <= 5


class TestPreferences:
    """Tests for street type preference weights."""

    def _make_categorized_streets(self):
        return [
            {
                "id": 1,
                "geometry": LineString([(-122.33, 47.60), (-122.33, 47.61)]),
                "length_meters": 200.0,
                "is_traveled": False,
                "highway_type": "residential",
            },
            {
                "id": 2,
                "geometry": LineString([(-122.34, 47.60), (-122.34, 47.61)]),
                "length_meters": 200.0,
                "is_traveled": False,
                "highway_type": "primary",  # main_roads
            },
            {
                "id": 3,
                "geometry": LineString([(-122.35, 47.60), (-122.35, 47.61)]),
                "length_meters": 200.0,
                "is_traveled": False,
                "highway_type": "footway",  # trails
            },
            {
                "id": 4,
                "geometry": LineString([(-122.36, 47.60), (-122.36, 47.61)]),
                "length_meters": 200.0,
                "is_traveled": False,
                "highway_type": "service",  # other
            },
        ]

    def test_zero_pref_excludes_category(self, engine):
        """Streets in a category with weight 0 should be excluded."""
        streets = self._make_categorized_streets()
        prefs = {"residential": 1.0, "main_roads": 0.0, "trails": 1.0, "other": 1.0}
        wp = engine.select_waypoints(streets, max_waypoints=10, variation=0.0, preferences=prefs)
        # 3 streets × 2 endpoints (not main_roads)
        assert len(wp) == 6

    def test_all_zero_prefs_falls_back(self, engine):
        """If all prefs are 0, should fall back to all untraveled."""
        streets = self._make_categorized_streets()
        prefs = {"residential": 0.0, "main_roads": 0.0, "trails": 0.0, "other": 0.0}
        wp = engine.select_waypoints(streets, max_waypoints=10, variation=0.0, preferences=prefs)
        # Falls back to all 4 untraveled × 2 endpoints
        assert len(wp) == 8

    def test_high_weight_ranks_first_at_variation_zero(self, engine):
        """With variation=0, heavily-weighted categories come first."""
        streets = self._make_categorized_streets()
        prefs = {"residential": 0.1, "main_roads": 0.1, "trails": 10.0, "other": 0.1}
        # max_waypoints=1 → 1 street → 2 endpoints (but capped at 1 street via max(1//2,1)=1)
        wp = engine.select_waypoints(streets, max_waypoints=2, variation=0.0, preferences=prefs)
        assert len(wp) == 2
        # The trail (footway) street should be selected — check first endpoint
        trail_coords = list(streets[2]["geometry"].coords)
        assert abs(wp[0][0] - trail_coords[0][0]) < 0.001
        assert abs(wp[0][1] - trail_coords[0][1]) < 0.001

    def test_unknown_highway_type_uses_other_category(self, engine):
        """Streets with unknown highway types should fall into 'other'."""
        streets = [
            {
                "id": 1,
                "geometry": LineString([(-122.33, 47.60), (-122.33, 47.61)]),
                "length_meters": 200.0,
                "is_traveled": False,
                "highway_type": "motorway_link",  # not in HIGHWAY_CATEGORIES
            },
        ]
        prefs = {"residential": 0.0, "main_roads": 0.0, "trails": 0.0, "other": 1.0}
        wp = engine.select_waypoints(streets, max_waypoints=10, variation=0.0, preferences=prefs)
        # 1 street × 2 endpoints
        assert len(wp) == 2
