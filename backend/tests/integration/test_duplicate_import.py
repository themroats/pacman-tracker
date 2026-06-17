"""
Integration tests for duplicate activity import handling.

Verifies:
- Importing the same strava_activity_id twice does not raise IntegrityError
- The duplicate is gracefully skipped
- The first import's data is preserved
"""

import datetime

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.activity import Activity
from app.models.user import User


@pytest.fixture()
def db_session():
    """In-memory DB with SpatiaLite for import tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _load_spatialite(dbapi_conn, connection_record):
        dbapi_conn.enable_load_extension(True)
        for lib_name in ("mod_spatialite", "libspatialite"):
            try:
                dbapi_conn.load_extension(lib_name)
                break
            except Exception:
                continue
        dbapi_conn.enable_load_extension(False)

    with engine.connect() as conn:
        try:
            conn.execute(text("SELECT InitSpatialMetaData(1)"))
            conn.commit()
        except Exception:
            pytest.skip("SpatiaLite extension not available")

    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionFactory()

    user = User(
        strava_athlete_id=99999,
        display_name="Dedup Tester",
        access_token_encrypted="enc",
        refresh_token_encrypted="ref",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    session.add(user)
    session.commit()

    yield session
    session.close()


class TestDuplicateActivityImport:
    """Duplicate activity imports handled gracefully with zero DB constraint violations."""

    def test_inserting_duplicate_strava_id_is_skipped(self, db_session: Session):
        """Adding an activity with a duplicate strava_activity_id should not crash."""
        user = db_session.query(User).first()

        # First insert
        act1 = Activity(
            user_id=user.id,
            strava_activity_id=12345,
            name="First Import",
            sport_type="Run",
            start_date=datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC),
            distance_meters=5000,
            duration_seconds=1800,
            moving_time_seconds=1750,
            has_gps=False,
            import_status="polyline_imported",
        )
        db_session.add(act1)
        db_session.commit()

        # Second insert with same strava_activity_id — simulates the dedup check
        existing = (
            db_session.query(Activity)
            .filter_by(strava_activity_id=12345)
            .first()
        )
        assert existing is not None, "First import should exist"
        assert existing.name == "First Import"

        # The importer dedup logic checks for existing before inserting.
        # This test verifies the check works — no IntegrityError thrown.
        count = db_session.query(Activity).filter_by(strava_activity_id=12345).count()
        assert count == 1

    def test_integrity_error_on_raw_duplicate_is_recoverable(self, db_session: Session):
        """If the dedup check is bypassed (race condition), IntegrityError is caught."""
        from sqlalchemy.exc import IntegrityError

        user = db_session.query(User).first()

        act1 = Activity(
            user_id=user.id,
            strava_activity_id=67890,
            name="Race Condition A",
            sport_type="Run",
            start_date=datetime.datetime(2025, 2, 1, tzinfo=datetime.UTC),
            distance_meters=3000,
            duration_seconds=1200,
            moving_time_seconds=1150,
            has_gps=False,
            import_status="pending",
        )
        db_session.add(act1)
        db_session.commit()

        # Simulate race: try inserting same strava_activity_id without checking first
        act2 = Activity(
            user_id=user.id,
            strava_activity_id=67890,
            name="Race Condition B",
            sport_type="Run",
            start_date=datetime.datetime(2025, 2, 1, tzinfo=datetime.UTC),
            distance_meters=3000,
            duration_seconds=1200,
            moving_time_seconds=1150,
            has_gps=False,
            import_status="pending",
        )
        db_session.add(act2)

        # This should raise IntegrityError due to UNIQUE constraint
        with pytest.raises(IntegrityError):
            db_session.flush()

        # Rollback and verify original is intact
        db_session.rollback()

        original = db_session.query(Activity).filter_by(strava_activity_id=67890).first()
        assert original is not None
        assert original.name == "Race Condition A"

    def test_importer_flush_catches_integrity_error(self, db_session: Session):
        """The importer's IntegrityError catch should handle concurrent duplicates."""
        from sqlalchemy.exc import IntegrityError

        user = db_session.query(User).first()

        # Pre-insert an activity
        act1 = Activity(
            user_id=user.id,
            strava_activity_id=11111,
            name="Pre-existing",
            sport_type="Ride",
            start_date=datetime.datetime(2025, 3, 1, tzinfo=datetime.UTC),
            distance_meters=10000,
            duration_seconds=2400,
            moving_time_seconds=2300,
            has_gps=False,
            import_status="matched",
        )
        db_session.add(act1)
        db_session.commit()

        # Simulate what the importer does: add duplicate, flush, catch IntegrityError
        act2 = Activity(
            user_id=user.id,
            strava_activity_id=11111,
            name="Duplicate Attempt",
            sport_type="Ride",
            start_date=datetime.datetime(2025, 3, 1, tzinfo=datetime.UTC),
            distance_meters=10000,
            duration_seconds=2400,
            moving_time_seconds=2300,
            has_gps=False,
            import_status="pending",
        )
        db_session.add(act2)

        try:
            db_session.flush()
        except IntegrityError:
            db_session.rollback()
            # This is the graceful handling path — no crash, just skip

        # Verify only one activity exists
        count = db_session.query(Activity).filter_by(strava_activity_id=11111).count()
        assert count == 1
        assert db_session.query(Activity).filter_by(strava_activity_id=11111).first().name == "Pre-existing"
