"""Protected admin endpoints for manual operational tasks."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import AppError
from app.services.city_bootstrap import get_city_bootstrap_state, start_city_bootstrap
from app.services.neighborhood_bootstrap import (
    get_neighborhood_bootstrap_state,
    start_neighborhood_bootstrap,
)

router = APIRouter(prefix="/admin/bootstrap", tags=["admin"])


def _require_bootstrap_token(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    settings = get_settings()
    expected_token = settings.manual_bootstrap_token.strip()

    if not expected_token:
        raise AppError(
            "FEATURE_DISABLED",
            "Manual bootstrap endpoint is disabled",
            503,
        )

    if x_admin_token is None or not hmac.compare_digest(x_admin_token, expected_token):
        raise AppError("UNAUTHORIZED", "Invalid admin token", 401)


@router.get("/cities")
async def city_bootstrap_status(_: None = Depends(_require_bootstrap_token)):
    """Return the current manual city bootstrap state."""
    return get_city_bootstrap_state()


@router.post("/cities")
async def trigger_city_bootstrap(
    city: str | None = Query(default=None),
    _: None = Depends(_require_bootstrap_token),
):
    """Start city bootstrap in a background thread without tying it to app startup."""
    target_city = city.strip() if city and city.strip() else None
    state = start_city_bootstrap(target_city)
    status_code = 202 if state["status"] == "loading" else 200
    return JSONResponse(status_code=status_code, content=state)


@router.get("/neighborhoods")
async def neighborhood_bootstrap_status(
    city: str | None = Query(default=None),
    _: None = Depends(_require_bootstrap_token),
):
    """Return the current manual neighborhood bootstrap state."""
    target_city = city.strip() if city and city.strip() else None
    return get_neighborhood_bootstrap_state(target_city)


@router.post("/neighborhoods")
async def trigger_neighborhood_bootstrap(
    city: str | None = Query(default=None),
    _: None = Depends(_require_bootstrap_token),
):
    """Start neighborhood bootstrap in a background thread for one city or all cities."""
    target_city = city.strip() if city and city.strip() else None
    state = start_neighborhood_bootstrap(target_city)
    status_code = 202 if state["status"] == "loading" else 200
    return JSONResponse(status_code=status_code, content=state)