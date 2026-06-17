"""
Unit tests for the activity import pipeline.

Tests cover:
- Two-phase import (polyline first, streams second)
- Activity deduplication
- Rate-limit queuing behaviour
"""

import datetime
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTwoPhaseImport:
    """Test the two-phase import strategy."""

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
        with patch(
            "app.services.importer.asyncio.to_thread",
            new=AsyncMock(return_value={"processed": 1, "failed": 0, "matched": 0}),
        ) as to_thread:
            result = await importer.import_phase_b(user_id=1, access_token="test_token")

        assert result["processed"] >= 1
        to_thread.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_phase_b_uses_separate_session_for_activity_updates(self):
        """Phase B should update activities through a thread-owned session, not the caller session."""
        from app.services.importer import ActivityImporter

        class FakeQuery:
            def __init__(self, session):
                self._session = session
                self._filters = {}

            def filter_by(self, **kwargs):
                self._filters.update(kwargs)
                return self

            def all(self):
                matches = []
                for row in self._session._store.values():
                    if all(getattr(row, key) == value for key, value in self._filters.items()):
                        matches.append(self._session.get(None, row.id))
                return matches

        class FakeSession:
            def __init__(self, store):
                self._store = store
                self._identity_map = {}

            def query(self, model):
                return FakeQuery(self)

            def get(self, model, key):
                if key not in self._identity_map and key in self._store:
                    self._identity_map[key] = deepcopy(self._store[key])
                return self._identity_map.get(key)

            def commit(self):
                for key, value in self._identity_map.items():
                    self._store[key] = deepcopy(value)

            def rollback(self):
                self._identity_map = {}

            def refresh(self, obj):
                latest = self._store[obj.id]
                obj.__dict__.update(deepcopy(latest.__dict__))

            def close(self):
                return None

        store = {
            1: SimpleNamespace(
                id=1,
                user_id=99,
                strava_activity_id=555001,
                name="Coverage Session Boundary Run",
                sport_type="Run",
                start_date=datetime.datetime.now(datetime.UTC),
                distance_meters=5000.0,
                duration_seconds=1800,
                moving_time_seconds=1750,
                summary_polyline="summary",
                detailed_polyline=None,
                gps_trace=None,
                has_gps=False,
                is_on_street=True,
                import_status="polyline_imported",
                city_id=None,
            )
        }

        request_session = FakeSession(store)
        loaded_activity = request_session.get(None, 1)
        assert loaded_activity.import_status == "polyline_imported"

        mock_strava = AsyncMock()
        mock_strava.fetch_activity_streams.return_value = {
            "latlng": {"data": [[47.6062, -122.3321], [47.6070, -122.3330]]},
        }

        importer = ActivityImporter(strava_service=mock_strava, db_session=request_session)

        async def run_inline(func, *args, **kwargs):
            return func(*args, **kwargs)

        with patch(
            "app.database.get_session_factory",
            return_value=lambda: FakeSession(store),
        ), patch(
            "app.services.importer.asyncio.to_thread",
            side_effect=run_inline,
        ), patch(
            "app.services.coverage.run_coverage_matching",
            return_value=0.75,
        ), patch(
            "app.services.coverage.classify_activity_on_street",
            return_value=True,
        ):
            result = await importer.import_phase_b(user_id=99, access_token="test-token")

        assert result == {"processed": 1, "failed": 0, "matched": 1}

        # The caller session still holds its original loaded instance; it is not directly mutated.
        assert loaded_activity.import_status == "polyline_imported"
        assert loaded_activity.gps_trace is None

        request_session.refresh(loaded_activity)
        assert loaded_activity.import_status == "matched"
        assert loaded_activity.has_gps is True
        assert loaded_activity.gps_trace is not None


class TestActivityDeduplication:
    """Test that duplicate activities are not re-imported."""

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
    """Test rate limit behaviour during import."""

    @pytest.mark.asyncio
    @patch("app.services.importer.asyncio.sleep", new_callable=AsyncMock)
    async def test_rate_limit_pauses_import(self, mock_sleep):
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
        assert mock_sleep.await_count == 5
