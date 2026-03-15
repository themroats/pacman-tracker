"""
Routes API router (T059).

Endpoints:
- POST /routes/suggest     → generate route suggestion
- GET  /routes/history     → past route suggestions
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import AppError
from app.models.city import City
from app.models.neighborhood import Neighborhood
from app.models.route import RouteSuggestion
from app.models.user import User
from app.schemas.route import RouteSuggestRequest
from app.services.routing import RoutePlannerService

router = APIRouter(prefix="/routes", tags=["routes"])

SERVICE_ERROR_STATUS_CODES = {
    "NOT_FOUND": 404,
    "OSRM_UNAVAILABLE": 503,
}


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


from app.api.deps import get_current_user as _get_current_user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/suggest")
async def suggest_route(
    body: RouteSuggestRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """Generate a route suggestion prioritising untraveled streets."""
    # Validate city
    city = db.get(City, body.city_id)
    if not city:
        raise AppError("NOT_FOUND", f"City {body.city_id} not found", 404)

    # Validate start point
    lng = body.start_point.get("lng")
    lat = body.start_point.get("lat")
    if lng is None or lat is None:
        raise AppError("VALIDATION_ERROR", "start_point must have lng and lat", 400)

    # Delegate to service
    planner = RoutePlannerService(db)
    result = await planner.suggest(
        user_id=user.id,
        city_id=body.city_id,
        neighborhood_id=body.neighborhood_id,
        start_lng=lng,
        start_lat=lat,
        distance_meters=body.distance_meters,
    )

    # Handle service-level errors
    if "error" in result:
        raise AppError(
            result["error"],
            result["message"],
            SERVICE_ERROR_STATUS_CODES.get(result["error"], 400),
        )

    return result


@router.get("/history")
async def route_history(
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """Return past route suggestions for the user."""
    suggestions = (
        db.query(RouteSuggestion)
        .filter_by(user_id=user.id)
        .order_by(RouteSuggestion.created_at.desc())
        .limit(50)
        .all()
    )

    routes = []
    for s in suggestions:
        city = db.get(City, s.city_id)
        n = db.get(Neighborhood, s.neighborhood_id) if s.neighborhood_id else None
        routes.append(
            {
                "id": s.id,
                "created_at": s.created_at.isoformat() if s.created_at else "",
                "distance_meters": s.distance_meters,
                "untraveled_ratio": s.untraveled_ratio,
                "neighborhood_name": n.name if n else None,
                "city_name": city.name if city else "",
            }
        )

    return {"routes": routes}
