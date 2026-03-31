"""Pydantic schemas for coverage plans and goals."""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Coverage Plans (neighborhood-level)
# ---------------------------------------------------------------------------


class CoveragePlanCreate(BaseModel):
    neighborhood_id: int = Field(..., gt=0)
    city_id: int = Field(..., gt=0)
    preferred_route_distance_m: float = Field(..., gt=0, le=50000)
    start_point_id: int = Field(..., gt=0, description="User's saved start point to use for all routes")


class CoveragePlanRouteInfo(BaseModel):
    sequence_order: int
    status: str
    route_id: int
    distance_meters: float
    estimated_duration_seconds: int
    streets_targeted: int
    untraveled_ratio: float


class CoveragePlanResponse(BaseModel):
    id: int
    neighborhood_id: int
    neighborhood_name: str
    city_id: int
    status: str
    preferred_route_distance_m: float
    initial_coverage_pct: float
    target_coverage_pct: float
    total_routes: int
    total_distance_m: float
    error_message: str | None = None
    routes: list[CoveragePlanRouteInfo] = []


class CoveragePlanSummary(BaseModel):
    id: int
    neighborhood_name: str
    status: str
    total_routes: int
    total_distance_m: float
    initial_coverage_pct: float
    goal_id: int | None = None


# ---------------------------------------------------------------------------
# Coverage Goals (city-level)
# ---------------------------------------------------------------------------


class CoverageGoalCreate(BaseModel):
    city_id: int = Field(..., gt=0)
    target_coverage_pct: float = Field(..., gt=0, le=100)
    preferred_route_distance_m: float = Field(..., gt=0, le=50000)


class GoalNeighborhoodInfo(BaseModel):
    neighborhood_id: int
    neighborhood_name: str
    current_coverage_pct: float
    untraveled_streets: int
    untraveled_distance_m: float
    plan_id: int | None = None
    plan_status: str | None = None
    estimated_routes: int


class CoverageGoalResponse(BaseModel):
    id: int
    city_id: int
    target_coverage_pct: float
    current_coverage_pct: float
    status: str
    total_routes: int
    total_distance_m: float
    neighborhoods: list[GoalNeighborhoodInfo] = []


class CoverageGoalSummary(BaseModel):
    id: int
    city_id: int
    target_coverage_pct: float
    current_coverage_pct: float
    status: str
    total_neighborhoods: int
    total_routes: int
