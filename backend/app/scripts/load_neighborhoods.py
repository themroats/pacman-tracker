"""
Load neighborhood boundaries for cities.

Fetches named neighborhoods from OSM (points + polygons), creates Voronoi
tessellation from their centroids, clips to the city boundary, and inserts
Neighborhood records.  Then spatially assigns street segments.

Usage: python -m app.scripts.load_neighborhoods [--city CITY_NAME]
"""

from __future__ import annotations

import sys
import datetime

import geopandas as gpd
import numpy as np
import osmnx as ox
from shapely.geometry import MultiPoint, MultiPolygon, Polygon, Point
from shapely.ops import voronoi_diagram
from sqlalchemy import text, func as sqlfunc
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.database import create_db_engine, get_session_factory
from app.models.city import City
from app.models.neighborhood import Neighborhood
from app.models.street import StreetSegment


def _fetch_neighborhood_points(city_name: str, state: str) -> list[dict]:
    """Fetch named neighborhoods from OSM and return centroid + name pairs."""
    place = f"{city_name}, {state}, USA"
    print(f"  Fetching OSM neighborhood features for {place}...")

    all_features: list[dict] = []
    seen_names: set[str] = set()

    # Try multiple OSM tags that carry neighborhood info
    tag_sets = [
        {"place": "neighbourhood"},
        {"admin_level": "10"},
        {"place": "suburb"},
    ]

    for tags in tag_sets:
        try:
            gdf = ox.features_from_place(place, tags=tags)
        except Exception:
            continue

        for _, row in gdf.iterrows():
            name = row.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            name = name.strip()
            if name in seen_names:
                continue
            seen_names.add(name)

            geom = row.geometry
            centroid = geom.centroid
            all_features.append({"name": name, "centroid": centroid, "geometry": geom})

    print(f"  Found {len(all_features)} unique named neighborhoods")
    return all_features


