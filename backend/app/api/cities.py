"""
Cities API router (T047).

Endpoints:
- GET /cities                                            → list all supported cities
- GET /cities/{city_id}/neighborhoods                    → list neighborhoods
- GET /cities/{city_id}/neighborhoods/boundaries         → GeoJSON boundaries for all neighborhoods
- GET /cities/{city_id}/neighborhoods/{neighborhood_id}/boundary → GeoJSON boundary
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Path
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.models.city import City
from app.models.neighborhood import Neighborhood
from app.models.user import User
from app.services.city_bootstrap import (
    ensure_city_bootstrap_started,
    get_city_bootstrap_state,
)

router = APIRouter(prefix="/cities", tags=["cities"])

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


from app.api.deps import get_current_user as _get_current_user


def _serialize_neighborhood_boundary(db: Session, user_id: int, neighborhood: Neighborhood, coverage_pct: float | None = None) -> dict:
    if coverage_pct is None:
        from app.api.coverage import _neighborhood_coverage
        cov = _neighborhood_coverage(db, user_id, neighborhood)
        coverage_pct = cov["coverage_percentage"]

    try:
        boundary_shape = to_shape(neighborhood.boundary)
        if boundary_shape.geom_type == "MultiPolygon":
            poly = list(boundary_shape.geoms)[0]
            geom_json = {
                "type": "Polygon",
                "coordinates": [list(poly.exterior.coords)],
            }
        else:
            geom_json = {
                "type": boundary_shape.geom_type,
                "coordinates": (
                    list(boundary_shape.exterior.coords)
                    if hasattr(boundary_shape, "exterior")
                    else []
                ),
            }
    except Exception:
        logger.warning("Failed to serialize boundary for neighborhood %d", neighborhood.id)
        geom_json = {}

    return {
        "type": "Feature",
        "properties": {
            "id": neighborhood.id,
            "name": neighborhood.name,
            "coverage_percentage": coverage_pct,
        },
        "geometry": geom_json,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
def list_cities(db: Session = Depends(get_db)):
    """List all supported cities."""
    cities = db.query(City).order_by(City.name).all()
    bootstrap_state = (
        get_city_bootstrap_state() if cities else ensure_city_bootstrap_started()
    )
    return {
        "cities": [
            {
                "id": c.id,
                "name": c.name,
                "state": c.state,
                "total_street_segments": c.total_street_segments,
                "total_neighborhoods": (
                    db.query(Neighborhood).filter_by(city_id=c.id).count()
                ),
            }
            for c in cities
        ],
        "bootstrap_status": bootstrap_state["status"],
        "bootstrap_error": bootstrap_state["error"],
    }


@router.get("/{city_id}/neighborhoods")
def list_neighborhoods(
    city_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """List neighborhoods for a city, with coverage percentages."""
    from sqlalchemy import and_, case, func, literal_column

    from app.models.coverage import UserStreetCoverage
    from app.models.street import StreetSegment

    city = db.get(City, city_id)
    if not city:
        raise AppError("NOT_FOUND", f"City {city_id} not found", 404)

    neighborhoods = (
        db.query(Neighborhood)
        .filter_by(city_id=city_id)
        .order_by(Neighborhood.name)
        .all()
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

    result = []
    for n in neighborhoods:
        row = coverage_rows.get(n.id)
        total = n.total_street_segments or (row.total if row else 0)
        traveled = row.traveled if row else 0
        pct = (traveled / total * 100) if total else 0.0
        result.append(
            {
                "id": n.id,
                "name": n.name,
                "total_street_segments": total,
                "coverage_percentage": round(pct, 1),
            }
        )

    return {"neighborhoods": result}


@router.get("/{city_id}/neighborhoods/{neighborhood_id}/boundary")
def neighborhood_boundary(
    city_id: int = Path(gt=0),
    neighborhood_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """Neighborhood boundary as a GeoJSON Feature."""
    n = db.query(Neighborhood).filter_by(id=neighborhood_id, city_id=city_id).first()
    if not n:
        raise AppError(
            "NOT_FOUND",
            f"Neighborhood {neighborhood_id} not found in city {city_id}",
            404,
        )

    return _serialize_neighborhood_boundary(db, user.id, n)


@router.get("/{city_id}/neighborhoods/boundaries")
def neighborhood_boundaries(
    city_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """Neighborhood boundaries for a city as a GeoJSON FeatureCollection."""
    from sqlalchemy import and_, func

    from app.models.coverage import UserStreetCoverage
    from app.models.street import StreetSegment

    city = db.get(City, city_id)
    if not city:
        raise AppError("NOT_FOUND", f"City {city_id} not found", 404)

    neighborhoods = (
        db.query(Neighborhood)
        .filter_by(city_id=city_id)
        .order_by(Neighborhood.name)
        .all()
    )

    # Batched coverage for all neighborhoods
    neighborhood_ids = [n.id for n in neighborhoods]
    coverage_map: dict[int, float] = {}
    if neighborhood_ids:
        rows = (
            db.query(
                StreetSegment.neighborhood_id,
                func.count(StreetSegment.id).label("total"),
                func.count(UserStreetCoverage.id).label("traveled"),
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
            total = row.total
            pct = (row.traveled / total * 100) if total else 0.0
            coverage_map[row[0]] = round(pct, 1)

    return {
        "type": "FeatureCollection",
        "features": [
            _serialize_neighborhood_boundary(
                db, user.id, n, coverage_pct=coverage_map.get(n.id, 0.0)
            )
            for n in neighborhoods
        ],
    }
