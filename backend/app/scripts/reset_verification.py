"""
Fast data-only reset for the verification database (feature 008).

Restores the demo baseline between warm verification runs WITHOUT re-restoring the
frozen street snapshot:

* truncates run-accumulated tables (route suggestions, plans, goals),
* clears + reseeds the demo user's sample activities and coverage,
* preserves the snapshot tables (cities / neighborhoods / street_segments),
* clears in-process routing/sync caches in the invoking CLI process (NOT the
  already-running backend; see the note on ``reset_runtime_caches``).

Guarded so it can ONLY target the verification database.

Usage::

    python -m app.scripts.reset_verification --database-url postgresql://.../pacman_verify
"""

from __future__ import annotations

import argparse

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.database import create_db_engine
from app.models.user import User
from app.scripts._verify_guard import assert_verification_db, resolve_verification_url
from app.scripts.seed_verification import (
    DEMO_STRAVA_ATHLETE_ID,
    clear_sample_data,
    ensure_demo_user,
    seed_sample_data,
)

# Run-accumulated tables truncated on every reset (child -> parent order).
# Safe to truncate fully: the verification DB has exactly one (demo) user.
RUN_ACCUMULATED_TABLES = [
    "route_suggestion_segments",
    "route_suggestions",
    "coverage_plan_routes",
    "coverage_plans",
    "coverage_goals",
]


def reset_runtime_caches() -> None:
    """
    Clear in-process state that would leak between warm runs (FR-018).

    NOTE: This affects the *current* Python process. When run as a standalone
    CLI it clears this process's globals; the live backend process clears its
    own state on restart (verify-clean) or via the OSRM cache TTL / force-check.
    """
    from app.services import routing, sync_runtime

    routing._osrm_available = None
    sync_runtime.clear_active_sync_jobs()


def reset_data(session: Session, user: User) -> None:
    """Truncate run-accumulated data and reseed the demo baseline."""
    clear_sample_data(session, user)
    for table in RUN_ACCUMULATED_TABLES:
        session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
    seed_sample_data(session, user)
    session.flush()


def reset(database_url: str) -> int:
    """Guarded entrypoint: fast data-only reset of the verification DB."""
    assert_verification_db(database_url)
    engine = create_db_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        user = session.scalar(select(User).where(User.strava_athlete_id == DEMO_STRAVA_ATHLETE_ID))
        if user is None:
            # Baseline missing — establish it so the loop can proceed.
            user = ensure_demo_user(session)
        reset_data(session, user)
        session.commit()
    reset_runtime_caches()
    print("Verification DB reset to baseline (snapshot preserved).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fast data-only reset of the verification DB.")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Verification database URL (defaults to VERIFICATION_DATABASE_URL).",
    )
    args = parser.parse_args(argv)
    return reset(resolve_verification_url(args.database_url))


if __name__ == "__main__":
    raise SystemExit(main())
