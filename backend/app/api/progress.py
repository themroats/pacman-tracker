"""Progress API router (T068) — timeline, milestones, and overall stats."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.progress import OverallStatsResponse, ProgressResponse
from app.services.progress import get_city_timeline, get_overall_stats

router = APIRouter(prefix="/progress", tags=["progress"])

# TODO: Replace with real auth dependency
PLACEHOLDER_USER_ID = 1


@router.get("/city/{city_id}", response_model=ProgressResponse)
def progress_city(city_id: int, db: Session = Depends(get_db)):
    """Get progress timeline and milestones for a city."""
    data = get_city_timeline(db, user_id=PLACEHOLDER_USER_ID, city_id=city_id)
    return ProgressResponse(**data)


@router.get("/stats", response_model=OverallStatsResponse)
def progress_stats(db: Session = Depends(get_db)):
    """Get overall user statistics."""
    data = get_overall_stats(db, user_id=PLACEHOLDER_USER_ID)
    return OverallStatsResponse(**data)
