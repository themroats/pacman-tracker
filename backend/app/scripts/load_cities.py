"""
City data loader script.

Downloads street networks from OSMnx, imports neighborhood boundaries,
and bulk-inserts data into SpatiaLite.

Usage: python -m app.scripts.load_cities [--city CITY_NAME]
"""

import datetime
import sys
from typing import Any

import geopandas as gpd
import osmnx as ox
from shapely.geometry import MultiPolygon
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import create_db_engine, get_session_factory
from app.models.city import City
from app.models.neighborhood import Neighborhood
from app.models.street import StreetSegment

# Launch cities with their projected CRS
LAUNCH_CITIES: list[dict[str, Any]] = [
    {"name": "Seattle", "state": "Washington", "projected_crs": "EPSG:2926"},
    # {"name": "Pittsburgh", "state": "Pennsylvania", "projected_crs": "EPSG:2272"},
    # {"name": "Chicago", "state": "Illinois", "projected_crs": "EPSG:3435"},
    # {"name": "New York", "state": "New York", "projected_crs": "EPSG:2263"},
    # {"name": "San Francisco", "state": "California", "projected_crs": "EPSG:2227"},
]


def get_city_boundary(city_name: str, state: str) -> MultiPolygon:
    """Download city boundary polygon from OSMnx."""
    place = f"{city_name}, {state}, USA"
    gdf = ox.geocode_to_gdf(place)
    geom = gdf.geometry.iloc[0]
    if geom.geom_type == "Polygon":
        geom = MultiPolygon([geom])
    return geom


def download_street_network(city_name: str, state: str) -> gpd.GeoDataFrame:
    """
    Download the walkable street network for a city using OSMnx.

    Returns a GeoDataFrame of edges (street segments).
    """
    place = f"{city_name}, {state}, USA"
    print(f"  Downloading street network for {place}...")
    graph = ox.graph_from_place(place, network_type="walk")
    edges = ox.graph_to_gdfs(graph, nodes=False)
    return edges


def load_city(session: Session, city_info: dict[str, Any]) -> City:
    """Load a single city: boundary, streets, and optionally neighborhoods."""
    city_name = city_info["name"]
    state = city_info["state"]
    projected_crs = city_info["projected_crs"]

    print(f"\n--- Loading {city_name}, {state} ---")

    # Check if city already exists
    existing = session.query(City).filter_by(name=city_name, state=state).first()
    if existing:
        print(f"  City {city_name} already exists (id={existing.id}), skipping.")
        return existing

    # 1. Get city boundary
    print(f"  Fetching boundary...")
    boundary = get_city_boundary(city_name, state)

    city = City(
        name=city_name,
        state=state,
        country="US",
        boundary=f"SRID=4326;{boundary.wkt}",
        projected_crs=projected_crs,
        osm_data_updated_at=datetime.datetime.now(datetime.UTC),
    )
    session.add(city)
    session.flush()  # Get city.id

    # 2. Download street network
    edges = download_street_network(city_name, state)
    print(f"  Downloaded {len(edges)} street segments")

    # Project to local CRS for accurate length calculation
    print(f"  Projecting to {projected_crs} for length calculation...")
    edges_projected = edges.to_crs(projected_crs)

    # 3. Bulk insert street segments
    print(f"  Building segment objects...")
    segments: list[StreetSegment] = []
    skipped = 0
    total = len(edges)
    for idx, (_, row) in enumerate(edges.iterrows()):
        if (idx + 1) % 50_000 == 0 or idx == 0:
            print(f"    Processing edge {idx + 1}/{total} ({(idx + 1) * 100 // total}%)...")

        geom = row.geometry
        if geom.geom_type != "LineString":
            skipped += 1
            continue

        # Get projected length
        proj_row = edges_projected.iloc[idx] if idx < len(edges_projected) else None
        length_m = proj_row.geometry.length if proj_row is not None else geom.length * 111_000

        segment = StreetSegment(
            city_id=city.id,
            osm_way_id=row.get("osmid", 0) if not isinstance(row.get("osmid"), list) else row["osmid"][0],
            osm_node_start=row.name[0] if isinstance(row.name, tuple) else 0,
            osm_node_end=row.name[1] if isinstance(row.name, tuple) else 0,
            name=row.get("name") if isinstance(row.get("name"), str) else None,
            highway_type=row.get("highway", "unclassified") if isinstance(row.get("highway"), str) else "unclassified",
            geometry=f"SRID=4326;{geom.wkt}",
            length_meters=length_m,
        )
        segments.append(segment)

    if skipped:
        print(f"  Skipped {skipped} non-LineString geometries")
    print(f"  Inserting {len(segments)} segments into database...")
    session.add_all(segments)
    session.flush()
    print(f"  Flush complete.")

    # 4. Update city cached counts
    city.total_street_segments = len(segments)
    city.total_street_length_m = sum(s.length_meters for s in segments)

    print(f"  Inserted {len(segments)} segments, total length: {city.total_street_length_m:.0f}m")

    return city


def load_all_cities(target_city: str | None = None) -> None:
    """Load all launch cities (or a specific one) into the database."""
    factory = get_session_factory()
    session = factory()

    try:
        cities_to_load = LAUNCH_CITIES
        if target_city:
            cities_to_load = [c for c in LAUNCH_CITIES if c["name"].lower() == target_city.lower()]
            if not cities_to_load:
                print(f"Unknown city: {target_city}")
                print(f"Available: {', '.join(c['name'] for c in LAUNCH_CITIES)}")
                return

        for city_info in cities_to_load:
            load_city(session, city_info)

        session.commit()
        print("\nAll cities loaded successfully.")
    except Exception as e:
        session.rollback()
        print(f"\nError loading cities: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    target = None
    if "--city" in sys.argv:
        idx = sys.argv.index("--city")
        if idx + 1 < len(sys.argv):
            target = sys.argv[idx + 1]
    load_all_cities(target)
