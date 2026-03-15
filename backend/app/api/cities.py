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
from app.main import AppError
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


def _serialize_neighborhood_boundary(db: Session, user_id: int, neighborhood: Neighborhood) -> dict:
    from app.api.coverage import _neighborhood_coverage

    cov = _neighborhood_coverage(db, user_id, neighborhood)

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
            "coverage_percentage": cov["coverage_percentage"],
        },
        "geometry": geom_json,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_cities(db: Session = Depends(get_db)):
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
async def list_neighborhoods(
    city_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """List neighborhoods for a city, with coverage percentages."""
    from app.api.coverage import _neighborhood_coverage

    city = db.get(City, city_id)
    if not city:
        raise AppError("NOT_FOUND", f"City {city_id} not found", 404)

    neighborhoods = (
        db.query(Neighborhood)
        .filter_by(city_id=city_id)
        .order_by(Neighborhood.name)
        .all()
    )

    result = []
    for n in neighborhoods:
        cov = _neighborhood_coverage(db, user.id, n)
        result.append(
            {
                "id": cov["id"],
                "name": cov["name"],
                "total_street_segments": cov["streets_total"],
                "coverage_percentage": cov["coverage_percentage"],
            }
        )

    return {"neighborhoods": result}


@router.get("/{city_id}/neighborhoods/{neighborhood_id}/boundary")
async def neighborhood_boundary(
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
async def neighborhood_boundaries(
    city_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """Neighborhood boundaries for a city as a GeoJSON FeatureCollection."""
    city = db.get(City, city_id)
    if not city:
        raise AppError("NOT_FOUND", f"City {city_id} not found", 404)

    neighborhoods = (
        db.query(Neighborhood)
        .filter_by(city_id=city_id)
        .order_by(Neighborhood.name)
        .all()
    )

    return {
        "type": "FeatureCollection",
        "features": [
            _serialize_neighborhood_boundary(db, user.id, neighborhood)
            for neighborhood in neighborhoods
        ],
    }
