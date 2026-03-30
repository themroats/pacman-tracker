"""Pydantic schemas for saved start points."""

from pydantic import BaseModel, Field


class StartPointCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    lng: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)
    is_default: bool = False


class StartPointUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    is_default: bool | None = None


class StartPointResponse(BaseModel):
    id: int
    name: str
    lng: float
    lat: float
    is_default: bool
