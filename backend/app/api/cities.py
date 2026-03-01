"""
Cities API router (T047).

Endpoints:
- GET /cities                                            → list all supported cities
- GET /cities/{city_id}/neighborhoods                    → list neighborhoods
- GET /cities/{city_id}/neighborhoods/{neighborhood_id}/boundary → GeoJSON boundary
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import AppError
from app.models.city import City
from app.models.coverage import UserStreetCoverage
from app.models.neighborhood import Neighborhood
from app.models.street import StreetSegment
from app.models.user import User

router = APIRouter(prefix="/cities", tags=["cities"])


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _get_current_user(
    db: Session = Depends(get_db),
    authorization: str = Header(None),
) -> User:
    """Placeholder auth."""
    if not authorization:
        raise AppError("UNAUTHORIZED", "Missing authorization header", 401)
    user = db.query(User).first()
    if not user:
        raise AppError("UNAUTHORIZED", "User not found", 401)
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_cities(db: Session = Depends(get_db)):
    """List all supported cities."""
    cities = db.query(City).order_by(City.name).all()
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
        ]
    }


@router.get("/{city_id}/neighborhoods")
async def list_neighborhoods(
    city_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """List neighborhoods for a city, with coverage percentages."""
    city = db.query(City).get(city_id)
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
        # Count traveled streets
        street_ids = [
            s.id
            for s in db.query(StreetSegment.id).filter_by(neighborhood_id=n.id).all()
        ]
        traveled = 0
        if street_ids:
            traveled = (
                db.query(UserStreetCoverage)
                .filter(
                    UserStreetCoverage.user_id == user.id,
                    UserStreetCoverage.street_segment_id.in_(street_ids),
                    UserStreetCoverage.is_traveled == True,
                )
                .count()
            )
        total = n.total_street_segments or len(street_ids)
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
async def neighborhood_boundary(
    city_id: int,
    neighborhood_id: int,
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

    # Compute coverage for the feature properties
    street_ids = [
        s.id for s in db.query(StreetSegment.id).filter_by(neighborhood_id=n.id).all()
    ]
    traveled = 0
    if street_ids:
        traveled = (
            db.query(UserStreetCoverage)
            .filter(
                UserStreetCoverage.user_id == user.id,
                UserStreetCoverage.street_segment_id.in_(street_ids),
                UserStreetCoverage.is_traveled == True,
            )
            .count()
        )
    total = n.total_street_segments or len(street_ids)
    pct = (traveled / total * 100) if total else 0.0

    try:
        boundary_shape = to_shape(n.boundary)
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
        geom_json = {}

    return {
        "type": "Feature",
        "properties": {
            "id": n.id,
            "name": n.name,
            "coverage_percentage": round(pct, 1),
        },
        "geometry": geom_json,
    }
