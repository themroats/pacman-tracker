"""Pydantic schemas for progress timeline, milestones, and overall stats."""

from pydantic import BaseModel


class TimelineEntry(BaseModel):
    """A single data point on the coverage-over-time chart."""

    date: str  # ISO date string YYYY-MM-DD
    coverage_percentage: float
    streets_traveled: int


class Milestone(BaseModel):
    """A coverage milestone (25/50/75/100%) for a neighborhood or city."""

    label: str  # e.g. "25%", "50%", "75%", "100%"
    neighborhood_name: str
    reached: bool
    date: str | None = None  # ISO date string, null if not yet reached


class ProgressResponse(BaseModel):
    """Response for GET /progress/city/{city_id}."""

    city_name: str
    current_coverage_percentage: float
    milestones: list[Milestone]
    timeline: list[TimelineEntry]


class CityStats(BaseModel):
    """Per-city stats for the overall stats response."""

    city_name: str
    coverage_percentage: float
    streets_traveled: int
    streets_total: int


class OverallStatsResponse(BaseModel):
    """Response for GET /progress/stats."""

    total_activities: int
    total_distance_meters: float
    total_unique_streets: int
    cities: list[CityStats]
