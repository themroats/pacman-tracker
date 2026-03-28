"""
GPX export service — converts RouteSuggestion geometry to GPX 1.1 files.

Produces a GPX track from the stored route_geometry LINESTRING so
users can import the exact route into OsmAnd, COROS, Garmin, etc.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import gpxpy
import gpxpy.gpx
from geoalchemy2.shape import to_shape

if TYPE_CHECKING:
    from app.models.route import RouteSuggestion


def build_gpx(suggestion: RouteSuggestion) -> str:
    """Convert a RouteSuggestion into a GPX 1.1 XML string.

    The stored ``route_geometry`` (LINESTRING, SRID=4326, ``overview=full``
    from OSRM) is dense enough for turn-by-turn navigation in apps like
    OsmAnd and breadcrumb navigation on Coros watches.

    Parameters
    ----------
    suggestion:
        A persisted RouteSuggestion with ``route_geometry`` populated.

    Returns
    -------
    str
        Valid GPX 1.1 XML.
    """
    gpx = gpxpy.gpx.GPX()
    gpx.creator = "Pacman Tracker"

    # -- metadata --
    created = suggestion.created_at or datetime.datetime.now(datetime.timezone.utc)
    dist_km = suggestion.distance_meters / 1000
    gpx.name = f"Pacman Route — {created.strftime('%Y-%m-%d %H:%M')}"
    gpx.description = (
        f"{dist_km:.1f} km route, "
        f"{suggestion.untraveled_ratio * 100:.0f}% untraveled streets"
    )
    gpx.time = created

    # -- track from stored geometry --
    line = to_shape(suggestion.route_geometry)
    track = gpxpy.gpx.GPXTrack()
    track.name = gpx.name
    gpx.tracks.append(track)

    segment = gpxpy.gpx.GPXTrackSegment()
    track.segments.append(segment)

    for coord in line.coords:
        # LINESTRING coords are (lng, lat [, z])
        lng, lat = coord[0], coord[1]
        segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lng))

    # -- start/end waypoints for easy reference --
    if len(line.coords) >= 2:
        start = line.coords[0]
        end = line.coords[-1]
        gpx.waypoints.append(
            gpxpy.gpx.GPXWaypoint(
                latitude=start[1], longitude=start[0], name="Start"
            )
        )
        gpx.waypoints.append(
            gpxpy.gpx.GPXWaypoint(
                latitude=end[1], longitude=end[0], name="End"
            )
        )

    return gpx.to_xml()
