"""Pacman Tracker MCP Server — tools and resources for street coverage tracking."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from pacman_mcp.auth import authenticate
from pacman_mcp.client import PacmanClient

logger = logging.getLogger(__name__)

mcp = FastMCP("Pacman Tracker")

# Lazy-initialized client (set on first tool/resource call)
_client: PacmanClient | None = None


async def _get_client() -> PacmanClient:
    """Get or create the authenticated API client."""
    global _client
    if _client is None:
        token = await authenticate()
        _client = PacmanClient(token)
    return _client


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def lookup_location(query: str) -> str:
    """Look up a city or neighborhood by name.

    Returns matching cities and neighborhoods with their IDs and coverage
    percentages. Use this to find IDs before calling get_coverage_summary.

    Args:
        query: City or neighborhood name (case-insensitive substring match).
    """
    client = await _get_client()
    q = query.lower()

    try:
        cities_data = await client.list_cities()
    except Exception as e:
        return f"Error connecting to backend: {e}"

    results: list[str] = []

    # Search cities
    matching_cities = [
        c for c in cities_data.get("cities", [])
        if q in c["name"].lower()
    ]

    for city in matching_cities:
        results.append(
            f"City: {city['name']} (ID: {city['id']}) — "
            f"{city.get('total_street_segments', '?')} streets, "
            f"{city.get('total_neighborhoods', '?')} neighborhoods"
        )

        # Also fetch neighborhoods for matching cities
        try:
            nh_data = await client.list_neighborhoods(city["id"])
            for nh in nh_data.get("neighborhoods", []):
                results.append(
                    f"  Neighborhood: {nh['name']} (ID: {nh['id']}) — "
                    f"{nh['coverage_percentage']}% covered"
                )
        except Exception:
            pass

    # Search neighborhoods across all cities (if query doesn't match a city)
    if not matching_cities:
        for city in cities_data.get("cities", []):
            try:
                nh_data = await client.list_neighborhoods(city["id"])
                matching_nhs = [
                    nh for nh in nh_data.get("neighborhoods", [])
                    if q in nh["name"].lower()
                ]
                for nh in matching_nhs:
                    results.append(
                        f"Neighborhood: {nh['name']} (ID: {nh['id']}) in {city['name']} — "
                        f"{nh['coverage_percentage']}% covered"
                    )
            except Exception:
                pass

    if not results:
        return f"No cities or neighborhoods found matching '{query}'."

    return "\n".join(results)


@mcp.tool()
async def get_coverage_summary(
    city: str | None = None,
    neighborhood: str | None = None,
) -> str:
    """Get street coverage statistics for a city or neighborhood.

    Provide either a city name or neighborhood name (or both to disambiguate).
    Returns coverage percentage, street counts, distance walked, and milestone
    proximity.

    Args:
        city: City name (optional, case-insensitive).
        neighborhood: Neighborhood name (optional, case-insensitive).
    """
    if not city and not neighborhood:
        return "Please provide a city name, neighborhood name, or both."

    client = await _get_client()

    try:
        cities_data = await client.list_cities()
    except Exception as e:
        return f"Error connecting to backend: {e}"

    all_cities = cities_data.get("cities", [])

    # --- Resolve city ---
    matched_city = None
    if city:
        q = city.lower()
        matches = [c for c in all_cities if q in c["name"].lower()]
        if not matches:
            return f"No city found matching '{city}'. Use lookup_location to find available cities."
        if len(matches) > 1:
            names = ", ".join(c["name"] for c in matches)
            return f"Multiple cities match '{city}': {names}. Please be more specific."
        matched_city = matches[0]

    # --- Neighborhood-only query (search all cities) ---
    if neighborhood and not matched_city:
        q = neighborhood.lower()
        for c in all_cities:
            try:
                nh_data = await client.list_neighborhoods(c["id"])
                matches = [n for n in nh_data.get("neighborhoods", []) if q in n["name"].lower()]
                if matches:
                    if len(matches) > 1:
                        names = ", ".join(n["name"] for n in matches)
                        return f"Multiple neighborhoods match '{neighborhood}' in {c['name']}: {names}. Please be more specific."
                    nh = matches[0]
                    return await _format_neighborhood_coverage(client, nh, c["name"])
            except Exception:
                pass
        return f"No neighborhood found matching '{neighborhood}'. Use lookup_location to find available neighborhoods."

    # --- City-level (with optional neighborhood filter) ---
    if neighborhood:
        q = neighborhood.lower()
        try:
            nh_data = await client.list_neighborhoods(matched_city["id"])
            matches = [n for n in nh_data.get("neighborhoods", []) if q in n["name"].lower()]
            if not matches:
                return f"No neighborhood matching '{neighborhood}' in {matched_city['name']}."
            if len(matches) > 1:
                names = ", ".join(n["name"] for n in matches)
                return f"Multiple neighborhoods match: {names}. Please be more specific."
            nh = matches[0]
            return await _format_neighborhood_coverage(client, nh, matched_city["name"])
        except Exception as e:
            return f"Error: {e}"

    # City-level coverage
    try:
        cov = await client.city_coverage(matched_city["id"])
    except Exception as e:
        return f"Error fetching coverage: {e}"

    return _format_city_coverage(cov)


def _format_city_coverage(cov: dict) -> str:
    """Format city coverage data into a readable string."""
    c = cov["city"]
    lines = [
        f"# {c['name']} — {c['coverage_percentage']}% covered",
        f"Streets: {c['streets_traveled']:,} / {c['streets_total']:,}",
        f"Distance: {c['distance_traveled_m'] / 1000:.1f} km / {c['distance_total_m'] / 1000:.1f} km",
        "",
        "## Neighborhoods",
    ]

    neighborhoods = sorted(cov.get("neighborhoods", []), key=lambda n: -n["coverage_percentage"])
    for n in neighborhoods:
        bar = _progress_bar(n["coverage_percentage"])
        lines.append(f"  {bar} {n['coverage_percentage']:5.1f}%  {n['name']} ({n['streets_traveled']}/{n['streets_total']})")

    # Milestone proximity
    pct = c["coverage_percentage"]
    next_milestone = next((m for m in [25, 50, 75, 100] if m > pct), None)
    if next_milestone:
        streets_needed = int((next_milestone / 100 * c["streets_total"]) - c["streets_traveled"])
        lines.append(f"\nNext milestone: {next_milestone}% — ~{streets_needed} more streets needed")

    return "\n".join(lines)


async def _format_neighborhood_coverage(client: PacmanClient, nh: dict, city_name: str) -> str:
    """Format neighborhood coverage."""
    try:
        detail = await client.neighborhood_coverage(nh["id"])
        n = detail["neighborhood"]
    except Exception:
        n = nh

    pct = n.get("coverage_percentage", nh.get("coverage_percentage", 0))
    traveled = n.get("streets_traveled", nh.get("streets_traveled", "?"))
    total = n.get("streets_total", nh.get("streets_total", "?"))

    lines = [
        f"# {n.get('name', nh['name'])} ({city_name}) — {pct}% covered",
        f"Streets: {traveled} / {total}",
    ]

    # Milestone proximity
    if isinstance(total, int) and isinstance(traveled, int) and total > 0:
        next_milestone = next((m for m in [25, 50, 75, 100] if m > pct), None)
        if next_milestone:
            streets_needed = int((next_milestone / 100 * total) - traveled)
            lines.append(f"Next milestone: {next_milestone}% — ~{streets_needed} more streets needed")

    return "\n".join(lines)


def _progress_bar(pct: float, width: int = 10) -> str:
    """Generate a text progress bar."""
    filled = int(pct / 100 * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


@mcp.tool()
async def get_untraveled_streets(
    neighborhood: str | None = None,
    city: str | None = None,
    limit: int = 20,
) -> str:
    """Get a list of untraveled streets in a neighborhood or city.

    Returns street names, lengths, and types grouped by name. A neighborhood
    is required (either directly or to narrow results within a city) because
    a full city can have 100k+ untraveled streets.

    Args:
        neighborhood: Neighborhood name (required unless city has few streets).
        city: City name (optional, helps disambiguate neighborhoods).
        limit: Max number of street groups to return (default 20).
    """
    client = await _get_client()

    try:
        cities_data = await client.list_cities()
    except Exception as e:
        return f"Error connecting to backend: {e}"

    all_cities = cities_data.get("cities", [])

    # Resolve city
    matched_city = None
    if city:
        q = city.lower()
        matches = [c for c in all_cities if q in c["name"].lower()]
        if not matches:
            return f"No city found matching '{city}'."
        if len(matches) > 1:
            return f"Multiple cities match '{city}': {', '.join(c['name'] for c in matches)}."
        matched_city = matches[0]

    # Resolve neighborhood
    matched_nh = None
    search_cities = [matched_city] if matched_city else all_cities
    if neighborhood:
        q = neighborhood.lower()
        for c in search_cities:
            try:
                nh_data = await client.list_neighborhoods(c["id"])
                matches = [n for n in nh_data.get("neighborhoods", []) if q in n["name"].lower()]
                if matches:
                    if len(matches) > 1:
                        return f"Multiple neighborhoods match: {', '.join(n['name'] for n in matches)}."
                    matched_nh = matches[0]
                    matched_city = c
                    break
            except Exception:
                pass
        if not matched_nh:
            return f"No neighborhood found matching '{neighborhood}'."

    if not matched_city:
        return "Please specify a city or neighborhood."
    if not matched_nh:
        return f"Please specify a neighborhood within {matched_city['name']} — a full city has too many streets to list."

    # Fetch untraveled streets
    try:
        geojson = await client.city_streets(
            matched_city["id"],
            neighborhood_id=matched_nh["id"],
            status="untraveled",
        )
    except Exception as e:
        return f"Error fetching streets: {e}"

    features = geojson.get("features", [])
    if not features:
        return f"No untraveled streets in {matched_nh['name']}! You've covered it all."

    # Group by street name
    by_name: dict[str, dict] = {}
    for f in features:
        props = f.get("properties", {})
        name = props.get("name") or "(unnamed)"
        if name not in by_name:
            by_name[name] = {"segments": 0, "length_m": 0.0, "types": set()}
        by_name[name]["segments"] += 1
        by_name[name]["length_m"] += props.get("length_meters", 0)
        by_name[name]["types"].add(props.get("highway_type", "unknown"))

    # Sort by total length descending
    sorted_streets = sorted(by_name.items(), key=lambda x: -x[1]["length_m"])
    total_length = sum(s[1]["length_m"] for s in sorted_streets)

    lines = [
        f"# Untraveled streets in {matched_nh['name']}",
        f"{len(features)} segments across {len(by_name)} unique streets ({total_length / 1000:.1f} km total)",
        "",
    ]

    for name, info in sorted_streets[:limit]:
        length_str = (
            f"{info['length_m']:.0f}m" if info["length_m"] < 1000
            else f"{info['length_m'] / 1000:.1f}km"
        )
        seg_note = f" ({info['segments']} segments)" if info["segments"] > 1 else ""
        lines.append(f"- {name}: {length_str}{seg_note}")

    remaining = len(sorted_streets) - limit
    if remaining > 0:
        lines.append(f"\n... and {remaining} more streets")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Shared: resolve city by name
# ---------------------------------------------------------------------------


async def _resolve_city(client: PacmanClient, city_name: str) -> tuple[dict | None, str | None]:
    """Resolve a city name to a city dict. Returns (city, error_msg)."""
    try:
        cities_data = await client.list_cities()
    except Exception as e:
        return None, f"Error connecting to backend: {e}"
    all_cities = cities_data.get("cities", [])
    q = city_name.lower()
    matches = [c for c in all_cities if q in c["name"].lower()]
    if not matches:
        return None, f"No city found matching '{city_name}'. Use lookup_location to find available cities."
    if len(matches) > 1:
        return None, f"Multiple cities match '{city_name}': {', '.join(c['name'] for c in matches)}."
    return matches[0], None


@mcp.tool()
async def get_progress_summary(city: str) -> str:
    """Get coverage progress timeline and milestones for a city.

    Shows how coverage has changed over time with dates, milestone achievements,
    and current trajectory.

    Args:
        city: City name (case-insensitive).
    """
    client = await _get_client()
    matched_city, err = await _resolve_city(client, city)
    if err:
        return err

    try:
        data = await client.city_progress(matched_city["id"])
    except Exception as e:
        return f"Error fetching progress: {e}"

    lines = [
        f"# {data['city_name']} — Progress Summary",
        f"Current coverage: {data['current_coverage_percentage']}%",
        "",
    ]

    # Milestones
    milestones = data.get("milestones", [])
    reached = [m for m in milestones if m["reached"]]
    upcoming = [m for m in milestones if not m["reached"]]

    if reached:
        lines.append("## Milestones Reached")
        for m in reached:
            nh = f" (in {m['neighborhood_name']})" if m.get("neighborhood_name") else ""
            lines.append(f"  {m['label']}{nh} — {m.get('date', '?')}")
        lines.append("")

    if upcoming:
        lines.append("## Upcoming Milestones")
        for m in upcoming:
            lines.append(f"  {m['label']} — not yet reached")
        lines.append("")

    # Timeline (last 10 data points)
    timeline = data.get("timeline", [])
    if timeline:
        lines.append("## Recent Timeline")
        for entry in timeline[-10:]:
            lines.append(
                f"  {entry['date']}: {entry['coverage_percentage']}% "
                f"({entry['streets_traveled']:,} streets)"
            )

        # Growth rate
        if len(timeline) >= 2:
            first, last = timeline[0], timeline[-1]
            pct_change = last["coverage_percentage"] - first["coverage_percentage"]
            street_change = last["streets_traveled"] - first["streets_traveled"]
            lines.append(f"\nGrowth: +{pct_change:.1f}% ({street_change:+,} streets) since {first['date']}")

    return "\n".join(lines)


@mcp.tool()
async def get_neighborhood_priority(city: str, limit: int = 10) -> str:
    """Rank neighborhoods by strategic priority for completion.

    Neighborhoods are ranked by how close they are to the next milestone
    (25/50/75/100%), making it easy to decide where to walk next for maximum
    milestone progress.

    Args:
        city: City name (case-insensitive).
        limit: Max number of neighborhoods to show (default 10).
    """
    client = await _get_client()
    matched_city, err = await _resolve_city(client, city)
    if err:
        return err

    try:
        cov = await client.city_coverage(matched_city["id"])
    except Exception as e:
        return f"Error fetching coverage: {e}"

    neighborhoods = cov.get("neighborhoods", [])
    if not neighborhoods:
        return f"No neighborhoods found in {matched_city['name']}."

    # For each neighborhood, calculate distance to next milestone
    scored: list[tuple[dict, int, float, int]] = []  # (nh, next_ms, gap_pct, streets_needed)
    for n in neighborhoods:
        pct = n["coverage_percentage"]
        total = n["streets_total"]
        traveled = n["streets_traveled"]

        if pct >= 100 or total == 0:
            continue

        next_ms = next((m for m in [25, 50, 75, 100] if m > pct), 100)
        streets_for_ms = int((next_ms / 100 * total) - traveled)
        gap_pct = next_ms - pct

        scored.append((n, next_ms, gap_pct, streets_for_ms))

    if not scored:
        return f"All neighborhoods in {matched_city['name']} are 100% complete!"

    # Sort by fewest streets needed to reach next milestone
    scored.sort(key=lambda x: x[3])

    lines = [
        f"# Neighborhood Priority — {matched_city['name']}",
        "Ranked by fewest streets needed to reach the next milestone.",
        "",
    ]

    for n, next_ms, gap_pct, streets_needed in scored[:limit]:
        bar = _progress_bar(n["coverage_percentage"])
        lines.append(
            f"  {bar} {n['name']}: {n['coverage_percentage']}% "
            f"→ {next_ms}% needs ~{streets_needed} streets ({gap_pct:.1f}% gap)"
        )

    # Also note fully complete neighborhoods
    complete = [n for n in neighborhoods if n["coverage_percentage"] >= 100]
    if complete:
        lines.append(f"\n{len(complete)} neighborhood(s) fully complete")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("user://profile")
async def user_profile() -> str:
    """Current user profile with overall street coverage statistics.

    Provides: total activities, total distance, unique streets visited,
    and per-city coverage breakdown.
    """
    client = await _get_client()

    try:
        stats = await client.overall_stats()
    except PermissionError:
        return "Not authenticated. Please trigger a tool call to start authentication."
    except Exception as e:
        return f"Error fetching profile: {e}"

    lines = [
        "# Pacman Tracker Profile",
        f"Total activities: {stats['total_activities']}",
        f"Total distance: {stats['total_distance_meters'] / 1000:.1f} km",
        f"Unique streets visited: {stats['total_unique_streets']}",
        "",
        "## Cities",
    ]

    for city in stats.get("cities", []):
        lines.append(
            f"  {city['city_name']}: {city['coverage_percentage']}% "
            f"({city['streets_traveled']}/{city['streets_total']})"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server via stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
