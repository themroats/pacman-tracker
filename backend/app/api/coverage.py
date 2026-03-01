"""
Coverage API router (T046).

Endpoints:
- GET /coverage/city/{city_id}                     → city summary + neighborhood breakdown
- GET /coverage/neighborhood/{neighborhood_id}     → neighborhood detail + boundary
- GET /coverage/neighborhood/{neighborhood_id}/streets → GeoJSON streets with coverage
- GET /coverage/city/{city_id}/streets             → GeoJSON streets (with filters)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query
from geoalchemy2.shape import to_shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import AppError
from app.models.city import City
from app.models.coverage import UserStreetCoverage
from app.models.neighborhood import Neighborhood
from app.models.street import StreetSegment
from app.models.user import User

router = APIRouter(prefix="/coverage", tags=["coverage"])


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _get_current_user(
    db: Session = Depends(get_db),
    authorization: str = Header(None),
) -> User:
    """Placeholder auth — same pattern as sync.py."""
    if not authorization:
        raise AppError("UNAUTHORIZED", "Missing authorization header", 401)
    # TODO: proper token validation
    user = db.query(User).first()
    if not user:
        raise AppError("UNAUTHORIZED", "User not found", 401)
    return user


def _coverage_stats_for_streets(
    db: Session,
    user_id: int,
    street_ids: list[int],
) -> dict[int, dict]:
    """Return a mapping street_segment_id → {coverage_ratio, is_traveled, first_traveled_at}."""
    if not street_ids:
        return {}
    rows = (
        db.query(UserStreetCoverage)
        .filter(
            UserStreetCoverage.user_id == user_id,
            UserStreetCoverage.street_segment_id.in_(street_ids),
        )
        .all()
    )
    return {
        r.street_segment_id: {
            "coverage_ratio": r.coverage_ratio,
            "is_traveled": r.is_traveled,
            "first_traveled_at": r.first_traveled_at.isoformat() if r.first_traveled_at else None,
        }
        for r in rows
    }


def _neighborhood_coverage(
    db: Session,
    user_id: int,
    neighborhood: Neighborhood,
) -> dict:
    """Build a neighborhood-coverage summary dict."""
    street_ids = [
        s.id
        for s in db.query(StreetSegment.id)
        .filter_by(neighborhood_id=neighborhood.id)
        .all()
    ]
    cov_map = _coverage_stats_for_streets(db, user_id, street_ids)
    traveled = sum(1 for v in cov_map.values() if v["is_traveled"])
    total = neighborhood.total_street_segments or len(street_ids)
    pct = (traveled / total * 100) if total else 0.0

    # Compute distance traveled
    traveled_length = 0.0
    for s in (
        db.query(StreetSegment)
        .filter(StreetSegment.id.in_([sid for sid, v in cov_map.items() if v["is_traveled"]]))
        .all()
    ):
        traveled_length += s.length_meters

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
    streets: list[StreetSegment],
    status_filter: str | None = None,
) -> dict:
    """Build a GeoJSON FeatureCollection from streets + coverage data."""
    street_ids = [s.id for s in streets]
    cov_map = _coverage_stats_for_streets(db, user_id, street_ids)

    features = []
    for s in streets:
        cov = cov_map.get(s.id, {"coverage_ratio": 0.0, "is_traveled": False, "first_traveled_at": None})

        # Apply status filter
        if status_filter == "traveled" and not cov["is_traveled"]:
            continue
        if status_filter == "untraveled" and cov["is_traveled"]:
            continue

        try:
            geom_shape = to_shape(s.geometry)
            geom_json = {
                "type": "LineString",
                "coordinates": list(geom_shape.coords),
            }
        except Exception:
            continue

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": s.id,
                    "name": s.name,
                    "highway_type": s.highway_type,
                    "length_meters": s.length_meters,
                    "is_traveled": cov["is_traveled"],
                    "coverage_ratio": round(cov["coverage_ratio"], 2),
                    "first_traveled_at": cov["first_traveled_at"],
                },
                "geometry": geom_json,
            }
        )

    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/city/{city_id}")
async def city_coverage(
    city_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """City-wide coverage summary with per-neighborhood breakdown."""
    city = db.query(City).get(city_id)
    if not city:
        raise AppError("NOT_FOUND", f"City {city_id} not found", 404)

    neighborhoods = (
        db.query(Neighborhood).filter_by(city_id=city.id).order_by(Neighborhood.name).all()
    )

    n_summaries = [_neighborhood_coverage(db, user.id, n) for n in neighborhoods]

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
async def neighborhood_detail(
    neighborhood_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """Detailed coverage for a single neighborhood, including boundary."""
    n = db.query(Neighborhood).get(neighborhood_id)
    if not n:
        raise AppError("NOT_FOUND", f"Neighborhood {neighborhood_id} not found", 404)

    city = db.query(City).get(n.city_id)
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
async def neighborhood_streets(
    neighborhood_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """Street segments for a neighborhood with coverage status."""
    n = db.query(Neighborhood).get(neighborhood_id)
    if not n:
        raise AppError("NOT_FOUND", f"Neighborhood {neighborhood_id} not found", 404)

    streets = (
        db.query(StreetSegment)
        .filter_by(neighborhood_id=neighborhood_id)
        .all()
    )
    return _streets_geojson(db, user.id, streets)


@router.get("/city/{city_id}/streets")
async def city_streets(
    city_id: int,
    neighborhood_id: int | None = Query(None),
    status: str | None = Query(None),
    bbox: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """All street segments for a city with coverage status (GeoJSON)."""
    city = db.query(City).get(city_id)
    if not city:
        raise AppError("NOT_FOUND", f"City {city_id} not found", 404)

    query = db.query(StreetSegment).filter_by(city_id=city_id)
    if neighborhood_id:
        query = query.filter_by(neighborhood_id=neighborhood_id)

    # bbox filter: "minLng,minLat,maxLng,maxLat"
    if bbox:
        try:
            parts = [float(x) for x in bbox.split(",")]
            if len(parts) == 4:
                min_lng, min_lat, max_lng, max_lat = parts
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
        except (ValueError, IndexError):
            pass  # ignore malformed bbox

    streets = query.all()
    return _streets_geojson(db, user.id, streets, status_filter=status)
