"""
Unit tests for the verification reset script.

Verifies the fast data-only reset restores the demo baseline, truncates
run-accumulated data, preserves the snapshot tables, and keeps exactly one user.
Runs offline against a PostGIS test database.
"""

import datetime

from geoalchemy2.shape import from_shape
from sqlalchemy import select

from app.models.activity import Activity
from app.models.city import City
from app.models.route import RouteSuggestion
from app.models.street import StreetSegment
from app.models.user import User
from app.scripts.reset_verification import RUN_ACCUMULATED_TABLES, reset_data
from app.scripts.seed_verification import (
    SAMPLE_ACTIVITY_COUNT,
    SAMPLE_STREET_COUNT,
    ensure_demo_user,
    seed_sample_data,
)
from tests.conftest import GeoFactory
from tests.unit.test_seed_verification import _build_snapshot


def _add_route_suggestion(session, user, city) -> None:
    """Insert a run-accumulated route suggestion to be cleared by reset."""
    street = session.scalars(select(StreetSegment).limit(1)).first()
    session.add(
        RouteSuggestion(
            user_id=user.id,
            city_id=city.id,
            start_point=from_shape(GeoFactory.SEATTLE_CENTER, srid=4326),
            route_geometry=street.geometry,
            distance_meters=4200.0,
            estimated_duration_seconds=1500,
            requested_distance_meters=4000.0,
            untraveled_distance_meters=1000.0,
            untraveled_ratio=0.25,
        )
    )
    session.flush()


class TestResetData:
    def test_restores_activity_baseline(self, db_session):
        city = _build_snapshot(db_session)
        user = ensure_demo_user(db_session)
        seed_sample_data(db_session, user)

        # Mutate: add an extra activity beyond the baseline.
        db_session.add(
            Activity(
                user_id=user.id,
                strava_activity_id=123456789,
                name="Extra Run",
                sport_type="Run",
                start_date=datetime.datetime(2026, 6, 10, 8, 0, 0),
                distance_meters=3000.0,
                duration_seconds=1200,
                moving_time_seconds=1150,
                has_gps=True,
                is_on_street=True,
                import_status="matched",
                city_id=city.id,
            )
        )
        db_session.flush()
        assert (
            len(list(db_session.scalars(select(Activity).where(Activity.user_id == user.id))))
            == SAMPLE_ACTIVITY_COUNT + 1
        )

        reset_data(db_session, user)

        activities = list(db_session.scalars(select(Activity).where(Activity.user_id == user.id)))
        assert len(activities) == SAMPLE_ACTIVITY_COUNT

    def test_truncates_run_accumulated_tables(self, db_session):
        city = _build_snapshot(db_session)
        user = ensure_demo_user(db_session)
        seed_sample_data(db_session, user)
        _add_route_suggestion(db_session, user, city)
        assert len(list(db_session.scalars(select(RouteSuggestion)))) == 1

        reset_data(db_session, user)

        assert len(list(db_session.scalars(select(RouteSuggestion)))) == 0

    def test_preserves_snapshot_tables(self, db_session):
        _build_snapshot(db_session)
        user = ensure_demo_user(db_session)
        seed_sample_data(db_session, user)

        streets_before = db_session.query(StreetSegment).count()
        cities_before = db_session.query(City).count()

        reset_data(db_session, user)

        assert db_session.query(StreetSegment).count() == streets_before
        assert db_session.query(City).count() == cities_before

    def test_keeps_single_user(self, db_session):
        _build_snapshot(db_session)
        user = ensure_demo_user(db_session)
        seed_sample_data(db_session, user)

        reset_data(db_session, user)

        assert len(list(db_session.scalars(select(User)))) == 1

    def test_coverage_baseline_after_reset(self, db_session):
        _build_snapshot(db_session)
        user = ensure_demo_user(db_session)
        seed_sample_data(db_session, user)
        reset_data(db_session, user)

        from app.models.coverage import UserStreetCoverage

        coverage = list(
            db_session.scalars(
                select(UserStreetCoverage).where(UserStreetCoverage.user_id == user.id)
            )
        )
        assert len(coverage) == SAMPLE_STREET_COUNT

    def test_run_accumulated_table_list_is_nonempty(self):
        assert RUN_ACCUMULATED_TABLES
        assert "route_suggestions" in RUN_ACCUMULATED_TABLES
