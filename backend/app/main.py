"""
FastAPI application entry point.

Includes CORS middleware, error handling, router registration, and lifespan events.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import AppError, error_response


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown hooks."""
    import logging

    from app import models  # noqa: F401
    from app.database import Base, get_engine
    from app.services.city_bootstrap import ensure_city_bootstrap_started

    startup_logger = logging.getLogger(__name__)

    engine = get_engine()

    # Apply pending Alembic migrations on startup
    from alembic.config import Config as AlembicConfig
    from alembic import command as alembic_command
    import os

    alembic_cfg = AlembicConfig(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url).replace("%", "%%"))
    alembic_command.upgrade(alembic_cfg, "head")

    # Recover stale sync statuses from previous process crash / restart
    from sqlalchemy.orm import Session
    from app.models.user import User

    with Session(engine) as session:
        stale_users = (
            session.query(User)
            .filter(User.sync_status.in_(["syncing", "importing"]))
            .all()
        )
        for u in stale_users:
            startup_logger.warning(
                "Recovering stale sync status for user %d (%s -> error)",
                u.id,
                u.sync_status,
            )
            u.sync_status = "error"
        if stale_users:
            session.commit()

    ensure_city_bootstrap_started()
    yield
    # Shutdown: clean up
    from app.database import reset_engine

    reset_engine()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(*, custom_lifespan=None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Strava Street Mapper",
        description="Track Strava exercises and compare with the street map.",
        version="0.1.0",
        lifespan=custom_lifespan or lifespan,
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

    from sqlalchemy.exc import OperationalError, InterfaceError

    @app.exception_handler(OperationalError)
    async def db_operational_error_handler(request: Request, exc: OperationalError):
        import logging
        logging.getLogger(__name__).error("Database connection error: %s", exc)
        return error_response("DATABASE_ERROR", "Database is temporarily unavailable", 503)

    @app.exception_handler(InterfaceError)
    async def db_interface_error_handler(request: Request, exc: InterfaceError):
        import logging
        logging.getLogger(__name__).error("Database interface error: %s", exc)
        return error_response("DATABASE_ERROR", "Database is temporarily unavailable", 503)

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
    from app.api.plans import router as plans_router
    from app.api.progress import router as progress_router
    from app.api.routes import router as routes_router
    from app.api.start_points import router as start_points_router
    from app.api.sync import router as sync_router
    from app.api.webhook import router as webhook_router

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(activities_router, prefix="/api/v1")
    app.include_router(cities_router, prefix="/api/v1")
    app.include_router(coverage_router, prefix="/api/v1")
    app.include_router(plans_router, prefix="/api/v1")
    app.include_router(progress_router, prefix="/api/v1")
    app.include_router(routes_router, prefix="/api/v1")
    app.include_router(start_points_router, prefix="/api/v1")
    app.include_router(sync_router, prefix="/api/v1")
    app.include_router(webhook_router, prefix="/api/v1")

    # Health check
    @app.get("/health")
    async def health_check():
        from app.services.routing import check_osrm_available

        osrm_ok = await check_osrm_available()
        return {"status": "ok", "osrm_available": osrm_ok}

    return app


# Create the app instance for Uvicorn
app = create_app()
