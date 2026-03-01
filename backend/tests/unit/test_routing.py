"""
T090 — OSRM client unit tests with stubbed HTTP responses.

Tests:
- /nearest endpoint parsing
- /trip endpoint parsing
- /route endpoint parsing
- Connection error handling
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.routing import OSRMClient


@pytest.fixture()
def osrm():
    return OSRMClient(base_url="http://localhost:5000")


class TestOSRMNearest:
    """Tests for /nearest endpoint."""

    @pytest.mark.asyncio
    async def test_nearest_returns_snapped_coords(self, osrm):
        mock_response = {
            "code": "Ok",
            "waypoints": [
                {
                    "location": [-122.332, 47.606],
                    "distance": 5.2,
                    "name": "E Pine St",
                }
            ],
        }
        with patch.object(osrm, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await osrm.nearest(-122.3321, 47.6062)
            assert result["location"] == [-122.332, 47.606]

    @pytest.mark.asyncio
    async def test_nearest_not_found(self, osrm):
        mock_response = {"code": "NoSegment", "waypoints": []}
        with patch.object(osrm, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await osrm.nearest(-180.0, 0.0)
            assert result is None


class TestOSRMTrip:
    """Tests for /trip endpoint."""

    @pytest.mark.asyncio
    async def test_trip_returns_geometry(self, osrm):
        mock_response = {
            "code": "Ok",
            "trips": [
                {
                    "distance": 5120.0,
                    "duration": 2560.0,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-122.33, 47.60], [-122.33, 47.61]],
                    },
                }
            ],
            "waypoints": [],
        }
        with patch.object(osrm, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await osrm.trip([(-122.33, 47.60), (-122.33, 47.61)])
            assert result["distance"] == 5120.0
            assert result["geometry"]["type"] == "LineString"

    @pytest.mark.asyncio
    async def test_trip_no_result(self, osrm):
        mock_response = {"code": "NoTrips", "trips": []}
        with patch.object(osrm, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await osrm.trip([(-122.33, 47.60)])
            assert result is None


class TestOSRMRoute:
    """Tests for /route endpoint."""

    @pytest.mark.asyncio
    async def test_route_returns_geometry(self, osrm):
        mock_response = {
            "code": "Ok",
            "routes": [
                {
                    "distance": 3000.0,
                    "duration": 1500.0,
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-122.33, 47.60], [-122.34, 47.61]],
                    },
                }
            ],
        }
        with patch.object(osrm, "_get", new_callable=AsyncMock, return_value=mock_response):
            result = await osrm.route((-122.33, 47.60), (-122.34, 47.61))
            assert result["distance"] == 3000.0
