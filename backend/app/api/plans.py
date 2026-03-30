"""
Plans API router — coverage plans and city-level goals.

Endpoints:
- POST   /plans/neighborhood              → generate a neighborhood coverage plan
- GET    /plans/{plan_id}                  → get plan with routes
- DELETE /plans/{plan_id}                  → delete a plan
- GET    /plans                            → list user's plans
- POST   /goals                            → create a city-level coverage goal
- GET    /goals/{goal_id}                  → get goal with linked plans
- GET    /goals                            → list user's goals
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.errors import AppError
from app.models.city import City
from app.models.neighborhood import Neighborhood
from app.models.plan import CoverageGoal, CoveragePlan, CoveragePlanRoute
from app.models.route import RouteSuggestion
from app.models.start_point import UserStartPoint
from app.models.user import User
from app.schemas.plan import (
    CoverageGoalCreate,
    CoverageGoalResponse,
    CoverageGoalSummary,
    CoveragePlanCreate,
    CoveragePlanResponse,
    CoveragePlanRouteInfo,
    CoveragePlanSummary,
    GoalNeighborhoodInfo,
)
from app.services.planner import CoveragePlannerService

router = APIRouter(prefix="/plans", tags=["plans"])


# ---------------------------------------------------------------------------
# Coverage Plans (neighborhood-level)
# ---------------------------------------------------------------------------


@router.post("/neighborhood", status_code=201)
async def create_neighborhood_plan(
    body: CoveragePlanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a multi-route coverage plan for a neighborhood."""
    from app.services.routing import check_osrm_available

    if not await check_osrm_available():
        raise AppError("OSRM_UNAVAILABLE", "Route suggestions are temporarily unavailable", 503)

    neighborhood = db.get(Neighborhood, body.neighborhood_id)
    if not neighborhood:
        raise AppError("NOT_FOUND", f"Neighborhood {body.neighborhood_id} not found", 404)

    city = db.get(City, body.city_id)
    if not city:
        raise AppError("NOT_FOUND", f"City {body.city_id} not found", 404)

    start_point = db.get(UserStartPoint, body.start_point_id)
    if not start_point or start_point.user_id != user.id:
        raise AppError("NOT_FOUND", f"Start point {body.start_point_id} not found", 404)

    from geoalchemy2.shape import to_shape
    sp_geom = to_shape(start_point.point)

    planner = CoveragePlannerService(db)
    plan = await planner.create_neighborhood_plan(
        user_id=user.id,
        city_id=body.city_id,
        neighborhood_id=body.neighborhood_id,
        preferred_distance_m=body.preferred_route_distance_m,
        start_lng=sp_geom.x,
        start_lat=sp_geom.y,
    )

    return _plan_response(plan, neighborhood)


