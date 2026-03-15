"""
Pydantic schemas for Route Suggestions (US3, T055).
"""

from pydantic import BaseModel, Field


class StartPoint(BaseModel):
    lng: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)


class RouteSuggestRequest(BaseModel):
    start_point: StartPoint
    distance_meters: float = Field(..., gt=0, le=50000)
    city_id: int = Field(..., gt=0)
    neighborhood_id: int | None = Field(None, gt=0)


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
