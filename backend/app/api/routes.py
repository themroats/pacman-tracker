"""
Routes API router (T059).

Endpoints:
- POST /routes/suggest     → generate route suggestion
- GET  /routes/history     → past route suggestions
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point, LineString
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import AppError
from app.models.city import City
from app.models.coverage import UserStreetCoverage
from app.models.neighborhood import Neighborhood
from app.models.route import RouteSuggestion, RouteSuggestionSegment
from app.models.street import StreetSegment
from app.models.user import User
from app.schemas.route import RouteSuggestRequest
from app.services.routing import OSRMClient, RouteSuggestionEngine

router = APIRouter(prefix="/routes", tags=["routes"])


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _get_current_user(
    db: Session = Depends(get_db),
    authorization: str = Header(None),
) -> User:
    if not authorization:
        raise AppError("UNAUTHORIZED", "Missing authorization header", 401)
    user = db.query(User).first()
    if not user:
        raise AppError("UNAUTHORIZED", "User not found", 401)
    return user


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
    city = db.query(City).get(body.city_id)
    if not city:
        raise AppError("NOT_FOUND", f"City {body.city_id} not found", 404)

    # Validate start point
    lng = body.start_point.get("lng")
    lat = body.start_point.get("lat")
    if lng is None or lat is None:
        raise AppError("VALIDATION_ERROR", "start_point must have lng and lat", 400)

    # Query street segments (optionally filtered by neighborhood)
    street_query = db.query(StreetSegment).filter_by(city_id=body.city_id)
    if body.neighborhood_id:
        street_query = street_query.filter_by(neighborhood_id=body.neighborhood_id)
    db_streets = street_query.all()

    if not db_streets:
        raise AppError("NOT_FOUND", "No streets found in this area", 404)

    # Build coverage lookup
    street_ids = [s.id for s in db_streets]
    cov_rows = (
        db.query(UserStreetCoverage)
        .filter(
            UserStreetCoverage.user_id == user.id,
            UserStreetCoverage.street_segment_id.in_(street_ids),
        )
        .all()
    )
    cov_map = {r.street_segment_id: r.is_traveled for r in cov_rows}

    # Prepare streets for the engine
    streets_for_engine = []
    for s in db_streets:
        try:
            geom = to_shape(s.geometry)
        except Exception:
            continue
        streets_for_engine.append(
            {
                "id": s.id,
                "geometry": geom,
                "length_meters": s.length_meters,
                "is_traveled": cov_map.get(s.id, False),
                "name": s.name,
            }
        )

    engine = RouteSuggestionEngine()
    result = await engine.suggest(
        start=(lng, lat),
        target_distance=body.distance_meters,
        streets=streets_for_engine,
    )

    # 100 %-covered fallback
    if result["route"] is None:
        # Suggest neighborhoods with lowest coverage
        neighborhoods = (
            db.query(Neighborhood).filter_by(city_id=body.city_id).all()
        )
        suggestions = []
        for n in neighborhoods:
            n_streets = [s.id for s in db.query(StreetSegment.id).filter_by(neighborhood_id=n.id).all()]
            if not n_streets:
                continue
            traveled = sum(1 for sid in n_streets if cov_map.get(sid, False))
            pct = traveled / len(n_streets) * 100
            if pct < 100:
                suggestions.append({"id": n.id, "name": n.name, "coverage_percentage": round(pct, 1)})

        suggestions.sort(key=lambda x: x["coverage_percentage"])

        return {
            "route": None,
            "segments": [],
            "message": result.get("message", "All streets covered."),
            "suggested_neighborhoods": suggestions[:5],
        }

    # Persist the suggestion
    route_data = result["route"]
    route_geom = LineString(
        [(c[0], c[1]) for c in route_data["geometry"]["coordinates"]]
    )
    untraveled_dist = route_data["distance"] * result["untraveled_ratio"]

    suggestion = RouteSuggestion(
        user_id=user.id,
        city_id=body.city_id,
        neighborhood_id=body.neighborhood_id,
        start_point=from_shape(Point(lng, lat), srid=4326),
        route_geometry=from_shape(route_geom, srid=4326),
        distance_meters=route_data["distance"],
        estimated_duration_seconds=int(route_data["duration"]),
        requested_distance_meters=body.distance_meters,
        untraveled_distance_meters=untraveled_dist,
        untraveled_ratio=result["untraveled_ratio"],
    )
    db.add(suggestion)
    db.flush()

    # Build segment list from waypoints matched to streets
    segments_info = []
    for i, s in enumerate(streets_for_engine):
        if s["id"] in {r["id"] for r in streets_for_engine if not r["is_traveled"]}:
            seg = RouteSuggestionSegment(
                route_suggestion_id=suggestion.id,
                street_segment_id=s["id"],
                sequence_order=i + 1,
                is_untraveled=not s["is_traveled"],
            )
            db.add(seg)
            segments_info.append(
                {
                    "street_name": s.get("name") or "Unnamed",
                    "is_untraveled": not s["is_traveled"],
                    "length_meters": s["length_meters"],
                }
            )
    db.flush()

    return {
        "route": {
            "id": suggestion.id,
            "distance_meters": route_data["distance"],
            "estimated_duration_seconds": int(route_data["duration"]),
            "untraveled_distance_meters": untraveled_dist,
            "untraveled_ratio": result["untraveled_ratio"],
            "geometry": route_data["geometry"],
        },
        "segments": segments_info[:50],  # Cap for response size
    }


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
        city = db.query(City).get(s.city_id)
        n = db.query(Neighborhood).get(s.neighborhood_id) if s.neighborhood_id else None
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
