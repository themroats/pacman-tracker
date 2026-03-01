"""
Progress service (T066) — daily coverage snapshots and milestone detection.

Functions:
- detect_milestones(old_pct, new_pct) → list of crossed milestone labels
- record_daily_snapshot(db, user_id, city_id, neighborhood_id?) → CoverageSnapshot
- get_city_timeline(db, user_id, city_id) → dict with timeline + milestones
- get_overall_stats(db, user_id) → dict with totals
"""

import datetime

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.city import City
from app.models.coverage import CoverageSnapshot, UserStreetCoverage
from app.models.neighborhood import Neighborhood
from app.models.street import StreetSegment

MILESTONE_LEVELS = [25.0, 50.0, 75.0, 100.0]


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def detect_milestones(old_pct: float, new_pct: float) -> list[str]:
    """Return list of milestone labels crossed when going from old_pct to new_pct.

    Only triggers on *increase* — a decrease never fires milestones.
    """
    if new_pct <= old_pct:
        return []
    return [f"{int(level)}%" for level in MILESTONE_LEVELS if old_pct < level <= new_pct]


# ---------------------------------------------------------------------------
# DB-aware functions
# ---------------------------------------------------------------------------


def record_daily_snapshot(
    db: Session,
    user_id: int,
    city_id: int,
    neighborhood_id: int | None = None,
) -> CoverageSnapshot:
    """Record or update a daily coverage snapshot for user + city (+ optional neighborhood).

    Returns the snapshot object (new or updated).
    """
    today = datetime.date.today()

    # Count total streets in scope
    street_q = db.query(StreetSegment).filter_by(city_id=city_id)
    if neighborhood_id:
        street_q = street_q.filter_by(neighborhood_id=neighborhood_id)
    total_streets = street_q.count()

    # Count traveled streets
    traveled_q = (
        db.query(UserStreetCoverage)
        .filter(UserStreetCoverage.user_id == user_id)
        .filter(UserStreetCoverage.is_traveled.is_(True))
    )
    if neighborhood_id:
        # Join to StreetSegment to filter by neighborhood
        traveled_q = traveled_q.join(
            StreetSegment,
            UserStreetCoverage.street_segment_id == StreetSegment.id,
        ).filter(
            StreetSegment.neighborhood_id == neighborhood_id,
            StreetSegment.city_id == city_id,
        )
    else:
        traveled_q = traveled_q.join(
            StreetSegment,
            UserStreetCoverage.street_segment_id == StreetSegment.id,
        ).filter(StreetSegment.city_id == city_id)
    traveled_count = traveled_q.count()

    pct = (traveled_count / total_streets * 100.0) if total_streets > 0 else 0.0

    # Check for existing snapshot today
    existing = (
        db.query(CoverageSnapshot)
        .filter_by(
            user_id=user_id,
            city_id=city_id,
            neighborhood_id=neighborhood_id,
            snapshot_date=today,
        )
        .first()
    )

    old_pct = existing.coverage_percentage if existing else 0.0

    if existing:
        # Update in place
        existing.coverage_percentage = pct
        existing.total_streets_traveled = traveled_count
        existing.total_streets = total_streets
        # Check if new milestones were crossed
        new_milestones = detect_milestones(old_pct, pct)
        if new_milestones:
            # Mark the highest new milestone
            existing.is_milestone = True
            existing.milestone_label = new_milestones[-1]
        db.flush()
        return existing

    # Create new snapshot
    new_milestones = detect_milestones(old_pct, pct)
    snap = CoverageSnapshot(
        user_id=user_id,
        city_id=city_id,
        neighborhood_id=neighborhood_id,
        coverage_percentage=pct,
        total_streets_traveled=traveled_count,
        total_streets=total_streets,
        is_milestone=bool(new_milestones),
        milestone_label=new_milestones[-1] if new_milestones else None,
        snapshot_date=today,
    )
    db.add(snap)
    db.flush()
    return snap


