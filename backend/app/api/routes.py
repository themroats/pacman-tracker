"""
Routes API router.

Endpoints:
- POST /routes/suggest              → generate route suggestion
- GET  /routes/history              → past route suggestions
- GET  /routes/{route_id}/export/gpx → download GPX file
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.models.city import City
from app.models.neighborhood import Neighborhood
from app.models.route import RouteSuggestion
from app.models.user import User
from app.schemas.route import RouteSuggestRequest
from app.services.gpx_export import build_gpx
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
    # Check OSRM availability
    from app.services.routing import check_osrm_available

    if not await check_osrm_available():
        raise AppError("OSRM_UNAVAILABLE", "Route suggestions are temporarily unavailable", 503)

    # Validate city
    city = db.get(City, body.city_id)
    if not city:
        raise AppError("NOT_FOUND", f"City {body.city_id} not found", 404)

    # Extract validated start point
    lng = body.start_point.lng
    lat = body.start_point.lat

    # Delegate to service
    planner = RoutePlannerService(db)
    result = await planner.suggest(
        user_id=user.id,
        city_id=body.city_id,
        neighborhood_id=body.neighborhood_id,
        start_lng=lng,
        start_lat=lat,
        distance_meters=body.distance_meters,
        variation=body.variation,
        preferences=body.preferences.model_dump() if body.preferences else None,
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
def route_history(
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


@router.get("/{route_id}/export/gpx")
def export_gpx(
    route_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """Download a route suggestion as a GPX file."""
    suggestion = db.get(RouteSuggestion, route_id)
    if not suggestion:
        raise AppError("NOT_FOUND", f"Route {route_id} not found", 404)
    if suggestion.user_id != user.id:
        raise AppError("FORBIDDEN", "You do not own this route", 403)

    gpx_xml = build_gpx(suggestion)
    filename = f"pacman-route-{route_id}.gpx"
    return Response(
        content=gpx_xml,
        media_type="application/gpx+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{route_id}/geojson")
def route_geojson(
    route_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_get_current_user),
):
    """Return the route geometry as GeoJSON for map display."""
    from geoalchemy2.shape import to_shape

    suggestion = db.get(RouteSuggestion, route_id)
    if not suggestion:
        raise AppError("NOT_FOUND", f"Route {route_id} not found", 404)
    if suggestion.user_id != user.id:
        raise AppError("FORBIDDEN", "You do not own this route", 403)

    geom = to_shape(suggestion.route_geometry)
    coords = [[c[0], c[1]] for c in geom.coords]

    return {
        "type": "Feature",
        "properties": {
            "route_id": route_id,
            "distance_meters": suggestion.distance_meters,
            "estimated_duration_seconds": suggestion.estimated_duration_seconds,
        },
        "geometry": {
            "type": "LineString",
            "coordinates": coords,
        },
    }
