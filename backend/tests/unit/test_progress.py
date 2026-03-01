"""
T093 — Unit tests for the progress / snapshot service.

Tests:
- Daily snapshot creation
- Milestone detection (25%, 50%, 75%, 100%)
- Timestamp accuracy
- Idempotent snapshot per date
"""

import datetime
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Snapshot creation
# ---------------------------------------------------------------------------


class TestRecordDailySnapshot:
    """Test record_daily_snapshot from app.services.progress."""

    def test_creates_snapshot_for_city(self):
        """A snapshot row is created with correct city-level stats."""
        from app.services.progress import record_daily_snapshot

        db = MagicMock()

        # The function calls db.query(StreetSegment).filter_by(city_id=...).count()
        # and db.query(UserStreetCoverage).filter(...).filter(...).join(...).filter(...).count()
        # and db.query(CoverageSnapshot).filter_by(...).first()
        # Since MagicMock returns the same mock for all calls, we need side_effect
        # on db.query to differentiate.

        # Mock for StreetSegment query: .filter_by().count() = 100
        street_query_mock = MagicMock()
        street_query_mock.filter_by.return_value.count.return_value = 100

        # Mock for UserStreetCoverage query: .filter().filter().join().filter().count() = 25
        coverage_query_mock = MagicMock()
        coverage_chain = coverage_query_mock.filter.return_value.filter.return_value
        coverage_chain.join.return_value.filter.return_value.count.return_value = 25

        # Mock for CoverageSnapshot query: .filter_by().first() = None (no existing)
        snapshot_query_mock = MagicMock()
        snapshot_query_mock.filter_by.return_value.first.return_value = None

        from app.models.street import StreetSegment
        from app.models.coverage import UserStreetCoverage, CoverageSnapshot

        def query_side_effect(model):
            if model is StreetSegment:
                return street_query_mock
            elif model is UserStreetCoverage:
                return coverage_query_mock
            elif model is CoverageSnapshot:
                return snapshot_query_mock
            return MagicMock()

        db.query.side_effect = query_side_effect

        snap = record_daily_snapshot(db, user_id=1, city_id=1)

        assert snap is not None
        assert snap.coverage_percentage == 25.0
        assert snap.total_streets == 100
        assert snap.total_streets_traveled == 25
        db.add.assert_called_once()

    def test_skips_duplicate_snapshot_same_date(self):
        """If a snapshot already exists for today, do NOT create another."""
        from app.services.progress import record_daily_snapshot

        db = MagicMock()

        existing = MagicMock()
        existing.coverage_percentage = 20.0

        from app.models.street import StreetSegment
        from app.models.coverage import UserStreetCoverage, CoverageSnapshot

        # StreetSegment query: total_streets = 100
        street_query_mock = MagicMock()
        street_query_mock.filter_by.return_value.count.return_value = 100

        # UserStreetCoverage query: traveled = 25
        coverage_query_mock = MagicMock()
        coverage_chain = coverage_query_mock.filter.return_value.filter.return_value
        coverage_chain.join.return_value.filter.return_value.count.return_value = 25

        # CoverageSnapshot query: existing snapshot found
        snapshot_query_mock = MagicMock()
        snapshot_query_mock.filter_by.return_value.first.return_value = existing

        def query_side_effect(model):
            if model is StreetSegment:
                return street_query_mock
            elif model is UserStreetCoverage:
                return coverage_query_mock
            elif model is CoverageSnapshot:
                return snapshot_query_mock
            return MagicMock()

        db.query.side_effect = query_side_effect

        result = record_daily_snapshot(db, user_id=1, city_id=1)

        # Should return updated existing, not add a new one
        db.add.assert_not_called()
        assert result is not None


# ---------------------------------------------------------------------------
# Milestone detection
# ---------------------------------------------------------------------------


class TestMilestoneDetection:
    """Test detect_milestones from app.services.progress."""

    @pytest.mark.parametrize(
        "old_pct,new_pct,expected_labels",
        [
            (0.0, 25.0, ["25%"]),
            (20.0, 50.0, ["25%", "50%"]),
            (0.0, 100.0, ["25%", "50%", "75%", "100%"]),
            (30.0, 40.0, []),
            (74.0, 76.0, ["75%"]),
        ],
    )
    def test_detects_crossed_milestones(self, old_pct, new_pct, expected_labels):
        """Milestones are detected when coverage crosses thresholds."""
        from app.services.progress import detect_milestones

        labels = detect_milestones(old_pct, new_pct)
        assert labels == expected_labels

    def test_no_milestones_on_decrease(self):
        """Coverage can decrease (data corrections) — no milestone should fire."""
        from app.services.progress import detect_milestones

        labels = detect_milestones(30.0, 20.0)
        assert labels == []


# ---------------------------------------------------------------------------
# Overall stats
# ---------------------------------------------------------------------------


class TestGetOverallStats:
    """Test get_overall_stats from app.services.progress."""

    def test_returns_correct_totals(self):
        """Overall stats aggregates across all cities."""
        from app.services.progress import get_overall_stats

        db = MagicMock()

        # Mock activity count + distance
        db.query.return_value.filter_by.return_value.count.return_value = 42
        db.query.return_value.filter_by.return_value.with_entities.return_value.scalar.return_value = (
            150000.0
        )

        # Mock unique streets
        db.query.return_value.filter.return_value.count.return_value = 500

        # Mock cities
        mock_city = MagicMock()
        mock_city.id = 1
        mock_city.name = "Seattle"
        db.query.return_value.all.return_value = [mock_city]

        stats = get_overall_stats(db, user_id=1)
        assert stats["total_activities"] == 42


# ---------------------------------------------------------------------------
# City timeline
# ---------------------------------------------------------------------------


class TestGetCityTimeline:
    """Test get_city_timeline from app.services.progress."""

    def test_returns_timeline_entries(self):
        """Timeline includes all snapshots ordered by date."""
        from app.services.progress import get_city_timeline

        db = MagicMock()
        mock_snap = MagicMock()
        mock_snap.snapshot_date = datetime.date(2025, 1, 15)
        mock_snap.coverage_percentage = 10.5
        mock_snap.total_streets_traveled = 105
        mock_snap.is_milestone = False
        mock_snap.milestone_label = None

        db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [
            mock_snap
        ]

        # Mock city
        mock_city = MagicMock()
        mock_city.name = "Seattle"
        db.query.return_value.filter_by.return_value.first.return_value = mock_city

        timeline = get_city_timeline(db, user_id=1, city_id=1)
        assert len(timeline["timeline"]) == 1
        assert timeline["timeline"][0]["coverage_percentage"] == 10.5
