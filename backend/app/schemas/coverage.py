"""
Pydantic schemas for Coverage.

Covers:
- City-wide summary with neighborhood breakdown
- Neighborhood detail with boundary
- Street GeoJSON features with coverage status
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# City Coverage
# ---------------------------------------------------------------------------


class CityCoverageSummary(BaseModel):
    id: int
    name: str
    coverage_percentage: float = Field(ge=0, le=100)
    streets_traveled: int
    streets_total: int
    distance_traveled_m: float
    distance_total_m: float


class NeighborhoodCoverageSummary(BaseModel):
    id: int
    name: str
    coverage_percentage: float = Field(ge=0, le=100)
    streets_traveled: int
    streets_total: int
    distance_traveled_m: float
    distance_total_m: float


class CityCoverageResponse(BaseModel):
    city: CityCoverageSummary
    neighborhoods: list[NeighborhoodCoverageSummary]


# ---------------------------------------------------------------------------
# Neighborhood Detail
# ---------------------------------------------------------------------------


class NeighborhoodDetail(BaseModel):
    id: int
    name: str
    city_name: str
    coverage_percentage: float = Field(ge=0, le=100)
    streets_traveled: int
    streets_total: int


class NeighborhoodDetailResponse(BaseModel):
    neighborhood: NeighborhoodDetail
    boundary: dict  # GeoJSON geometry object


# ---------------------------------------------------------------------------
# Street GeoJSON Feature Properties
# ---------------------------------------------------------------------------


class StreetCoverageProperties(BaseModel):
    id: int
    name: str | None
    highway_type: str
    length_meters: float
    is_traveled: bool
    coverage_ratio: float = Field(ge=0, le=1)
    first_traveled_at: str | None = None


class StreetCoverageFeature(BaseModel):
    type: str = "Feature"
    properties: StreetCoverageProperties
    geometry: dict  # GeoJSON LineString


class StreetCoverageFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[StreetCoverageFeature]