def get_city_timeline(
    db: Session,
    user_id: int,
    city_id: int,
) -> dict:
    """Get progress timeline and milestones for a user in a city.

    Returns dict matching ProgressResponse schema.
    """
    city = db.query(City).filter_by(id=city_id).first()
    city_name = city.name if city else "Unknown"

    # All snapshots for this user + city (city-wide, neighborhood_id=None)
    snapshots = (
        db.query(CoverageSnapshot)
        .filter_by(user_id=user_id, city_id=city_id, neighborhood_id=None)
        .order_by(CoverageSnapshot.snapshot_date)
        .all()
    )

    timeline = [
        {
            "date": s.snapshot_date.isoformat(),
            "coverage_percentage": s.coverage_percentage,
            "streets_traveled": s.total_streets_traveled,
        }
        for s in snapshots
    ]

    current_pct = snapshots[-1].coverage_percentage if snapshots else 0.0

    # Gather milestones from neighborhood-level snapshots
    milestone_snaps = (
        db.query(CoverageSnapshot)
        .filter_by(user_id=user_id, city_id=city_id, is_milestone=True)
        .filter(CoverageSnapshot.neighborhood_id.isnot(None))
        .order_by(CoverageSnapshot.snapshot_date)
        .all()
    )

    # Build milestone list per target level
    milestones = []
    for level in MILESTONE_LEVELS:
        label = f"{int(level)}%"
        match = next(
            (s for s in milestone_snaps if s.milestone_label == label),
            None,
        )
        if match:
            hood = db.query(Neighborhood).filter_by(id=match.neighborhood_id).first()
            milestones.append(
                {
                    "label": label,
                    "neighborhood_name": hood.name if hood else "Unknown",
                    "reached": True,
                    "date": match.snapshot_date.isoformat(),
                }
            )
        else:
            milestones.append(
                {
                    "label": label,
                    "neighborhood_name": "",
                    "reached": False,
                    "date": None,
                }
            )

    return {
        "city_name": city_name,
        "current_coverage_percentage": round(current_pct, 1),
        "milestones": milestones,
        "timeline": timeline,
    }


def get_overall_stats(db: Session, user_id: int) -> dict:
    """Get overall statistics for a user across all cities.

    Returns dict matching OverallStatsResponse schema.
    """
    # Total activities
    total_activities = db.query(Activity).filter_by(user_id=user_id).count()

    # Total distance
    total_distance = (
        db.query(sa_func.coalesce(sa_func.sum(Activity.distance_meters), 0.0))
        .filter(Activity.user_id == user_id)
        .scalar()
    )

    # Total unique streets traveled
    total_unique_streets = (
        db.query(UserStreetCoverage)
        .filter(
            UserStreetCoverage.user_id == user_id,
            UserStreetCoverage.is_traveled.is_(True),
        )
        .count()
    )

    # Per-city breakdown
    cities = db.query(City).all()
    city_stats = []
    for city in cities:
        total_in_city = (
            db.query(StreetSegment).filter_by(city_id=city.id).count()
        )
        traveled_in_city = (
            db.query(UserStreetCoverage)
            .join(
                StreetSegment,
                UserStreetCoverage.street_segment_id == StreetSegment.id,
            )
            .filter(
                UserStreetCoverage.user_id == user_id,
                UserStreetCoverage.is_traveled.is_(True),
                StreetSegment.city_id == city.id,
            )
            .count()
        )
        pct = (traveled_in_city / total_in_city * 100.0) if total_in_city > 0 else 0.0
        city_stats.append(
            {
                "city_name": city.name,
                "coverage_percentage": round(pct, 1),
                "streets_traveled": traveled_in_city,
                "streets_total": total_in_city,
            }
        )

    return {
        "total_activities": total_activities,
        "total_distance_meters": round(total_distance, 1),
        "total_unique_streets": total_unique_streets,
        "cities": city_stats,
    }
