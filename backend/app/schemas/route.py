"""
Pydantic schemas for Route Suggestions (US3, T055).
"""

from pydantic import BaseModel, Field


class RouteSuggestRequest(BaseModel):
    start_point: dict = Field(..., description='{"lng": float, "lat": float}')
    distance_meters: float = Field(..., gt=0)
    city_id: int
    neighborhood_id: int | None = None


class RouteGeometry(BaseModel):
    type: str = "LineString"
    coordinates: list[list[float]]


class RouteSuggestRouteInfo(BaseModel):
    id: int
    distance_meters: float
    estimated_duration_seconds: int
    untraveled_distance_meters: float
    untraveled_ratio: float = Field(ge=0, le=1)
    geometry: RouteGeometry


class RouteSegmentInfo(BaseModel):
    street_name: str
    is_untraveled: bool
    length_meters: float


class NeighborhoodSuggestion(BaseModel):
    id: int
    name: str
    coverage_percentage: float


class RouteSuggestResponse(BaseModel):
    route: RouteSuggestRouteInfo | None = None
    segments: list[RouteSegmentInfo] = []
    message: str | None = None
    suggested_neighborhoods: list[NeighborhoodSuggestion] | None = None


class RouteHistoryItem(BaseModel):
    id: int
    created_at: str
    distance_meters: float
    untraveled_ratio: float
    neighborhood_name: str | None
    city_name: str
