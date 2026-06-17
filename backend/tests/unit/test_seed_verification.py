"""
Unit tests for the verification seed script (feature 008, T017).

Tests the seed building blocks directly against a PostGIS test database. They run
offline (no OSM downloads, no Strava). The guarded CLI entrypoint is covered
separately in test_verify_guard.py.
"""

import datetime

import pytest
from geoalchemy2.shape import from_shape
from sqlalchemy import select

from app.models.activity import Activity
from app.models.city import City
from app.models.coverage import CoverageSnapshot, UserStreetCoverage
from app.models.street import StreetSegment
from app.models.user import User
from app.scripts.seed_verification import (
    EXIT_UNEXPECTED_USERS,
    SAMPLE_ACTIVITY_COUNT,
    SAMPLE_STREET_COUNT,
    clear_sample_data,
    ensure_demo_user,
    seed_sample_data,
)
from tests.conftest import GeoFactory


def _build_snapshot(session, num_streets: int = SAMPLE_STREET_COUNT + 5) -> City:
    """Create a minimal restored-snapshot stand-in: one city + street segments."""
    city = City(
        name="Seattle",
        state="Washington",
        boundary=from_shape(GeoFactory.make_city_boundary(), srid=4326),
        projected_crs="EPSG:32610",
    )
    session.add(city)
    session.flush()

    for i in range(num_streets):
        line = GeoFactory.make_street_segment(
            start=(-122.3321 + i * 0.001, 47.6062),
            end=(-122.3340 + i * 0.001, 47.6080),
        )
        session.add(
            StreetSegment(
                city_id=city.id,
                osm_way_id=1000 + i,
                osm_node_start=2000 + i,
                osm_node_end=3000 + i,
                name=f"Test St {i}",
                highway_type="residential",
                geometry=from_shape(line, srid=4326),
                length_meters=250.0,
            )
        )
    session.flush()
    return city


class TestSeedSampleData:
    def test_creates_single_demo_user(self, db_session):
        _build_snapshot(db_session)
        user = ensure_demo_user(db_session)
        seed_sample_data(db_session, user)

        users = list(db_session.scalars(select(User)))
        assert len(users) == 1
        assert users[0].display_name == "Demo Runner"
        assert users[0].sync_status == "complete"

    def test_seeds_expected_activities_and_coverage(self, db_session):
        _build_snapshot(db_session)
        user = ensure_demo_user(db_session)
        seed_sample_data(db_session, user)

        activities = list(db_session.scalars(select(Activity).where(Activity.user_id == user.id)))
        assert len(activities) == SAMPLE_ACTIVITY_COUNT
        assert all(a.import_status == "matched" for a in activities)
        assert all(a.has_gps for a in activities)

        coverage = list(
            db_session.scalars(
                select(UserStreetCoverage).where(UserStreetCoverage.user_id == user.id)
            )
        )
        assert len(coverage) == SAMPLE_STREET_COUNT
        assert all(c.is_traveled for c in coverage)

        snapshots = list(
            db_session.scalars(select(CoverageSnapshot).where(CoverageSnapshot.user_id == user.id))
        )
        assert len(snapshots) == 1
        assert snapshots[0].total_streets_traveled == SAMPLE_STREET_COUNT

    def test_idempotent_no_duplicate_user_or_activities(self, db_session):
        _build_snapshot(db_session)
        user = ensure_demo_user(db_session)
        seed_sample_data(db_session, user)

        # Re-run the data step the way the seed entrypoint does (clear + seed).
        clear_sample_data(db_session, user)
        seed_sample_data(db_session, user)

        assert len(list(db_session.scalars(select(User)))) == 1
        activities = list(db_session.scalars(select(Activity).where(Activity.user_id == user.id)))
        assert len(activities) == SAMPLE_ACTIVITY_COUNT

    def test_ensure_demo_user_is_idempotent(self, db_session):
        _build_snapshot(db_session)
        first = ensure_demo_user(db_session)
        second = ensure_demo_user(db_session)
        assert first.id == second.id
        assert len(list(db_session.scalars(select(User)))) == 1

    def test_ensure_demo_user_fails_fast_on_unexpected_users(self, db_session):
        """A non-demo user breaks DEV_AUTH_BYPASS determinism — refuse to seed."""
        _build_snapshot(db_session)
        db_session.add(
            User(
                strava_athlete_id=123456,
                display_name="Someone Else",
                access_token_encrypted="x",
                refresh_token_encrypted="x",
                token_expires_at=datetime.datetime(2099, 1, 1),
                strava_scope="read",
            )
        )
        db_session.flush()

        with pytest.raises(SystemExit) as exc:
            ensure_demo_user(db_session)
        assert exc.value.code == EXIT_UNEXPECTED_USERS

    def test_repeated_seed_produces_identical_baseline(self, db_session):
        """T023 — re-seeding yields the same baseline (deterministic, SC-003)."""
        _build_snapshot(db_session)
        user = ensure_demo_user(db_session)

        seed_sample_data(db_session, user)
        first_activities = sorted(
            a.strava_activity_id
            for a in db_session.scalars(select(Activity).where(Activity.user_id == user.id))
        )
        first_coverage = db_session.query(UserStreetCoverage).filter_by(user_id=user.id).count()

        clear_sample_data(db_session, user)
        seed_sample_data(db_session, user)
        second_activities = sorted(
            a.strava_activity_id
            for a in db_session.scalars(select(Activity).where(Activity.user_id == user.id))
        )
        second_coverage = db_session.query(UserStreetCoverage).filter_by(user_id=user.id).count()

        assert first_activities == second_activities
        assert first_coverage == second_coverage
