"""
Application configuration — Pydantic BaseSettings.

Loads from environment variables / .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Strava OAuth ---
    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_redirect_uri: str = "http://localhost:8000/api/v1/auth/strava/callback"
    strava_webhook_verify_token: str = "pacman-tracker-verify"

    # --- Security ---
    secret_key: str = "CHANGE-ME-IN-PRODUCTION"

    # --- Database ---
    database_url: str = "sqlite:///./data/pacman.db"

    # --- OSRM ---
    osrm_url: str = "http://localhost:5000"

    # --- Development ---
    dev_auth_bypass: bool = False

    # --- CORS ---
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_sqlite(self) -> bool:
        """True when using SQLite/SpatiaLite backend."""
        return self.database_url.startswith("sqlite")


def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
