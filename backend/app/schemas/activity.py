"""Pydantic schemas for Activity request/response models."""

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field


class ActivitySummary(BaseModel):
    """Activity summary for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    strava_activity_id: int
    name: str
    sport_type: str
    start_date: datetime.datetime
    distance_meters: float
    duration_seconds: int
    moving_time_seconds: int
    has_gps: bool
    is_on_street: bool
    city_name: str | None = None

    @computed_field
    @property
    def pace_min_per_km(self) -> float | None:
        if self.distance_meters > 0:
            return round((self.moving_time_seconds / 60) / (self.distance_meters / 1000), 2)
        return None


class ActivityDetail(ActivitySummary):
    """Activity detail with GPS trace."""

    gps_trace: dict[str, Any] | None = None


class ActivityGeoJSONProperties(BaseModel):
    """Properties for a GeoJSON Feature representing an activity."""

    id: int
    name: str
    sport_type: str
    distance_meters: float
    start_date: datetime.datetime


class ActivityGeoJSONFeature(BaseModel):
    """GeoJSON Feature for a single activity."""

    type: str = "Feature"
    properties: ActivityGeoJSONProperties
    geometry: dict[str, Any] | None = None


class ActivityGeoJSONCollection(BaseModel):
    """GeoJSON FeatureCollection for all activities."""

    type: str = "FeatureCollection"
    features: list[ActivityGeoJSONFeature] = []


class ActivityListResponse(BaseModel):
    """Paginated list of activities."""

    activities: list[ActivitySummary]
    total: int
    page: int
    per_page: int
