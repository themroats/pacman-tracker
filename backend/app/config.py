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
    database_url: str = "postgresql://pacman:pacman_dev@localhost:5432/pacman"
    pool_size: int = 10
    max_overflow: int = 20
    use_azure_identity: bool = False

    # --- Local verification harness (feature 008) ---
    # Dedicated, isolated database used ONLY by the local browser verification
    # harness. The seed/reset/snapshot scripts refuse to run against any database
    # whose name does not match this URL's database name.
    verification_database_url: str = (
        "postgresql://pacman:pacman_dev@localhost:5432/pacman_verify"
    )

    # --- OSRM ---
    osrm_url: str = "http://localhost:5000"

    # --- Development ---
    dev_auth_bypass: bool = False

    # --- CORS ---
    cors_origins: str = "http://localhost:5173"

    # --- City bootstrap ---
    auto_load_cities_on_empty_db: bool = True
    auto_load_city_name: str = ""
    manual_bootstrap_token: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
