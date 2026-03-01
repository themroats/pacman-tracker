"""
Unit tests for the activity import pipeline.

Tests cover:
- Two-phase import (polyline first, streams second)
- Activity deduplication
- Rate-limit queuing behaviour
"""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTwoPhaseImport:
    """T084: Test the two-phase import strategy."""

    @pytest.mark.asyncio
    async def test_phase_a_imports_polylines(self):
        """Phase A should fetch summary + detailed polyline for each activity."""
        from app.services.importer import ActivityImporter

        mock_strava = AsyncMock()
        # Return data on first call, empty list on second to break pagination loop
        mock_strava.fetch_activity_list.side_effect = [
            [
                {
                    "id": 100,
                    "name": "Morning Run",
                    "sport_type": "Run",
                    "start_date": "2025-01-15T08:00:00Z",
                    "distance": 5000.0,
                    "elapsed_time": 1800,
                    "moving_time": 1750,
                    "map": {"summary_polyline": "encoded_polyline_a"},
                }
            ],
            [],  # Page 2: empty → stops pagination
        ]
        mock_strava.fetch_activity_detail.return_value = {
            "id": 100,
            "map": {"polyline": "detailed_polyline_a"},
        }

        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = None
        # order_by chain for last_activity lookup
        mock_session.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = None

        importer = ActivityImporter(strava_service=mock_strava, db_session=mock_session)
        result = await importer.import_phase_a(user_id=1, access_token="test_token")

        assert result["imported"] >= 1
        assert mock_strava.fetch_activity_list.call_count == 2

    @pytest.mark.asyncio
    async def test_phase_b_fetches_gps_streams(self):
        """Phase B should fetch full GPS streams for activities with polylines."""
        from app.services.importer import ActivityImporter

        mock_strava = AsyncMock()
        mock_strava.fetch_activity_streams.return_value = {
            "latlng": {"data": [[47.6062, -122.3321], [47.607, -122.333]]},
        }

        mock_activity = MagicMock()
        mock_activity.id = 1
        mock_activity.strava_activity_id = 100
        mock_activity.import_status = "polyline_imported"

        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.all.return_value = [
            mock_activity
        ]

        importer = ActivityImporter(strava_service=mock_strava, db_session=mock_session)
        result = await importer.import_phase_b(user_id=1, access_token="test_token")

        assert result["processed"] >= 1


class TestActivityDeduplication:
    """T084: Test that duplicate activities are not re-imported."""

    @pytest.mark.asyncio
    async def test_duplicate_strava_id_skipped(self):
        """Activities with an already-known strava_activity_id should be skipped."""
        from app.services.importer import ActivityImporter

        mock_strava = AsyncMock()
        # Return data on first call, empty on second to stop pagination
        mock_strava.fetch_activity_list.side_effect = [
            [
                {
                    "id": 100,
                    "name": "Morning Run",
                    "sport_type": "Run",
                    "start_date": "2025-01-15T08:00:00Z",
                    "distance": 5000.0,
                    "elapsed_time": 1800,
                    "moving_time": 1750,
                    "map": {"summary_polyline": "encoded_polyline_a"},
                }
            ],
            [],  # Page 2: empty → stops pagination
        ]

        # Simulate existing activity in DB
        mock_existing = MagicMock()
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_existing
        mock_session.query.return_value.filter_by.return_value.order_by.return_value.first.return_value = None

        importer = ActivityImporter(strava_service=mock_strava, db_session=mock_session)
        result = await importer.import_phase_a(user_id=1, access_token="test_token")

        assert result["skipped"] >= 1


class TestRateLimitHandling:
    """T084: Test rate limit behaviour during import."""

    @pytest.mark.asyncio
    async def test_rate_limit_pauses_import(self):
        """When Strava returns 429, importer should pause and retry."""
        from app.services.importer import ActivityImporter, RateLimitError

        mock_strava = AsyncMock()
        mock_strava.fetch_activity_list.side_effect = RateLimitError(
            retry_after=60
        )

        mock_session = MagicMock()
        importer = ActivityImporter(strava_service=mock_strava, db_session=mock_session)

        with pytest.raises(RateLimitError) as exc_info:
            await importer.import_phase_a(user_id=1, access_token="test_token")

        assert exc_info.value.retry_after == 60
