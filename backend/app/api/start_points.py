"""
Start Points API router — CRUD for saved favorite start locations.

Endpoints:
- GET    /start-points            → list user's saved points
- POST   /start-points            → save a new point
- PATCH  /start-points/{id}       → update name or default flag
- DELETE /start-points/{id}       → remove a saved point
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.errors import AppError
from app.models.start_point import UserStartPoint
from app.models.user import User
from app.schemas.start_point import StartPointCreate, StartPointResponse, StartPointUpdate

router = APIRouter(prefix="/start-points", tags=["start-points"])

MAX_START_POINTS = 20


@router.get("", response_model=list[StartPointResponse])
def list_start_points(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return all saved start points for the current user."""
    points = (
        db.query(UserStartPoint)
        .filter_by(user_id=user.id)
        .order_by(UserStartPoint.is_default.desc(), UserStartPoint.name)
        .all()
    )
    return [_to_response(p) for p in points]


@router.post("", response_model=StartPointResponse, status_code=201)
def create_start_point(
    body: StartPointCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save a new start point."""
    count = db.query(UserStartPoint).filter_by(user_id=user.id).count()
    if count >= MAX_START_POINTS:
        raise AppError(
            "LIMIT_EXCEEDED",
            f"Maximum of {MAX_START_POINTS} start points allowed",
            400,
        )

    # If setting as default, clear existing default
    if body.is_default:
        _clear_defaults(db, user.id)

    sp = UserStartPoint(
        user_id=user.id,
        name=body.name,
        point=from_shape(Point(body.lng, body.lat), srid=4326),
        is_default=body.is_default,
    )
    db.add(sp)
    db.flush()
    return _to_response(sp)


@router.patch("/{point_id}", response_model=StartPointResponse)
def update_start_point(
    point_id: int,
    body: StartPointUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a saved start point's name or default flag."""
    sp = db.get(UserStartPoint, point_id)
    if not sp or sp.user_id != user.id:
        raise AppError("NOT_FOUND", "Start point not found", 404)

    if body.name is not None:
        sp.name = body.name
    if body.is_default is not None:
        if body.is_default:
            _clear_defaults(db, user.id)
        sp.is_default = body.is_default

    db.flush()
    return _to_response(sp)


@router.delete("/{point_id}", status_code=204)
def delete_start_point(
    point_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a saved start point."""
    sp = db.get(UserStartPoint, point_id)
    if not sp or sp.user_id != user.id:
        raise AppError("NOT_FOUND", "Start point not found", 404)

    db.delete(sp)
    db.flush()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_defaults(db: Session, user_id: int) -> None:
    """Unset is_default on all start points for a user."""
    db.query(UserStartPoint).filter_by(user_id=user_id, is_default=True).update(
        {"is_default": False}
    )


def _to_response(sp: UserStartPoint) -> StartPointResponse:
    """Convert a DB start point to a response schema."""
    pt = to_shape(sp.point)
    return StartPointResponse(
        id=sp.id,
        name=sp.name,
        lng=pt.x,
        lat=pt.y,
        is_default=sp.is_default,
    )
