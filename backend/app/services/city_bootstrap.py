"""Background bootstrap for initial city catalog loading."""

from __future__ import annotations

import logging
import threading

from app.config import get_settings
from app.database import get_session_factory
from app.models.city import City
from app.scripts.load_cities import load_all_cities

logger = logging.getLogger(__name__)

_state_lock = threading.Lock()
_state = {
    "started": False,
    "in_progress": False,
    "failed": False,
    "error": None,
}


def _state_payload(status: str, error: str | None) -> dict[str, str | bool | None]:
    return {
        "status": status,
        "in_progress": status == "loading",
        "error": error,
    }


def _has_city_data() -> bool:
    session = get_session_factory()()
    try:
        return session.query(City.id).first() is not None
    finally:
        session.close()


def _set_state(**updates) -> None:
    with _state_lock:
        _state.update(updates)


def get_city_bootstrap_state() -> dict[str, str | bool | None]:
    if _has_city_data():
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
    try:
        logger.info("Starting initial city bootstrap%s", f" for {target_city}" if target_city else "")
        load_all_cities(target_city)
        if not _has_city_data():
            raise RuntimeError("city bootstrap finished without loading any city data")
        _set_state(in_progress=False, failed=False, error=None)
        logger.info("Initial city bootstrap completed")
    except Exception as exc:
        logger.exception("Initial city bootstrap failed")
        _set_state(in_progress=False, failed=True, error=str(exc))


def start_city_bootstrap(target_city: str | None = None, *, force: bool = False) -> dict[str, str | bool | None]:
    if _has_city_data() and not force:
        return get_city_bootstrap_state()

    with _state_lock:
        if _state["in_progress"]:
            return _state_payload("loading", _state["error"])

        _state.update(
            {
                "started": True,
                "in_progress": True,
                "failed": False,
                "error": None,
            }
        )

    thread = threading.Thread(
        target=_run_bootstrap,
        args=(target_city,),
        name="city-bootstrap",
        daemon=True,
    )
    thread.start()

    return _state_payload("loading", None)


def ensure_city_bootstrap_started() -> dict[str, str | bool | None]:
    settings = get_settings()
    if not settings.auto_load_cities_on_empty_db:
        return get_city_bootstrap_state()

    if _has_city_data():
        return get_city_bootstrap_state()

    target_city = settings.auto_load_city_name.strip() or None
    return start_city_bootstrap(target_city)


def reset_city_bootstrap_state() -> None:
    _set_state(started=False, in_progress=False, failed=False, error=None)