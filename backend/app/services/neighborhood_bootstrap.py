"""Background bootstrap for neighborhood loading."""

from __future__ import annotations

import logging
import threading

from sqlalchemy import func as sqlfunc

from app.database import get_session_factory
from app.models.city import City
from app.models.neighborhood import Neighborhood
from app.scripts.load_neighborhoods import load_neighborhoods_for_city

logger = logging.getLogger(__name__)

_state_lock = threading.Lock()
_state = {
    "started": False,
    "in_progress": False,
    "failed": False,
    "error": None,
    "city": None,
    "loaded": 0,
    "total": 0,
    "processed": 0,
    "assigned": 0,
    "unassigned": 0,
}


def _state_payload(status: str, error: str | None) -> dict[str, str | bool | int | None]:
    return {
        "status": status,
        "in_progress": status == "loading",
        "error": error,
        "city": _state["city"],
        "loaded": _state["loaded"],
        "total": _state["total"],
        "processed": _state["processed"],
        "assigned": _state["assigned"],
        "unassigned": _state["unassigned"],
    }


def _set_state(**updates) -> None:
    with _state_lock:
        _state.update(updates)


def _has_neighborhood_data(target_city: str | None = None) -> bool:
    session = get_session_factory()()
    try:
        query = session.query(Neighborhood.id)
        if target_city:
            query = query.join(City).filter(sqlfunc.lower(City.name) == target_city.lower())
        return query.first() is not None
    finally:
        session.close()


def get_neighborhood_bootstrap_state(target_city: str | None = None) -> dict[str, str | bool | int | None]:
    if _has_neighborhood_data(target_city):
        return _state_payload("ready", None)

    with _state_lock:
        if _state["in_progress"]:
            status = "loading"
        elif _state["failed"]:
            status = "failed"
        else:
            status = "idle"

        return _state_payload(status, _state["error"])


def _run_bootstrap(target_city: str | None) -> None:
    session = get_session_factory()()
    try:
        logger.info("Starting neighborhood bootstrap%s", f" for {target_city}" if target_city else "")

        query = session.query(City)
        if target_city:
            query = query.filter(sqlfunc.lower(City.name) == target_city.lower())

        cities = query.order_by(City.name).all()
        if not cities:
            raise RuntimeError(f"No cities found matching {target_city!r}" if target_city else "No cities found")

        total_loaded = 0

        def on_progress(progress: dict[str, int]) -> None:
            _set_state(
                city=target_city,
                loaded=total_loaded + progress["loaded"],
                total=total_loaded + progress["total"],
                processed=total_loaded + progress["processed"],
                assigned=progress["assigned"],
                unassigned=progress["unassigned"],
            )

        for city in cities:
            result = load_neighborhoods_for_city(session, city, progress_callback=on_progress)
            total_loaded += result["loaded"]

        _set_state(
            city=target_city,
            loaded=total_loaded,
            total=total_loaded,
            processed=total_loaded,
        )

        session.commit()

        if not _has_neighborhood_data(target_city):
            raise RuntimeError("neighborhood bootstrap finished without loading any neighborhoods")

        _set_state(in_progress=False, failed=False, error=None, city=target_city, loaded=total_loaded)
        logger.info("Neighborhood bootstrap completed")
    except Exception as exc:
        session.rollback()
        logger.exception("Neighborhood bootstrap failed")
        _set_state(in_progress=False, failed=True, error=str(exc), city=target_city)
    finally:
        session.close()


def start_neighborhood_bootstrap(
    target_city: str | None = None,
    *,
    force: bool = False,
) -> dict[str, str | bool | int | None]:
    if _has_neighborhood_data(target_city) and not force:
        return get_neighborhood_bootstrap_state(target_city)

    with _state_lock:
        if _state["in_progress"]:
            return _state_payload("loading", _state["error"])

        _state.update(
            {
                "started": True,
                "in_progress": True,
                "failed": False,
                "error": None,
                "city": target_city,
                "loaded": 0,
                "total": 0,
                "processed": 0,
                "assigned": 0,
                "unassigned": 0,
            }
        )

    thread = threading.Thread(
        target=_run_bootstrap,
        args=(target_city,),
        name="neighborhood-bootstrap",
        daemon=True,
    )
    thread.start()

    return _state_payload("loading", None)


def reset_neighborhood_bootstrap_state() -> None:
    _set_state(
        started=False,
        in_progress=False,
        failed=False,
        error=None,
        city=None,
        loaded=0,
        total=0,
        processed=0,
        assigned=0,
        unassigned=0,
    )