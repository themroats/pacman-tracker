"""
Activity import pipeline — two-phase import strategy.

Phase A: Fetch activity list + detailed polylines (fast, gets routes on map)
Phase B: Fetch full GPS streams for accurate street matching (background)
"""

import asyncio
import datetime
import logging
from typing import Any

from shapely.geometry import LineString
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.user import User
from app.services.strava import RateLimitError, StravaOAuthService, TokenRevokedError

logger = logging.getLogger(__name__)

# T076: Exponential backoff settings
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 5


async def _retry_with_backoff(coro_factory, max_retries: int = MAX_RETRIES):
    """Execute an async callable with exponential backoff on rate-limit errors (T076).

    Args:
        coro_factory: A zero-arg callable that returns a new coroutine each call.
        max_retries: Maximum number of retries.

    Returns the result of the coroutine on success.
    Raises RateLimitError if all retries exhausted.
    """
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except RateLimitError as e:
            if attempt == max_retries:
                raise
            wait = min(e.retry_after, BASE_BACKOFF_SECONDS * (2**attempt))
            logger.warning(
                "Rate limited (attempt %d/%d), waiting %.0fs...",
                attempt + 1,
                max_retries,
                wait,
            )
            await asyncio.sleep(wait)


class ActivityImporter:
    """Manages the two-phase activity import pipeline."""

    def __init__(
        self,
        strava_service: StravaOAuthService | None = None,
        db_session: Session | None = None,
    ):
        self.strava = strava_service or StravaOAuthService()
        self.db = db_session

    async def import_phase_a(
        self,
        user_id: int,
        access_token: str | None = None,
    ) -> dict[str, int]:
        """
        Phase A: Fetch activity list and detailed polylines.

        Returns dict with counts: imported, skipped, total.
        """
        imported = 0
        skipped = 0

        if access_token is None:
            access_token = self._get_access_token(user_id)

        # Determine "after" timestamp for incremental sync
        last_activity = (
            self.db.query(Activity)
            .filter_by(user_id=user_id)
            .order_by(Activity.start_date.desc())
            .first()
        )
        after = None
        if last_activity:
            after = int(last_activity.start_date.timestamp())

        # Paginate through activities
        page = 1
        while True:
            activities = await self.strava.fetch_activity_list(
                access_token=access_token,
                page=page,
                per_page=200,
                after=after,
            )

            if not activities:
                break

            for act_data in activities:
                strava_id = act_data["id"]

                # Deduplication check
                existing = (
                    self.db.query(Activity)
                    .filter_by(strava_activity_id=strava_id)
                    .first()
                )
                if existing:
                    skipped += 1
                    continue

                # Fetch detailed polyline
                try:
                    detail = await self.strava.fetch_activity_detail(
                        access_token, strava_id
                    )
                except Exception:
                    detail = {}

                summary_polyline = act_data.get("map", {}).get("summary_polyline")
                detailed_polyline = detail.get("map", {}).get("polyline")

                activity = Activity(
                    user_id=user_id,
                    strava_activity_id=strava_id,
                    name=act_data.get("name", "Untitled"),
                    sport_type=act_data.get("sport_type", act_data.get("type", "Unknown")),
                    start_date=datetime.datetime.fromisoformat(
                        act_data["start_date"].replace("Z", "+00:00")
                    ),
                    distance_meters=act_data.get("distance", 0.0),
                    duration_seconds=act_data.get("elapsed_time", 0),
                    moving_time_seconds=act_data.get("moving_time", 0),
                    summary_polyline=summary_polyline,
                    detailed_polyline=detailed_polyline,
                    has_gps=bool(summary_polyline or detailed_polyline),
                    import_status="polyline_imported" if detailed_polyline else "pending",
                )
                self.db.add(activity)
                imported += 1

            page += 1

        if imported > 0:
            self.db.flush()

        return {"imported": imported, "skipped": skipped, "total": imported + skipped}

    async def import_phase_b(
        self,
        user_id: int,
        access_token: str | None = None,
    ) -> dict[str, int]:
        """
        Phase B: Fetch GPS streams for activities that have polylines,
        then run coverage matching against the street network.

        Returns dict with counts: processed, failed, matched.
        """
        processed = 0
        failed = 0
        matched = 0

        if access_token is None:
            access_token = self._get_access_token(user_id)

        # Get activities needing streams
        activities = (
            self.db.query(Activity)
            .filter_by(user_id=user_id, import_status="polyline_imported")
            .all()
        )

        for activity in activities:
            try:
                streams = await self.strava.fetch_activity_streams(
                    access_token, activity.strava_activity_id
                )

                latlng_data = streams.get("latlng", {}).get("data", [])
                if latlng_data and len(latlng_data) >= 2:
                    # Convert lat/lng to lng/lat for GeoJSON standard
                    coords = [(lng, lat) for lat, lng in latlng_data]
                    linestring = LineString(coords)
                    activity.gps_trace = f"SRID=4326;{linestring.wkt}"
                    activity.has_gps = True

                    # T078: GPS quality detection — flag activities with large gaps
                    _check_gps_quality(activity, latlng_data)
                else:
                    activity.has_gps = False

                activity.import_status = "streams_imported"
                processed += 1

                # --- Coverage matching (T045) ---
                if activity.has_gps and latlng_data and len(latlng_data) >= 2:
                    try:
                        from app.services.coverage import (
                            classify_activity_on_street,
                            run_coverage_matching,
                        )

                        coords_for_matching = [(lng, lat) for lat, lng in latlng_data]
                        gps_line = LineString(coords_for_matching)

                        overall_ratio = run_coverage_matching(
                            db=self.db,
                            user_id=user_id,
                            activity_id=activity.id,
                            gps_trace=gps_line,
                            city_id=activity.city_id,
                        )

                        # Classify on-street vs off-road (T099)
                        activity.is_on_street = classify_activity_on_street(overall_ratio)
                        activity.import_status = "matched"
                        matched += 1
                    except Exception:
                        # Coverage matching failure should not block the import
                        pass

            except RateLimitError:
                # Re-raise rate limits to let caller handle
                raise
            except Exception:
                failed += 1
                continue

        if processed > 0:
            self.db.flush()

        return {"processed": processed, "failed": failed, "matched": matched}

    def _get_access_token(self, user_id: int) -> str:
        """Retrieve and decrypt the access token for a user."""
        from app.services.crypto import decrypt_token

        user = self.db.query(User).get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        return decrypt_token(user.access_token_encrypted)


