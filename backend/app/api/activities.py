"""
Activities API router — activity CRUD and filtering.

Endpoints:
- GET /activities            → List with filters
- GET /activities/{id}       → Detail with GPS trace
- GET /activities/{id}/geojson → Single activity GeoJSON
- GET /activities/geojson    → All activities GeoJSON FeatureCollection
"""

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import AppError
from app.models.activity import Activity
from app.schemas.activity import (
    ActivityDetail,
    ActivityGeoJSONCollection,
    ActivityGeoJSONFeature,
    ActivityGeoJSONProperties,
    ActivityListResponse,
    ActivitySummary,
)

router = APIRouter(prefix="/activities", tags=["activities"])


def get_current_user(db: Session = Depends(get_db), **kwargs):
    """Placeholder auth dependency — will be replaced with proper auth."""
    from app.api.sync import get_current_user as _get_user
    raise AppError("UNAUTHORIZED", "Auth not implemented", 401)


def _activity_to_summary(act: Activity) -> ActivitySummary:
    """Convert an Activity ORM instance to an ActivitySummary schema."""
    return ActivitySummary(
        id=act.id,
        strava_activity_id=act.strava_activity_id,
        name=act.name,
        sport_type=act.sport_type,
        start_date=act.start_date,
        distance_meters=act.distance_meters,
        duration_seconds=act.duration_seconds,
        moving_time_seconds=act.moving_time_seconds,
        has_gps=act.has_gps,
        is_on_street=act.is_on_street,
        city_name=None,  # Populated when city join is available
    )


def _activity_to_geojson_feature(act: Activity) -> ActivityGeoJSONFeature:
    """Convert an Activity to a GeoJSON Feature."""
    geometry = None
    if act.gps_trace is not None:
        try:
            shape = to_shape(act.gps_trace)
            geometry = {
                "type": "LineString",
                "coordinates": list(shape.coords),
            }
        except Exception:
            pass

    return ActivityGeoJSONFeature(
        properties=ActivityGeoJSONProperties(
            id=act.id,
            name=act.name,
            sport_type=act.sport_type,
            distance_meters=act.distance_meters,
            start_date=act.start_date,
        ),
        geometry=geometry,
    )


@router.get("", response_model=ActivityListResponse)
async def list_activities(
    sport_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    min_distance: Optional[float] = Query(None),
    max_distance: Optional[float] = Query(None),
    city_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List user's imported activities with optional filters."""
    # TODO: Replace with proper auth
    # user = Depends(get_current_user)
    query = db.query(Activity)

    if sport_type:
        query = query.filter(Activity.sport_type == sport_type)
    if start_date:
        query = query.filter(Activity.start_date >= datetime.datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(Activity.start_date <= datetime.datetime.fromisoformat(end_date))
    if min_distance is not None:
        query = query.filter(Activity.distance_meters >= min_distance)
    if max_distance is not None:
        query = query.filter(Activity.distance_meters <= max_distance)
    if city_id is not None:
        query = query.filter(Activity.city_id == city_id)

    total = query.count()
    activities = (
        query.order_by(Activity.start_date.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return ActivityListResponse(
        activities=[_activity_to_summary(a) for a in activities],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/geojson")
async def activities_geojson(
    sport_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get all user activities as a GeoJSON FeatureCollection."""
    query = db.query(Activity).filter(Activity.has_gps == True)  # noqa: E712

    if sport_type:
        query = query.filter(Activity.sport_type == sport_type)
    if start_date:
        query = query.filter(Activity.start_date >= datetime.datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(Activity.start_date <= datetime.datetime.fromisoformat(end_date))

    activities = query.order_by(Activity.start_date.desc()).all()

    return ActivityGeoJSONCollection(
        features=[_activity_to_geojson_feature(a) for a in activities],
    )


@router.get("/{activity_id}")
async def get_activity(
    activity_id: int,
    db: Session = Depends(get_db),
):
    """Get detailed activity with GPS trace."""
    activity = db.query(Activity).get(activity_id)
    if not activity:
        raise AppError("NOT_FOUND", "Activity not found", 404)

    gps_trace = None
    if activity.gps_trace is not None:
        try:
            shape = to_shape(activity.gps_trace)
            gps_trace = {
                "type": "LineString",
                "coordinates": list(shape.coords),
            }
        except Exception:
            pass

    return ActivityDetail(
        id=activity.id,
        strava_activity_id=activity.strava_activity_id,
        name=activity.name,
        sport_type=activity.sport_type,
        start_date=activity.start_date,
        distance_meters=activity.distance_meters,
        duration_seconds=activity.duration_seconds,
        moving_time_seconds=activity.moving_time_seconds,
        has_gps=activity.has_gps,
        is_on_street=activity.is_on_street,
        gps_trace=gps_trace,
    )


@router.get("/{activity_id}/geojson")
async def activity_geojson(
    activity_id: int,
    db: Session = Depends(get_db),
):
    """Get single activity as GeoJSON Feature."""
    activity = db.query(Activity).get(activity_id)
    if not activity:
        raise AppError("NOT_FOUND", "Activity not found", 404)

    return _activity_to_geojson_feature(activity)
