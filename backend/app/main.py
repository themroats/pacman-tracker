"""
FastAPI application entry point.

Includes CORS middleware, error handling, router registration, and lifespan events.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings


# ---------------------------------------------------------------------------
# Standard error response format
# ---------------------------------------------------------------------------


class AppError(Exception):
    """Application-level error with structured response."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def error_response(code: str, message: str, status_code: int, details: dict | None = None) -> JSONResponse:
    """Build a standardised JSON error response."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
    )


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown hooks."""
    # Startup: ensure database engine and schema are initialised.
    from app import models  # noqa: F401
    from app.database import Base, get_engine
    from app.services.city_bootstrap import ensure_city_bootstrap_started

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    ensure_city_bootstrap_started()
    yield
    # Shutdown: clean up
    from app.database import reset_engine

    reset_engine()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Strava Street Mapper",
        description="Track Strava exercises and compare with the street map.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Error handlers ---
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return error_response(exc.code, exc.message, exc.status_code, exc.details)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return error_response("NOT_FOUND", "Resource not found", 404)

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc):
        import traceback
        traceback.print_exc()
        return error_response("INTERNAL_ERROR", "Internal server error", 500)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        import traceback
        traceback.print_exc()
        return error_response("INTERNAL_ERROR", str(exc), 500)

    # --- Routers ---
    from app.api.auth import router as auth_router
    from app.api.admin import router as admin_router
    from app.api.activities import router as activities_router
    from app.api.cities import router as cities_router
    from app.api.coverage import router as coverage_router
    from app.api.progress import router as progress_router
    from app.api.routes import router as routes_router
    from app.api.sync import router as sync_router
    from app.api.webhook import router as webhook_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(activities_router, prefix="/api/v1")
    app.include_router(cities_router, prefix="/api/v1")
    app.include_router(coverage_router, prefix="/api/v1")
    app.include_router(progress_router, prefix="/api/v1")
    app.include_router(routes_router, prefix="/api/v1")
    app.include_router(sync_router, prefix="/api/v1")
    app.include_router(webhook_router, prefix="/api/v1")

    # Health check
    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app


# Create the app instance for Uvicorn
app = create_app()