# ---------------------------------------------------------------------------
# T078: GPS quality detection
# ---------------------------------------------------------------------------

# Max distance (meters) between consecutive GPS points before flagging as a gap
GPS_GAP_THRESHOLD_METERS = 500.0
# If more than this fraction of points have large gaps, flag the activity
GPS_GAP_RATIO_THRESHOLD = 0.1


def _haversine_approx(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Approximate distance in meters between two lat/lng points."""
    import math

    R = 6_371_000  # Earth radius in meters
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _check_gps_quality(activity: Activity, latlng_data: list[list[float]]) -> None:
    """Flag activity if GPS data has significant gaps (T078).

    Sets activity.import_status to 'gps_quality_warning' if too many gaps detected.
    Does NOT prevent further processing — it's just a flag for user review.
    """
    if len(latlng_data) < 3:
        return

    gap_count = 0
    for i in range(1, len(latlng_data)):
        lat1, lng1 = latlng_data[i - 1]
        lat2, lng2 = latlng_data[i]
        dist = _haversine_approx(lat1, lng1, lat2, lng2)
        if dist > GPS_GAP_THRESHOLD_METERS:
            gap_count += 1

    gap_ratio = gap_count / (len(latlng_data) - 1)
    if gap_ratio > GPS_GAP_RATIO_THRESHOLD:
        logger.warning(
            "Activity %s has GPS quality issues: %d gaps (%.1f%% of segments)",
            activity.strava_activity_id,
            gap_count,
            gap_ratio * 100,
        )
        # Don't override an already better status — just add metadata info
        # The activity can still be processed but users should be warned
