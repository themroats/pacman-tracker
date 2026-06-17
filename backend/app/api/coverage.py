"""
Coverage API router.

Endpoints:
- GET /coverage/city/{city_id}                     → city summary + neighborhood breakdown
- GET /coverage/neighborhood/{neighborhood_id}     → neighborhood detail + boundary
- GET /coverage/neighborhood/{neighborhood_id}/streets → GeoJSON streets with coverage
- GET /coverage/city/{city_id}/streets             → GeoJSON streets (with filters)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Path, Query
from geoalchemy2.shape import to_shape
from sqlalchemy import func, and_, case, literal_column
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.models.city import City
from app.models.coverage import UserStreetCoverage
from app.models.neighborhood import Neighborhood
from app.models.street import StreetSegment
from app.models.user import User

router = APIRouter(prefix="/coverage", tags=["coverage"])

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


from app.api.deps import get_current_user as _get_current_user


def _neighborhood_coverage(
    db: Session,
    user_id: int,
    neighborhood: Neighborhood,
) -> dict:
    """Build a neighborhood-coverage summary dict using efficient SQL."""
    # Single query: count total streets and traveled streets via LEFT JOIN
    row = (
        db.query(
            func.count(StreetSegment.id).label("total"),
            func.count(UserStreetCoverage.id).label("traveled"),
            func.coalesce(
                func.sum(
                    case(
                        (UserStreetCoverage.is_traveled == True, StreetSegment.length_meters),
                        else_=literal_column("0"),
                    )
                ),
                0,
            ).label("traveled_length"),
        )
        .outerjoin(
            UserStreetCoverage,
            and_(
                UserStreetCoverage.street_segment_id == StreetSegment.id,
                UserStreetCoverage.user_id == user_id,
                UserStreetCoverage.is_traveled == True,
            ),
        )
        .filter(StreetSegment.neighborhood_id == neighborhood.id)
        .one()
    )

    total = neighborhood.total_street_segments or row.total
    traveled = row.traveled
    pct = (traveled / total * 100) if total else 0.0
    traveled_length = float(row.traveled_length)

    return {
        "id": neighborhood.id,
        "name": neighborhood.name,
        "coverage_percentage": round(pct, 1),
        "streets_traveled": traveled,
        "streets_total": total,
        "distance_traveled_m": round(traveled_length, 1),
        "distance_total_m": round(neighborhood.total_street_length_m, 1),
    }


def _streets_geojson(
    db: Session,
    user_id: int,
    street_query,
    status_filter: str | None = None,
) -> dict:
    """Build a GeoJSON FeatureCollection from a street query + coverage data.

    Accepts a SQLAlchemy query (not a materialised list) so that the database
    does the heavy lifting via a JOIN instead of a giant ``IN(...)`` clause.
    """
    # LEFT JOIN coverage onto the street query
    rows = (
        street_query
        .outerjoin(
            UserStreetCoverage,
            and_(
                UserStreetCoverage.street_segment_id == StreetSegment.id,
                UserStreetCoverage.user_id == user_id,
            ),
        )
        .add_columns(
            UserStreetCoverage.coverage_ratio,
            UserStreetCoverage.is_traveled,
            UserStreetCoverage.first_traveled_at,
        )
        .all()
    )

    features = []
    for row in rows:
        # Unpack: first element is StreetSegment, rest are coverage columns
        s = row[0]
        cov_ratio = row[1] or 0.0
        is_traveled = bool(row[2]) if row[2] is not None else False
        first_traveled = row[3].isoformat() if row[3] else None

        # Apply status filter
        if status_filter == "traveled" and not is_traveled:
            continue
        if status_filter == "untraveled" and is_traveled:
            continue

        try:
            geom_shape = to_shape(s.geometry)
            geom_json = {
                "type": "LineString",
                "coordinates": list(geom_shape.coords),
            }
        except Exception:
            logger.warning("Failed to serialize geometry for street %d", s.id)
            continue

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": s.id,
                    "name": s.name,
                    "highway_type": s.highway_type,
                    "length_meters": s.length_meters,
                    "is_traveled": is_traveled,
                    "coverage_ratio": round(cov_ratio, 2),
                    "first_traveled_at": first_traveled,
                },
                "geometry": geom_json,
            }
        )

    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/city/{city_id}")
def city_coverage(
    city_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """City-wide coverage summary with per-neighborhood breakdown."""
    city = db.get(City, city_id)
    if not city:
        raise AppError("NOT_FOUND", f"City {city_id} not found", 404)

    neighborhoods = (
        db.query(Neighborhood).filter_by(city_id=city.id).order_by(Neighborhood.name).all()
    )

    # Batched coverage query — single GROUP BY instead of N+1
    neighborhood_ids = [n.id for n in neighborhoods]
    coverage_rows = {}
    if neighborhood_ids:
        rows = (
            db.query(
                StreetSegment.neighborhood_id,
                func.count(StreetSegment.id).label("total"),
                func.count(UserStreetCoverage.id).label("traveled"),
                func.coalesce(
                    func.sum(
                        case(
                            (UserStreetCoverage.is_traveled == True, StreetSegment.length_meters),
                            else_=literal_column("0"),
                        )
                    ),
                    0,
                ).label("traveled_length"),
            )
            .outerjoin(
                UserStreetCoverage,
                and_(
                    UserStreetCoverage.street_segment_id == StreetSegment.id,
                    UserStreetCoverage.user_id == user.id,
                    UserStreetCoverage.is_traveled == True,
                ),
            )
            .filter(StreetSegment.neighborhood_id.in_(neighborhood_ids))
            .group_by(StreetSegment.neighborhood_id)
            .all()
        )
        for row in rows:
            coverage_rows[row[0]] = row

    n_summaries = []
    for n in neighborhoods:
        row = coverage_rows.get(n.id)
        if row:
            total = n.total_street_segments or row.total
            traveled = row.traveled
            traveled_length = float(row.traveled_length)
        else:
            total = n.total_street_segments or 0
            traveled = 0
            traveled_length = 0.0
        pct = (traveled / total * 100) if total else 0.0
        n_summaries.append({
            "id": n.id,
            "name": n.name,
            "coverage_percentage": round(pct, 1),
            "streets_traveled": traveled,
            "streets_total": total,
            "distance_traveled_m": round(traveled_length, 1),
            "distance_total_m": round(n.total_street_length_m, 1),
        })

    total_streets = city.total_street_segments or sum(ns["streets_total"] for ns in n_summaries)
    traveled_streets = sum(ns["streets_traveled"] for ns in n_summaries)
    total_dist = city.total_street_length_m or sum(ns["distance_total_m"] for ns in n_summaries)
    traveled_dist = sum(ns["distance_traveled_m"] for ns in n_summaries)
    pct = (traveled_streets / total_streets * 100) if total_streets else 0.0

    return {
        "city": {
            "id": city.id,
            "name": city.name,
            "coverage_percentage": round(pct, 1),
            "streets_traveled": traveled_streets,
            "streets_total": total_streets,
            "distance_traveled_m": round(traveled_dist, 1),
            "distance_total_m": round(total_dist, 1),
        },
        "neighborhoods": n_summaries,
    }


@router.get("/neighborhood/{neighborhood_id}")
def neighborhood_detail(
    neighborhood_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """Detailed coverage for a single neighborhood, including boundary."""
    n = db.get(Neighborhood, neighborhood_id)
    if not n:
        raise AppError("NOT_FOUND", f"Neighborhood {neighborhood_id} not found", 404)

    city = db.get(City, n.city_id)
    summary = _neighborhood_coverage(db, user.id, n)

    try:
        boundary_shape = to_shape(n.boundary)
        # MultiPolygon → take first polygon for GeoJSON representation
        if boundary_shape.geom_type == "MultiPolygon":
            poly = list(boundary_shape.geoms)[0]
            boundary_json = {
                "type": "Polygon",
                "coordinates": [list(poly.exterior.coords)],
            }
        else:
            boundary_json = {
                "type": boundary_shape.geom_type,
                "coordinates": list(boundary_shape.exterior.coords) if hasattr(boundary_shape, "exterior") else [],
            }
    except Exception:
        boundary_json = {}

    return {
        "neighborhood": {
            "id": n.id,
            "name": n.name,
            "city_name": city.name if city else "",
            "coverage_percentage": summary["coverage_percentage"],
            "streets_traveled": summary["streets_traveled"],
            "streets_total": summary["streets_total"],
        },
        "boundary": boundary_json,
    }


@router.get("/neighborhood/{neighborhood_id}/streets")
def neighborhood_streets(
    neighborhood_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """Street segments for a neighborhood with coverage status."""
    n = db.get(Neighborhood, neighborhood_id)
    if not n:
        raise AppError("NOT_FOUND", f"Neighborhood {neighborhood_id} not found", 404)

    street_query = (
        db.query(StreetSegment)
        .filter_by(neighborhood_id=neighborhood_id)
    )
    return _streets_geojson(db, user.id, street_query)


@router.get("/city/{city_id}/streets")
def city_streets(
    city_id: int = Path(gt=0),
    neighborhood_id: int | None = Query(None),
    status: str | None = Query(None),
    bbox: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """All street segments for a city with coverage status (GeoJSON)."""
    city = db.get(City, city_id)
    if not city:
        raise AppError("NOT_FOUND", f"City {city_id} not found", 404)

    query = db.query(StreetSegment).filter_by(city_id=city_id)
    if neighborhood_id:
        query = query.filter_by(neighborhood_id=neighborhood_id)
    elif not bbox:
        # Without a neighborhood or bbox filter, returning 300k+ streets as
        # GeoJSON would be too large.  Return an empty collection so the
        # frontend can prompt the user to select a neighborhood first.
        return {"type": "FeatureCollection", "features": []}

    # bbox filter: "minLng,minLat,maxLng,maxLat"
    if bbox:
        try:
            parts = [float(x) for x in bbox.split(",")]
        except ValueError:
            raise AppError("VALIDATION_ERROR", "Invalid bbox: values must be numbers", 400)

        if len(parts) != 4:
            raise AppError("VALIDATION_ERROR", "Invalid bbox: expected 4 values (minLng,minLat,maxLng,maxLat)", 400)

        min_lng, min_lat, max_lng, max_lat = parts

        if not (-180 <= min_lng <= 180 and -180 <= max_lng <= 180):
            raise AppError("VALIDATION_ERROR", "Invalid bbox: longitude must be between -180 and 180", 400)
        if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            raise AppError("VALIDATION_ERROR", "Invalid bbox: latitude must be between -90 and 90", 400)

        from geoalchemy2 import functions as gfunc

        bbox_wkt = (
            f"POLYGON(({min_lng} {min_lat}, {max_lng} {min_lat}, "
            f"{max_lng} {max_lat}, {min_lng} {max_lat}, {min_lng} {min_lat}))"
        )
        query = query.filter(
            gfunc.ST_Intersects(
                StreetSegment.geometry,
                gfunc.ST_GeomFromText(bbox_wkt, 4326),
            )
        )

    return _streets_geojson(db, user.id, query, status_filter=status)
