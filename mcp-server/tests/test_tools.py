"""Tests for MCP tool functions with mocked PacmanClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from pacman_mcp import server as server_mod
from pacman_mcp.server import (
    _resolve_city,
    get_coverage_summary,
    get_neighborhood_priority,
    get_progress_summary,
    get_untraveled_streets,
    lookup_location,
    user_profile,
)
from tests.conftest import (
    CITIES_RESPONSE,
    CITY_COVERAGE_RESPONSE,
    NEIGHBORHOODS_RESPONSE,
    OVERALL_STATS_RESPONSE,
    PROGRESS_RESPONSE,
    STREETS_GEOJSON_RESPONSE,
)


@pytest.fixture(autouse=True)
def _patch_get_client(mock_client):
    """Patch _get_client to return our mock for all tool tests."""
    async def fake_get_client():
        return mock_client
    with patch.object(server_mod, "_get_client", fake_get_client):
        yield


# ---------------------------------------------------------------------------
# _resolve_city
# ---------------------------------------------------------------------------


class TestResolveCity:
    async def test_exact_match(self, mock_client):
        city, err = await _resolve_city(mock_client, "Seattle")
        assert err is None
        assert city["name"] == "Seattle"

    async def test_case_insensitive(self, mock_client):
        city, err = await _resolve_city(mock_client, "seattle")
        assert err is None
        assert city["name"] == "Seattle"

    async def test_substring_match(self, mock_client):
        city, err = await _resolve_city(mock_client, "port")
        assert err is None
        assert city["name"] == "Portland"

    async def test_no_match(self, mock_client):
        city, err = await _resolve_city(mock_client, "narnia")
        assert city is None
        assert "No city found" in err

    async def test_multiple_matches(self, mock_client):
        # Both "Seattle" and "Portland" contain "l"
        mock_client.list_cities = AsyncMock(return_value={
            "cities": [
                {"id": 1, "name": "Salt Lake City"},
                {"id": 2, "name": "Salt Lake South"},
            ]
        })
        city, err = await _resolve_city(mock_client, "salt lake")
        assert city is None
        assert "Multiple cities" in err

    async def test_backend_error(self, mock_client):
        mock_client.list_cities = AsyncMock(side_effect=ConnectionError("offline"))
        city, err = await _resolve_city(mock_client, "Seattle")
        assert city is None
        assert "Error" in err


# ---------------------------------------------------------------------------
# lookup_location
# ---------------------------------------------------------------------------


class TestLookupLocation:
    async def test_city_match_includes_neighborhoods(self):
        result = await lookup_location("seattle")
        assert "Seattle" in result
        assert "Fremont" in result
        assert "Capitol Hill" in result

    async def test_neighborhood_search_when_no_city_match(self):
        result = await lookup_location("fremont")
        assert "Fremont" in result
        assert "Seattle" in result

    async def test_no_match(self):
        result = await lookup_location("atlantis")
        assert "No cities or neighborhoods found" in result

    async def test_case_insensitive(self):
        result = await lookup_location("CAPITOL HILL")
        assert "Capitol Hill" in result


# ---------------------------------------------------------------------------
# get_coverage_summary
# ---------------------------------------------------------------------------


class TestGetCoverageSummary:
    async def test_no_args(self):
        result = await get_coverage_summary()
        assert "Please provide" in result

    async def test_city_level(self):
        result = await get_coverage_summary(city="Seattle")
        assert "Seattle" in result
        assert "42.5%" in result
        assert "Neighborhoods" in result

    async def test_neighborhood_by_name(self):
        result = await get_coverage_summary(neighborhood="Fremont")
        assert "Fremont" in result
        assert "73.2%" in result

    async def test_city_and_neighborhood(self):
        result = await get_coverage_summary(city="Seattle", neighborhood="Fremont")
        assert "Fremont" in result

    async def test_no_city_match(self):
        result = await get_coverage_summary(city="Narnia")
        assert "No city found" in result

    async def test_no_neighborhood_match(self):
        result = await get_coverage_summary(city="Seattle", neighborhood="Fakeville")
        assert "No neighborhood matching" in result


# ---------------------------------------------------------------------------
# get_untraveled_streets
# ---------------------------------------------------------------------------


class TestGetUntraveledStreets:
    async def test_requires_location(self):
        result = await get_untraveled_streets()
        assert "specify" in result.lower()

    async def test_requires_neighborhood(self):
        result = await get_untraveled_streets(city="Seattle")
        assert "specify a neighborhood" in result.lower()

    async def test_neighborhood_results(self):
        result = await get_untraveled_streets(neighborhood="Fremont")
        assert "Untraveled streets in Fremont" in result
        assert "N 36th St" in result
        assert "Fremont Ave N" in result
        assert "(unnamed)" in result

    async def test_groups_segments(self):
        result = await get_untraveled_streets(neighborhood="Fremont")
        # N 36th St has 2 segments
        assert "2 segments" in result

    async def test_sorted_by_length(self):
        result = await get_untraveled_streets(neighborhood="Fremont")
        # Fremont Ave N (890m) should come before N 36th St (630m total)
        fremont_pos = result.index("Fremont Ave N")
        n36_pos = result.index("N 36th St")
        assert fremont_pos < n36_pos

    async def test_all_traveled(self, mock_client):
        mock_client.city_streets = AsyncMock(return_value={"type": "FeatureCollection", "features": []})
        result = await get_untraveled_streets(neighborhood="Fremont")
        assert "covered it all" in result

    async def test_limit(self):
        result = await get_untraveled_streets(neighborhood="Fremont", limit=1)
        # Should show only 1 street + "and N more"
        assert "... and" in result

    async def test_no_neighborhood_match(self):
        result = await get_untraveled_streets(neighborhood="Fake")
        assert "No neighborhood found" in result


# ---------------------------------------------------------------------------
# get_progress_summary
# ---------------------------------------------------------------------------


class TestGetProgressSummary:
    async def test_basic_output(self):
        result = await get_progress_summary("Seattle")
        assert "Seattle" in result
        assert "42.5%" in result

    async def test_milestones_reached(self):
        result = await get_progress_summary("Seattle")
        assert "Milestones Reached" in result
        assert "25%" in result
        assert "Fremont" in result
        assert "2025-06-15" in result

    async def test_upcoming_milestones(self):
        result = await get_progress_summary("Seattle")
        assert "Upcoming Milestones" in result
        assert "50%" in result

    async def test_timeline(self):
        result = await get_progress_summary("Seattle")
        assert "Recent Timeline" in result
        assert "2025-03-01" in result

    async def test_growth_rate(self):
        result = await get_progress_summary("Seattle")
        assert "Growth:" in result
        assert "+32.5%" in result
        assert "+16,250 streets" in result

    async def test_no_city_match(self):
        result = await get_progress_summary("Narnia")
        assert "No city found" in result


# ---------------------------------------------------------------------------
# get_neighborhood_priority
# ---------------------------------------------------------------------------


class TestGetNeighborhoodPriority:
    async def test_basic_ranking(self):
        result = await get_neighborhood_priority("Seattle")
        assert "Neighborhood Priority" in result
        assert "Seattle" in result

    async def test_sorted_by_streets_needed(self):
        result = await get_neighborhood_priority("Seattle")
        lines = result.split("\n")
        ranked_lines = [l for l in lines if "→" in l]
        assert len(ranked_lines) >= 3
        # Ballard (9 streets to 100%) and Fremont (9 streets to 75%) tie
        # Both should appear in the top 2
        top_two = ranked_lines[0] + ranked_lines[1]
        assert "Ballard" in top_two
        assert "Fremont" in top_two

    async def test_milestone_info(self):
        result = await get_neighborhood_priority("Seattle")
        assert "→ 100%" in result  # Ballard near 100%
        assert "→ 75%" in result   # Fremont near 75%
        assert "→ 25%" in result   # University District near 25%

    async def test_all_complete(self, mock_client):
        mock_client.list_cities = AsyncMock(return_value={
            "cities": [{"id": 99, "name": "Done", "state": "XX", "total_street_segments": 100, "total_neighborhoods": 1}]
        })
        mock_client.city_coverage = AsyncMock(return_value={
            "city": {"id": 99, "name": "Done"},
            "neighborhoods": [
                {"name": "A", "coverage_percentage": 100, "streets_traveled": 100, "streets_total": 100},
            ],
        })
        result = await get_neighborhood_priority("Done")
        assert "100% complete" in result

    async def test_limit(self):
        result = await get_neighborhood_priority("Seattle", limit=2)
        lines = [l for l in result.split("\n") if "→" in l]
        assert len(lines) == 2

    async def test_no_city_match(self):
        result = await get_neighborhood_priority("Narnia")
        assert "No city found" in result


# ---------------------------------------------------------------------------
# user_profile resource
# ---------------------------------------------------------------------------


class TestUserProfile:
    async def test_basic_output(self):
        result = await user_profile()
        assert "Pacman Tracker Profile" in result
        assert "150" in result  # total_activities
        assert "1200.0 km" in result
        assert "21250" in result  # unique streets
        assert "Seattle" in result
        assert "42.5%" in result

    async def test_auth_error(self, mock_client):
        mock_client.overall_stats = AsyncMock(side_effect=PermissionError("expired"))
        result = await user_profile()
        assert "Not authenticated" in result

    async def test_connection_error(self, mock_client):
        mock_client.overall_stats = AsyncMock(side_effect=ConnectionError("offline"))
        result = await user_profile()
        assert "Error" in result
