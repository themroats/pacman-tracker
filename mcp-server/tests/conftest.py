"""Shared test fixtures and mock data for MCP server tests."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from pacman_mcp.client import PacmanClient


# ---------------------------------------------------------------------------
# Sample API responses
# ---------------------------------------------------------------------------

CITIES_RESPONSE = {
    "cities": [
        {"id": 1, "name": "Seattle", "state": "WA", "total_street_segments": 50000, "total_neighborhoods": 80},
        {"id": 2, "name": "Portland", "state": "OR", "total_street_segments": 30000, "total_neighborhoods": 50},
    ],
    "bootstrap_status": "complete",
    "bootstrap_error": None,
}

NEIGHBORHOODS_RESPONSE = {
    "neighborhoods": [
        {"id": 10, "name": "Fremont", "total_street_segments": 500, "coverage_percentage": 73.2},
        {"id": 11, "name": "Capitol Hill", "total_street_segments": 800, "coverage_percentage": 45.0},
        {"id": 12, "name": "Ballard", "total_street_segments": 600, "coverage_percentage": 98.5},
        {"id": 13, "name": "University District", "total_street_segments": 400, "coverage_percentage": 12.0},
    ],
}

CITY_COVERAGE_RESPONSE = {
    "city": {
        "id": 1,
        "name": "Seattle",
        "coverage_percentage": 42.5,
        "streets_traveled": 21250,
        "streets_total": 50000,
        "distance_traveled_m": 850000.0,
        "distance_total_m": 2000000.0,
    },
    "neighborhoods": [
        {
            "id": 10, "name": "Fremont", "coverage_percentage": 73.2,
            "streets_traveled": 366, "streets_total": 500,
            "distance_traveled_m": 15000.0, "distance_total_m": 20000.0,
        },
        {
            "id": 11, "name": "Capitol Hill", "coverage_percentage": 45.0,
            "streets_traveled": 360, "streets_total": 800,
            "distance_traveled_m": 12000.0, "distance_total_m": 28000.0,
        },
        {
            "id": 12, "name": "Ballard", "coverage_percentage": 98.5,
            "streets_traveled": 591, "streets_total": 600,
            "distance_traveled_m": 24000.0, "distance_total_m": 25000.0,
        },
        {
            "id": 13, "name": "University District", "coverage_percentage": 12.0,
            "streets_traveled": 48, "streets_total": 400,
            "distance_traveled_m": 2000.0, "distance_total_m": 16000.0,
        },
    ],
}

NEIGHBORHOOD_DETAIL_RESPONSE = {
    "neighborhood": {
        "id": 10,
        "name": "Fremont",
        "city_name": "Seattle",
        "coverage_percentage": 73.2,
        "streets_traveled": 366,
        "streets_total": 500,
    },
    "boundary": {},
}

OVERALL_STATS_RESPONSE = {
    "total_activities": 150,
    "total_distance_meters": 1200000.0,
    "total_unique_streets": 21250,
    "cities": [
        {"city_name": "Seattle", "coverage_percentage": 42.5, "streets_traveled": 21250, "streets_total": 50000},
    ],
}

PROGRESS_RESPONSE = {
    "city_name": "Seattle",
    "current_coverage_percentage": 42.5,
    "milestones": [
        {"label": "25%", "neighborhood_name": "Fremont", "reached": True, "date": "2025-06-15"},
        {"label": "50%", "neighborhood_name": "", "reached": False, "date": None},
        {"label": "75%", "neighborhood_name": "", "reached": False, "date": None},
        {"label": "100%", "neighborhood_name": "", "reached": False, "date": None},
    ],
    "timeline": [
        {"date": "2025-03-01", "coverage_percentage": 10.0, "streets_traveled": 5000},
        {"date": "2025-06-01", "coverage_percentage": 25.0, "streets_traveled": 12500},
        {"date": "2025-09-01", "coverage_percentage": 35.0, "streets_traveled": 17500},
        {"date": "2026-01-01", "coverage_percentage": 40.0, "streets_traveled": 20000},
        {"date": "2026-03-01", "coverage_percentage": 42.5, "streets_traveled": 21250},
    ],
}

STREETS_GEOJSON_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"id": 1, "name": "N 36th St", "highway_type": "residential", "length_meters": 350.0, "is_traveled": False, "coverage_ratio": 0.0},
            "geometry": {"type": "LineString", "coordinates": [[-122.35, 47.65], [-122.36, 47.65]]},
        },
        {
            "type": "Feature",
            "properties": {"id": 2, "name": "N 36th St", "highway_type": "residential", "length_meters": 280.0, "is_traveled": False, "coverage_ratio": 0.0},
            "geometry": {"type": "LineString", "coordinates": [[-122.36, 47.65], [-122.37, 47.65]]},
        },
        {
            "type": "Feature",
            "properties": {"id": 3, "name": "Fremont Ave N", "highway_type": "tertiary", "length_meters": 890.0, "is_traveled": False, "coverage_ratio": 0.0},
            "geometry": {"type": "LineString", "coordinates": [[-122.35, 47.64], [-122.35, 47.66]]},
        },
        {
            "type": "Feature",
            "properties": {"id": 4, "name": None, "highway_type": "service", "length_meters": 45.0, "is_traveled": False, "coverage_ratio": 0.0},
            "geometry": {"type": "LineString", "coordinates": [[-122.35, 47.65], [-122.351, 47.651]]},
        },
    ],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """A PacmanClient with all methods mocked."""
    client = PacmanClient.__new__(PacmanClient)
    client._base = "http://localhost:8000"
    client._token = "test-token"

    client.list_cities = AsyncMock(return_value=CITIES_RESPONSE)
    client.list_neighborhoods = AsyncMock(return_value=NEIGHBORHOODS_RESPONSE)
    client.city_coverage = AsyncMock(return_value=CITY_COVERAGE_RESPONSE)
    client.neighborhood_coverage = AsyncMock(return_value=NEIGHBORHOOD_DETAIL_RESPONSE)
    client.city_streets = AsyncMock(return_value=STREETS_GEOJSON_RESPONSE)
    client.overall_stats = AsyncMock(return_value=OVERALL_STATS_RESPONSE)
    client.city_progress = AsyncMock(return_value=PROGRESS_RESPONSE)
    client.health = AsyncMock(return_value=OVERALL_STATS_RESPONSE)

    return client
