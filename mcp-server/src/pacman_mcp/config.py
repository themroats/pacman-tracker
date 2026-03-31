"""Configuration — reads settings from environment variables."""

from __future__ import annotations

import os


def get_api_url() -> str:
    return os.environ.get("PACMAN_API_URL", "http://localhost:8000")


def get_strava_client_id() -> str:
    value = os.environ.get("STRAVA_CLIENT_ID", "")
    if not value:
        raise RuntimeError("STRAVA_CLIENT_ID environment variable is required")
    return value


def get_strava_client_secret() -> str:
    value = os.environ.get("STRAVA_CLIENT_SECRET", "")
    if not value:
        raise RuntimeError("STRAVA_CLIENT_SECRET environment variable is required")
    return value