@router.get("", response_model=list[CoveragePlanSummary])
def list_plans(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all coverage plans for the current user."""
    plans = (
        db.query(CoveragePlan)
        .filter_by(user_id=user.id)
        .order_by(CoveragePlan.created_at.desc())
        .limit(50)
        .all()
    )
    result = []
    for p in plans:
        n = db.get(Neighborhood, p.neighborhood_id)
        result.append(CoveragePlanSummary(
            id=p.id,
            neighborhood_name=n.name if n else "Unknown",
            status=p.status,
            total_routes=p.total_routes,
            total_distance_m=p.total_distance_m,
            initial_coverage_pct=p.initial_coverage_pct,
        ))
    return result


# ---------------------------------------------------------------------------
# Coverage Goals (city-level) — must be before /{plan_id} catch-all
# ---------------------------------------------------------------------------


@router.post("/goals", status_code=201)
async def create_goal(
    body: CoverageGoalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a city-level coverage goal and generate plans."""
    from app.services.routing import check_osrm_available

    if not await check_osrm_available():
        raise AppError("OSRM_UNAVAILABLE", "Route suggestions are temporarily unavailable", 503)

    city = db.get(City, body.city_id)
    if not city:
        raise AppError("NOT_FOUND", f"City {body.city_id} not found", 404)

    planner = CoveragePlannerService(db)
    goal = await planner.create_coverage_goal(
        user_id=user.id,
        city_id=body.city_id,
        target_coverage_pct=body.target_coverage_pct,
        preferred_route_distance_m=body.preferred_route_distance_m,
    )

    return _goal_response(goal, db)


@router.get("/goals", response_model=list[CoverageGoalSummary])
def list_goals(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all coverage goals for the current user."""
    goals = (
        db.query(CoverageGoal)
        .filter_by(user_id=user.id)
        .order_by(CoverageGoal.created_at.desc())
        .limit(20)
        .all()
    )
    result = []
    for g in goals:
        total_routes = sum(p.total_routes for p in g.plans)
        result.append(CoverageGoalSummary(
            id=g.id,
            city_id=g.city_id,
            target_coverage_pct=g.target_coverage_pct,
            current_coverage_pct=g.current_coverage_pct,
            status=g.status,
            total_neighborhoods=len(g.plans),
            total_routes=total_routes,
        ))
    return result


@router.get("/goals/{goal_id}")
def get_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a coverage goal with its linked plans."""
    goal = db.get(CoverageGoal, goal_id)
    if not goal or goal.user_id != user.id:
        raise AppError("NOT_FOUND", "Goal not found", 404)

    return _goal_response(goal, db)


# ---------------------------------------------------------------------------
# Coverage Plan detail routes (/{plan_id} must come after /goals)
# ---------------------------------------------------------------------------


@router.get("/{plan_id}")
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a coverage plan with its routes."""
    plan = db.get(CoveragePlan, plan_id)
    if not plan or plan.user_id != user.id:
        raise AppError("NOT_FOUND", "Plan not found", 404)

    neighborhood = db.get(Neighborhood, plan.neighborhood_id)
    return _plan_response(plan, neighborhood)


@router.delete("/{plan_id}", status_code=204)
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a coverage plan and its routes."""
    plan = db.get(CoveragePlan, plan_id)
    if not plan or plan.user_id != user.id:
        raise AppError("NOT_FOUND", "Plan not found", 404)

    db.delete(plan)
    db.flush()


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------


def _plan_response(plan: CoveragePlan, neighborhood: Neighborhood | None) -> dict:
    """Build a CoveragePlanResponse dict."""
    routes = []
    for pr in plan.routes:
        rs = pr.route_suggestion
        routes.append(CoveragePlanRouteInfo(
            sequence_order=pr.sequence_order,
            status=pr.status,
            route_id=rs.id if rs else 0,
            distance_meters=rs.distance_meters if rs else 0,
            estimated_duration_seconds=rs.estimated_duration_seconds if rs else 0,
            streets_targeted=pr.streets_targeted,
            untraveled_ratio=rs.untraveled_ratio if rs else 0,
        ))

    return CoveragePlanResponse(
        id=plan.id,
        neighborhood_id=plan.neighborhood_id,
        neighborhood_name=neighborhood.name if neighborhood else "Unknown",
        city_id=plan.city_id,
        status=plan.status,
        preferred_route_distance_m=plan.preferred_route_distance_m,
        initial_coverage_pct=plan.initial_coverage_pct,
        target_coverage_pct=plan.target_coverage_pct,
        total_routes=plan.total_routes,
        total_distance_m=plan.total_distance_m,
        error_message=plan.error_message,
        routes=routes,
    ).model_dump()


def _goal_response(goal: CoverageGoal, db: Session) -> dict:
    """Build a CoverageGoalResponse dict."""
    neighborhoods = []
    total_routes = 0
    total_distance = 0.0

    for plan in goal.plans:
        n = db.get(Neighborhood, plan.neighborhood_id)
        total_routes += plan.total_routes
        total_distance += plan.total_distance_m

        planner = CoveragePlannerService(db)
        stats = planner._neighborhood_stats(goal.user_id, n) if n else {}

        neighborhoods.append(GoalNeighborhoodInfo(
            neighborhood_id=plan.neighborhood_id,
            neighborhood_name=n.name if n else "Unknown",
            current_coverage_pct=plan.initial_coverage_pct,
            untraveled_streets=stats.get("untraveled_count", 0),
            untraveled_distance_m=stats.get("untraveled_distance", 0.0),
            plan_id=plan.id,
            plan_status=plan.status,
            estimated_routes=plan.total_routes,
        ))

    return CoverageGoalResponse(
        id=goal.id,
        city_id=goal.city_id,
        target_coverage_pct=goal.target_coverage_pct,
        current_coverage_pct=goal.current_coverage_pct,
        status=goal.status,
        total_routes=total_routes,
        total_distance_m=total_distance,
        neighborhoods=neighborhoods,
    ).model_dump()
