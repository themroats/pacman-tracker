"""Pydantic schemas for User request/response models."""

import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    """Public user information returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    display_name: str
    profile_image_url: str | None = None
    home_city: int | None = None
    sync_status: str = "idle"


class AuthCallbackResponse(BaseModel):
    """Response after successful OAuth callback."""

    user_id: int
    display_name: str
    access_token: str
    home_city: int | None = None
    sync_status: str = "importing"


class LogoutResponse(BaseModel):
    """Response after logout."""

    message: str = "Logged out"


class SyncStatusResponse(BaseModel):
    """Sync status for the authenticated user."""

    status: str
    total_activities: int = 0
    imported_activities: int = 0
    matched_activities: int = 0
    last_sync_at: datetime.datetime | None = None
    error_message: str | None = None
