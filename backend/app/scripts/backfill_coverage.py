"""
Backfill coverage data for all imported activities.

Runs GPS-to-street matching for every activity that has a gps_trace
geometry but hasn't been matched yet.  Also assigns city_id to activities
based on spatial containment.

Usage: python -m app.scripts.backfill_coverage [--force]
"""

from __future__ import annotations

import sys
import time

from geoalchemy2.shape import to_shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import create_db_engine, get_session_factory
from app.models.activity import Activity
from app.models.city import City
from app.models.coverage import UserStreetCoverage
from app.services.coverage import run_coverage_matching, classify_activity_on_street


def _assign_city_ids(session: Session) -> int:
    """Assign city_id to activities based on GPS trace location."""
    from geoalchemy2 import functions as gfunc

    cities = session.query(City).all()
    if not cities:
        return 0

    unassigned = (
        session.query(Activity)
        .filter(Activity.gps_trace.isnot(None), Activity.city_id.is_(None))
        .all()
    )
    if not unassigned:
        return 0

    print(f"  Assigning city_id to {len(unassigned)} activities...")
    assigned = 0

    # Build city boundary shapes once
    city_shapes = []
    for city in cities:
        try:
            shape = to_shape(city.boundary)
            city_shapes.append((city.id, shape))
        except Exception:
            continue

    for activity in unassigned:
        try:
            trace = to_shape(activity.gps_trace)
            # Use the trace's centroid to determine the city
            centroid = trace.centroid
            for city_id, boundary in city_shapes:
                if boundary.contains(centroid):
                    activity.city_id = city_id
                    assigned += 1
                    break
        except Exception:
            continue

    session.flush()
    print(f"  Assigned city_id to {assigned} activities")
    return assigned


def backfill(force: bool = False) -> None:
    """Run coverage matching for all activities with GPS data."""
    factory = get_session_factory()
    session = factory()

    try:
        # Step 1: Assign city_id to activities that don't have one
        _assign_city_ids(session)

        # Step 2: Only process activities with a city_id (in a supported city)
        query = session.query(Activity).filter(
            Activity.gps_trace.isnot(None),
            Activity.city_id.isnot(None),
        )
        if not force:
            # Only match activities not yet matched
            query = query.filter(Activity.import_status != "matched")

        activities = query.order_by(Activity.start_date).all()
        total = len(activities)
        if total == 0:
            print("No activities to process.")
            return

        print(f"Processing {total} activities...")

        matched = 0
        errors = 0
        start_time = time.time()

        for i, activity in enumerate(activities, 1):
            try:
                # Convert DB geometry to Shapely
                gps_trace = to_shape(activity.gps_trace)
                if gps_trace.is_empty or len(gps_trace.coords) < 2:
                    print(f"  [{i}/{total}] {activity.name}: skipping (empty/short trace)")
                    continue

                # Run coverage matching
                overall_ratio = run_coverage_matching(
                    db=session,
                    user_id=activity.user_id,
                    activity_id=activity.id,
                    gps_trace=gps_trace,
                    city_id=activity.city_id,
                )

                # Classify on-street/off-road
                is_on_street = classify_activity_on_street(overall_ratio)
                activity.is_on_street = is_on_street
                activity.import_status = "matched"
                matched += 1

                # Commit in batches of 10
                if i % 10 == 0:
                    session.commit()
                    elapsed = time.time() - start_time
                    rate = i / elapsed if elapsed > 0 else 0
                    print(
                        f"  [{i}/{total}] {activity.name}: "
                        f"ratio={overall_ratio:.2%}, on_street={is_on_street} "
                        f"({rate:.1f} activities/s)"
                    )

            except Exception as e:
                errors += 1
                print(f"  [{i}/{total}] {activity.name}: ERROR - {e}")
                session.rollback()

        # Final commit
        session.commit()

        elapsed = time.time() - start_time
        print(f"\nDone in {elapsed:.1f}s")
        print(f"  Matched: {matched}")
        print(f"  Errors: {errors}")
        print(f"  Skipped: {total - matched - errors}")

        # Summary stats
        cov_count = session.query(UserStreetCoverage).count()
        traveled = session.query(UserStreetCoverage).filter_by(is_traveled=True).count()
        print(f"\nCoverage records: {cov_count} total, {traveled} traveled")

    except Exception as e:
        session.rollback()
        print(f"\nFatal error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    force = "--force" in sys.argv
    if force:
        print("Force mode: re-matching all activities (including previously matched)")
    backfill(force=force)