def _voronoi_neighborhoods(
    features: list[dict],
    city_boundary: MultiPolygon | Polygon,
) -> list[dict]:
    """Create Voronoi-based neighborhood polygons clipped to the city boundary."""
    if not features:
        return []

    # Collect centroids
    points = [f["centroid"] for f in features]
    multi_pt = MultiPoint(points)

    print(f"  Computing Voronoi tessellation from {len(points)} centroids...")
    voronoi_result = voronoi_diagram(multi_pt, envelope=city_boundary)

    # Match each Voronoi cell to its source neighborhood
    results: list[dict] = []
    used_cells: set[int] = set()

    for feat in features:
        pt = feat["centroid"]
        best_idx = -1
        for i, cell in enumerate(voronoi_result.geoms):
            if i in used_cells:
                continue
            if cell.contains(pt):
                best_idx = i
                break

        if best_idx == -1:
            # Fallback: find nearest cell
            min_dist = float("inf")
            for i, cell in enumerate(voronoi_result.geoms):
                if i in used_cells:
                    continue
                d = cell.distance(pt)
                if d < min_dist:
                    min_dist = d
                    best_idx = i

        if best_idx == -1:
            continue

        used_cells.add(best_idx)
        cell = voronoi_result.geoms[best_idx]

        # Clip to city boundary
        clipped = cell.intersection(city_boundary)
        if clipped.is_empty:
            continue

        # Normalize to MultiPolygon
        if clipped.geom_type == "Polygon":
            clipped = MultiPolygon([clipped])
        elif clipped.geom_type == "MultiPolygon":
            pass
        elif clipped.geom_type == "GeometryCollection":
            polys = [g for g in clipped.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
            if not polys:
                continue
            clipped = MultiPolygon(
                [p for g in polys for p in (g.geoms if g.geom_type == "MultiPolygon" else [g])]
            )
        else:
            continue

        results.append({"name": feat["name"], "boundary": clipped})

    print(f"  Created {len(results)} Voronoi neighborhood polygons")
    return results


def load_neighborhoods_for_city(
    session: Session,
    city: City,
    *,
    commit_every: int = 10,
    progress_callback: Callable[[dict[str, int]], None] | None = None,
) -> dict[str, int]:
    """Load neighborhoods for a city and assign streets.

    Commits progress in batches to avoid holding SQLite writer locks for the
    entire neighborhood assignment run.
    """
    city_name = city.name
    state = city.state or ""
    print(f"\n--- Loading neighborhoods for {city_name}, {state} ---")

    # Check if neighborhoods already exist
    existing = session.query(Neighborhood).filter_by(city_id=city.id).count()
    if existing > 0:
        print(f"  {existing} neighborhoods already exist. Skipping.")
        return {
            "loaded": existing,
            "total": existing,
            "processed": existing,
            "assigned": 0,
            "unassigned": 0,
        }

    # Get city boundary as Shapely
    from geoalchemy2.shape import to_shape
    city_boundary = to_shape(city.boundary)

    # Fetch OSM neighborhood info
    features = _fetch_neighborhood_points(city_name, state)
    if not features:
        print("  No neighborhood data found in OSM.")
        return {"loaded": 0, "total": 0, "processed": 0, "assigned": 0, "unassigned": 0}

    # Create Voronoi polygons
    neighborhoods = _voronoi_neighborhoods(features, city_boundary)
    if not neighborhoods:
        print("  Failed to create neighborhood polygons.")
        return {"loaded": 0, "total": 0, "processed": 0, "assigned": 0, "unassigned": 0}

    # Insert Neighborhood records
    print(f"  Inserting {len(neighborhoods)} neighborhoods...")
    neighborhood_objs: list[Neighborhood] = []
    for n in neighborhoods:
        obj = Neighborhood(
            city_id=city.id,
            name=n["name"],
            boundary=f"SRID=4326;{n['boundary'].wkt}",
            total_street_segments=0,
            total_street_length_m=0.0,
        )
        session.add(obj)
        neighborhood_objs.append(obj)

    session.flush()  # Get IDs
    session.commit()
    print(f"  Inserted {len(neighborhood_objs)} neighborhoods")

    total_neighborhoods = len(neighborhood_objs)
    if progress_callback:
        progress_callback(
            {
                "loaded": total_neighborhoods,
                "total": total_neighborhoods,
                "processed": 0,
                "assigned": 0,
                "unassigned": 0,
            }
        )

    # Assign streets to neighborhoods using SpatiaLite R-tree spatial index
    print("  Assigning streets to neighborhoods (R-tree + ST_Within)...")
    assigned = 0
    for i, (nb, n_data) in enumerate(zip(neighborhood_objs, neighborhoods), 1):
        shape = n_data["boundary"]  # Shapely MultiPolygon (already in memory)
        bounds = shape.bounds  # (minx, miny, maxx, maxy)

        result = session.execute(
            text(
                "UPDATE street_segments SET neighborhood_id = :nb_id "
                "WHERE city_id = :city_id "
                "AND neighborhood_id IS NULL "
                "AND ROWID IN ("
                "  SELECT ROWID FROM SpatialIndex "
                "  WHERE f_table_name='street_segments' "
                "  AND f_geometry_column='geometry' "
                "  AND search_frame=BuildMbr(:minx, :miny, :maxx, :maxy, 4326)"
                ") "
                "AND ST_Within(ST_Centroid(geometry), GeomFromText(:nb_wkt, 4326))"
            ),
            {
                "nb_id": nb.id,
                "city_id": city.id,
                "minx": bounds[0],
                "miny": bounds[1],
                "maxx": bounds[2],
                "maxy": bounds[3],
                "nb_wkt": shape.wkt,
            },
        )
        count = result.rowcount
        assigned += count

        # Update cached counts
        nb.total_street_segments = count
        length_sum = (
            session.query(sqlfunc.coalesce(sqlfunc.sum(StreetSegment.length_meters), 0))
            .filter_by(neighborhood_id=nb.id)
            .scalar()
        )
        nb.total_street_length_m = float(length_sum)

        if (i % 20 == 0) or i == len(neighborhood_objs):
            print(f"    [{i}/{len(neighborhood_objs)}] assigned {assigned} streets so far...")

        if progress_callback:
            progress_callback(
                {
                    "loaded": total_neighborhoods,
                    "total": total_neighborhoods,
                    "processed": i,
                    "assigned": assigned,
                    "unassigned": 0,
                }
            )

        if i % commit_every == 0:
            session.commit()

    session.flush()
    session.commit()

    # Count unassigned streets
    unassigned = (
        session.query(StreetSegment)
        .filter_by(city_id=city.id, neighborhood_id=None)
        .count()
    )

    print(f"  Assigned {assigned} streets to neighborhoods")
    if unassigned > 0:
        print(f"  {unassigned} streets remain unassigned (outside all neighborhood boundaries)")

    result = {
        "loaded": total_neighborhoods,
        "total": total_neighborhoods,
        "processed": total_neighborhoods,
        "assigned": assigned,
        "unassigned": unassigned,
    }
    if progress_callback:
        progress_callback(result)
    return result


def main(target_city: str | None = None) -> None:
    """Load neighborhoods for all cities (or a specific one)."""
    factory = get_session_factory()
    session = factory()

    try:
        query = session.query(City)
        if target_city:
            query = query.filter(sqlfunc.lower(City.name) == target_city.lower())

        cities = query.all()
        if not cities:
            print(f"No cities found{f' matching {target_city!r}' if target_city else ''}.")
            return

        total = 0
        for city in cities:
            result = load_neighborhoods_for_city(session, city)
            total += result["loaded"]

        session.commit()
        print(f"\nDone. Loaded {total} neighborhoods total.")

    except Exception as e:
        session.rollback()
        print(f"\nError: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    target = None
    if "--city" in sys.argv:
        idx = sys.argv.index("--city")
        if idx + 1 < len(sys.argv):
            target = sys.argv[idx + 1]
    main(target)
