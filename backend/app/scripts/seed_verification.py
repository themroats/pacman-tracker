"""
Seed the isolated verification database (feature 008).

Layers a single demo user plus deterministic sample activities and coverage on
top of a restored street snapshot, so protected pages render meaningfully in the
local browser verification harness.

Guarded so it can ONLY target the verification database. Idempotent: re-running
restores the same baseline without creating duplicate users or activities.

Usage::

    python -m app.scripts.seed_verification --database-url postgresql://.../pacman_verify
"""

from __future__ import annotations

import argparse
import datetime
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.database import create_db_engine
from app.models.activity import Activity
from app.models.city import City
from app.models.coverage import CoverageSnapshot, UserStreetCoverage
from app.models.street import StreetSegment
from app.models.user import User
from app.scripts._verify_guard import assert_verification_db, resolve_verification_url
from app.services.crypto import encrypt_token

# --- Deterministic demo identity (synthetic, never a real athlete) ---
DEMO_STRAVA_ATHLETE_ID = 9_000_000_001
DEMO_DISPLAY_NAME = "Demo Runner"
DEMO_TOKEN_PLACEHOLDER = "verification-harness-placeholder-not-a-real-token"

# How many real street segments to mark as covered / build sample activities from.
SAMPLE_STREET_COUNT = 25
SAMPLE_ACTIVITY_COUNT = 3

EXIT_SNAPSHOT_MISSING = 6
EXIT_UNEXPECTED_USERS = 8


def ensure_demo_user(session: Session) -> User:
    """Ensure the demo user exists and is the ONLY user. Idempotent.

    DEV_AUTH_BYPASS authenticates every request as the first user, so the harness
    is only deterministic when the synthetic demo user is the sole user in the
    verification DB. If any non-demo users exist, fail fast with an actionable
    message instead of attempting a partial cleanup — other user-linked tables
    (routes, plans, start points) could otherwise violate FK constraints or leave
    inconsistent data behind.
    """
    other_users = (
        session.query(User).filter(User.strava_athlete_id != DEMO_STRAVA_ATHLETE_ID).count()
    )
    if other_users:
        print(
            f"Verification DB contains {other_users} unexpected non-demo user(s). "
            "DEV_AUTH_BYPASS authenticates as the first user, so seeding would not be "
            "deterministic. Rebuild the isolated DB with infra/verify-clean.ps1, then re-run.",
            file=sys.stderr,
        )
        sys.exit(EXIT_UNEXPECTED_USERS)

    user = session.scalar(select(User).where(User.strava_athlete_id == DEMO_STRAVA_ATHLETE_ID))
    if user is not None:
        return user

    city = session.scalar(select(City).order_by(City.id))
    encrypted = encrypt_token(DEMO_TOKEN_PLACEHOLDER)
    user = User(
        strava_athlete_id=DEMO_STRAVA_ATHLETE_ID,
        display_name=DEMO_DISPLAY_NAME,
        access_token_encrypted=encrypted,
        refresh_token_encrypted=encrypted,
        token_expires_at=datetime.datetime(2099, 1, 1),
        strava_scope="read,activity:read",
        home_city_id=city.id if city else None,
        sync_status="complete",
        last_sync_at=datetime.datetime.now(datetime.UTC),
    )
    session.add(user)
    session.flush()
    return user


def clear_sample_data(session: Session, user: User) -> None:
    """Remove the demo user's run-specific sample data (used by reset)."""
    session.query(CoverageSnapshot).filter_by(user_id=user.id).delete()
    session.query(UserStreetCoverage).filter_by(user_id=user.id).delete()
    session.query(Activity).filter_by(user_id=user.id).delete()
    session.flush()


def seed_sample_data(session: Session, user: User) -> None:
    """Create deterministic sample activities + coverage from real streets."""
    city = session.scalar(select(City).order_by(City.id))
    if city is None:
        print(
            "Snapshot tables are empty (no cities). Restore the snapshot before seeding.",
            file=sys.stderr,
        )
        sys.exit(EXIT_SNAPSHOT_MISSING)

    streets = list(
        session.scalars(
            select(StreetSegment)
            .where(StreetSegment.city_id == city.id)
            .order_by(StreetSegment.id)
            .limit(SAMPLE_STREET_COUNT)
        )
    )
    if not streets:
        print(
            "Snapshot has no street segments for the seeded city. Restore the snapshot first.",
            file=sys.stderr,
        )
        sys.exit(EXIT_SNAPSHOT_MISSING)

    base_date = datetime.datetime(2026, 6, 1, 8, 0, 0)
    streets_per_activity = max(1, len(streets) // SAMPLE_ACTIVITY_COUNT)

    # Sample activities, each tracing a real street's geometry.
    for i in range(SAMPLE_ACTIVITY_COUNT):
        trace_street = streets[i * streets_per_activity % len(streets)]
        session.add(
            Activity(
                user_id=user.id,
                strava_activity_id=DEMO_STRAVA_ATHLETE_ID + 1 + i,
                name=f"Demo Run {i + 1}",
                sport_type="Run",
                start_date=base_date + datetime.timedelta(days=i),
                distance_meters=5000.0 + i * 1000,
                duration_seconds=1800 + i * 300,
                moving_time_seconds=1750 + i * 300,
                gps_trace=trace_street.geometry,
                has_gps=True,
                is_on_street=True,
                import_status="matched",
                city_id=city.id,
            )
        )

    # Coverage: mark the sampled streets as fully traveled.
    for street in streets:
        session.add(
            UserStreetCoverage(
                user_id=user.id,
                street_segment_id=street.id,
                coverage_ratio=1.0,
                is_traveled=True,
                first_traveled_at=base_date,
            )
        )

    # A progress snapshot so the dashboard shows non-zero coverage.
    total_streets = session.query(StreetSegment).filter_by(city_id=city.id).count()
    pct = (len(streets) / total_streets * 100.0) if total_streets else 0.0
    session.add(
        CoverageSnapshot(
            user_id=user.id,
            city_id=city.id,
            neighborhood_id=None,
            coverage_percentage=round(pct, 2),
            total_streets_traveled=len(streets),
            total_streets=total_streets,
            is_milestone=False,
            snapshot_date=base_date.date(),
        )
    )
    session.flush()


def seed(database_url: str) -> int:
    """Full seed: ensure demo user + reset sample data to the known baseline."""
    assert_verification_db(database_url)
    engine = create_db_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        user = ensure_demo_user(session)
        clear_sample_data(session, user)
        seed_sample_data(session, user)
        session.commit()
    print(
        f"Seeded verification DB: demo user {DEMO_DISPLAY_NAME!r} "
        f"(id={user.id}) with sample activities and coverage."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the verification database.")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Verification database URL (defaults to VERIFICATION_DATABASE_URL).",
    )
    args = parser.parse_args(argv)
    return seed(resolve_verification_url(args.database_url))


if __name__ == "__main__":
    raise SystemExit(main())
