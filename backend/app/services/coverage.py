"""
GPS-to-street matching service (T044 + T099).

Core algorithms:
- Buffer GPS trace by 15 m, intersect with street segments, compute coverage_ratio.
- 80 % threshold determines ``is_traveled``.
- < 20 % overall street match → activity classified as off-road (``is_on_street=False``).
- Persists / updates ``UserStreetCoverage`` records, taking the *max* ratio
  when multiple activities contribute to the same street.
"""

from __future__ import annotations

import datetime
import math
from typing import Any

from shapely.geometry import LineString
from shapely.ops import transform
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COVERAGE_THRESHOLD = 0.80  # ≥ 80 % → traveled
ON_STREET_THRESHOLD = 0.20  # < 20 % overall → off-road
DEFAULT_BUFFER_METERS = 15

# Rough degree→metre factor at mid-latitudes (good enough for buffering)
_DEG_TO_M_LAT = 111_320.0  # metres per degree latitude (constant-ish)


# ---------------------------------------------------------------------------
# Pure geometry helpers (no DB)
# ---------------------------------------------------------------------------


def _approx_buffer_degrees(meters: float, latitude: float = 47.6) -> float:
    """Convert a buffer distance in metres to approximate degrees.

    Uses a simple cosine correction that is adequate for ≤50 m buffers
    at the latitudes of the five launch cities (40–48 °N).
    """
    m_per_deg_lng = _DEG_TO_M_LAT * math.cos(math.radians(latitude))
    avg_m_per_deg = (_DEG_TO_M_LAT + m_per_deg_lng) / 2
    return meters / avg_m_per_deg


def compute_coverage_ratio(
    street: LineString,
    gps_trace: LineString,
    buffer_meters: float = DEFAULT_BUFFER_METERS,
) -> float:
    """Return the fraction of *street* covered by *gps_trace* (0.0 – 1.0).

    Algorithm:
    1. Buffer the GPS trace by ``buffer_meters`` (converted to approximate degrees).
    2. Intersect the street geometry with the buffer.
    3. Ratio = length(intersection) / length(street).
    """
    if street.is_empty or gps_trace.is_empty:
        return 0.0

    street_len = street.length
    if street_len == 0:
        return 0.0

    # Approximate latitude from the street's centroid
    lat = street.centroid.y
    buf_deg = _approx_buffer_degrees(buffer_meters, lat)

    gps_buffer = gps_trace.buffer(buf_deg)
    intersection = street.intersection(gps_buffer)

    ratio = intersection.length / street_len
    return min(ratio, 1.0)


def classify_activity_on_street(overall_ratio: float) -> bool:
    """Return ``True`` if the activity is on-street (≥ 20 % match)."""
    return overall_ratio >= ON_STREET_THRESHOLD


def match_activity_to_streets(
    gps_trace: LineString,
    street_geometries: list[tuple[int, LineString, float]],
    buffer_meters: float = DEFAULT_BUFFER_METERS,
) -> list[dict[str, Any]]:
    """Match a GPS trace against a list of candidate streets.

    Parameters
    ----------
    gps_trace:
        The activity's GPS trace as a Shapely LineString.
    street_geometries:
        List of ``(street_segment_id, shapely_geom, length_meters)``.
    buffer_meters:
        Buffer distance in metres.

    Returns
    -------
    List of dicts with keys: ``street_segment_id``, ``coverage_ratio``, ``is_traveled``.
    """
    if not street_geometries:
        return []

    results: list[dict[str, Any]] = []
    for seg_id, street_geom, length_m in street_geometries:
        ratio = compute_coverage_ratio(street_geom, gps_trace, buffer_meters)
        if ratio > 0.0:
            results.append(
                {
                    "street_segment_id": seg_id,
                    "coverage_ratio": ratio,
                    "is_traveled": ratio >= COVERAGE_THRESHOLD,
                }
            )
    return results


# ---------------------------------------------------------------------------
# DB-aware service functions
# ---------------------------------------------------------------------------


def run_coverage_matching(
    db: Session,
    user_id: int,
    activity_id: int,
    gps_trace: LineString,
    city_id: int | None,
) -> float:
    """Match a single activity's GPS trace against streets and persist coverage.

    Returns the overall street-match ratio for the activity (for on-street
    classification).
    """
    from geoalchemy2.shape import to_shape

    from app.models.coverage import UserStreetCoverage
    from app.models.street import StreetSegment

    # Fetch candidate streets in the same city (or all if city unknown)
    query = db.query(StreetSegment)
    if city_id:
        query = query.filter(StreetSegment.city_id == city_id)

    # Spatial pre-filter: streets whose bounding box intersects the gps trace bbox
    # For SpatiaLite, we rely on the R-tree index implicitly; explicit bbox filter here:
    bounds = gps_trace.bounds  # (minx, miny, maxx, maxy)
    pad = _approx_buffer_degrees(DEFAULT_BUFFER_METERS * 2)
    # We'll just fetch all streets in the city for now; spatial indexing will help in prod.
    streets = query.all()

    # Convert DB geometries to Shapely
    street_geoms: list[tuple[int, LineString, float]] = []
    for s in streets:
        try:
            shape = to_shape(s.geometry)
            if not shape.is_empty:
                street_geoms.append((s.id, shape, s.length_meters))
        except Exception:
            continue

    if not street_geoms:
        return 0.0

    # Run matching
    results = match_activity_to_streets(gps_trace, street_geoms, DEFAULT_BUFFER_METERS)

    # Compute overall ratio: sum of covered-street-length / total nearby street length
    total_length = sum(l for _, _, l in street_geoms)
    covered_length = 0.0
    for r in results:
        # Find the matching street's length
        for seg_id, _, length_m in street_geoms:
            if seg_id == r["street_segment_id"]:
                covered_length += r["coverage_ratio"] * length_m
                break
    overall_ratio = covered_length / total_length if total_length > 0 else 0.0

    # Persist / update UserStreetCoverage records
    now = datetime.datetime.now(datetime.UTC)
    for r in results:
        existing = (
            db.query(UserStreetCoverage)
            .filter_by(user_id=user_id, street_segment_id=r["street_segment_id"])
            .first()
        )
        if existing:
            # Take max coverage ratio (multiple activities accumulate)
            new_ratio = max(existing.coverage_ratio, r["coverage_ratio"])
            existing.coverage_ratio = new_ratio
            existing.is_traveled = new_ratio >= COVERAGE_THRESHOLD
            existing.last_activity_id = activity_id
            if existing.is_traveled and existing.first_traveled_at is None:
                existing.first_traveled_at = now
        else:
            cov = UserStreetCoverage(
                user_id=user_id,
                street_segment_id=r["street_segment_id"],
                coverage_ratio=r["coverage_ratio"],
                is_traveled=r["coverage_ratio"] >= COVERAGE_THRESHOLD,
                last_activity_id=activity_id,
                first_traveled_at=now if r["coverage_ratio"] >= COVERAGE_THRESHOLD else None,
            )
            db.add(cov)

    db.flush()

    # Record a daily progress snapshot for the city (T067)
    if city_id:
        try:
            from app.services.progress import record_daily_snapshot

            record_daily_snapshot(db, user_id=user_id, city_id=city_id)
        except Exception:
            # Non-critical — don't fail coverage matching if snapshot fails
            pass

    return overall_ratio
