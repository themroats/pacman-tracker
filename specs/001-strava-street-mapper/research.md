# Research: Strava Street Mapper

**Feature**: 001-strava-street-mapper  
**Date**: 2026-02-28  
**Status**: Complete

## 1. Strava API Integration

### Decision: OAuth2 Authorization Code Flow + Webhooks

**Rationale**: Standard web app OAuth2 flow with 6-hour access tokens and refresh tokens. Strava's API terms require webhook subscription for real-time notifications.

**Key findings**:
- **Scope**: `activity:read_all` (not `activity:read`) — the `_all` variant is required to access "Only Me" privacy activities and privacy-zone-included GPS data, which are essential for complete street coverage
- **Endpoints**: `GET /athlete/activities` (list, `per_page=200`), `GET /activities/{id}` (detailed polyline), `GET /activities/{id}/streams` (raw `latlng` GPS coordinates)
- **Rate limits**: 100 requests/15 min (short-term), 1000 requests/day. A 500-activity import requires ~75 minutes with detail+stream fetches
- **GPS data tiers**: Summary polyline (lossy) → detailed polyline (~1.1m precision) → raw `latlng` streams (full GPS). Use streams for street matching accuracy
- **Webhooks**: One subscription per app; events contain only activity IDs (must fetch details separately). Implement webhook + polling fallback
- **Gotchas**: Some activities lack GPS (manual entries, indoor); detect via `start_latlng == null`. Token refresh must be atomic (always persist latest refresh token). `sport_type` field preferred over deprecated `type`

**Alternatives considered**:
- Polling only (simpler, but violates Strava API terms; less responsive)
- `activity:read` scope (would miss private activities, leaving coverage gaps)

### Decision: Two-Phase Import Strategy

**Rationale**: Respect rate limits while getting usable data to the user quickly.

- **Phase A**: Fetch activity list + detailed polylines (enough for map display)
- **Phase B**: Fetch GPS streams for street matching (can run in background)
- User sees their routes on the map within minutes; street coverage calculation continues asynchronously

---

## 2. Street Network & Geospatial Storage

### Decision: OSMnx `graph_from_place()` with `network_type="walk"` + SpatiaLite

**Rationale**: Walk network includes sidewalks and footways (relevant for runners), excludes motorways. SpatiaLite is sufficient for single-user local development.

**Key findings**:
- **Download**: `ox.graph_from_place("Seattle, Washington, USA", network_type="walk")`. NYC is the largest (~350K edges, 3–8 min download). Set Overpass timeout to 300s
- **Storage**: Convert graph to GeoDataFrame of edges via `ox.graph_to_gdfs()`, then store in SpatiaLite using raw SQL with `mod_spatialite` (GeoPandas `to_sql()` can't write SpatiaLite geometry natively)
- **GeoAlchemy2**: Works with SpatiaLite when `management=True` is set. ORM reads work fine; bulk inserts should use raw SQL for performance
- **Spatial indexes**: R-tree indexes via `SELECT CreateSpatialIndex('streets', 'geometry')` — 1000× speedup on spatial queries, mandatory
- **SpatiaLite vs PostGIS gaps**: No `ST_DWithin` (use `ST_Buffer` + `ST_Intersects` instead), no geography type (use projected CRS per city), single-writer only — all acceptable for single-user

**Alternatives considered**:
- PostgreSQL + PostGIS (production-grade but heavyweight for local dev; migration path preserved in data model)
- Flat file GeoJSON (no spatial indexing, too slow for matching)

### Decision: Buffer + Intersection for GPS Matching (15m buffer)

**Rationale**: A 15m buffer around GPS traces accounts for typical GPS drift (5–15m). Computing intersection length against each street segment gives exact coverage ratios.

- **Algorithm**: Buffer GPS LineString by 15m → intersect with each street segment → `intersection_length / street_length ≥ 0.80` → mark as "traveled"
- **Pre-compute at import time**: Store results in `user_street_coverage` table → dashboard queries become simple SQL aggregations (<100ms)
- **Batch performance**: 500 activities × NYC street network ≈ 15–30 minutes (one-time); incremental for new activities is seconds
- **Projected CRS**: Use per-city projected CRS for accurate distance calculations (e.g., EPSG:2926 for Seattle, EPSG:2263 for NYC)

**Alternatives considered**:
- Nearest-edge snapping via OSMnx `nearest_edges()` (faster but doesn't compute partial coverage)
- Hidden Markov Model map matching (most accurate but far more complex; overkill for 80% threshold)

### Decision: Civic Open Data for Neighborhood Boundaries

**Rationale**: OSM admin boundaries are incomplete for US neighborhoods. Official city data portals provide authoritative GeoJSON/Shapefile boundaries.

- Seattle: Seattle GeoData portal
- Pittsburgh: WPRDC (Western PA Regional Data Center)
- Chicago: Chicago Data Portal
- New York: NYC Open Data
- San Francisco: DataSF

Streets assigned to neighborhoods via centroid containment (v1 simplicity).

---

## 3. Routing Engine

### Decision: Self-Hosted OSRM via Docker with Foot Profile

**Rationale**: Free, open-source, fast routing with built-in TSP solver. No API key needed. ~100–200 MB RAM per city.

**Key findings**:
- **Setup**: Docker image `osrm/osrm-backend`, MLD algorithm, city-level OSM extracts from Geofabrik
- **Pipeline**: `osrm-extract` (foot.lua profile) → `osrm-partition` → `osrm-customize`
- **Route generation for untraveled streets**:
  1. Query SpatiaLite for untraveled streets in target area
  2. Select N midpoints as waypoints (prioritize longest untraveled segments)
  3. Call OSRM `/trip?roundtrip=true&source=first` for optimized loop
  4. Iteratively add/remove waypoints to hit ±10% of target distance (max 3 iterations)
- **API**: `/nearest` (snap to road), `/trip` (TSP), `/route` (fixed-order fallback). Use `geometries=geojson` to avoid polyline decoding
- Backend proxies all OSRM calls — frontend never calls OSRM directly

**Alternatives considered**:
- GraphHopper (TSP is paid/enterprise only)
- OSMnx + NetworkX shortest paths (too slow for interactive use; 10–30s per route vs OSRM's <100ms)
- Valhalla (viable upgrade path if isochrones needed later; more complex setup)
- Mapbox Directions API (proprietary, usage costs)

---

## 4. Frontend Map

### Decision: react-leaflet v4 + CartoDB Positron Basemap + Zustand

**Rationale**: Leaflet is free/open-source, lightweight, and has excellent OSM support. CartoDB Positron provides a light theme that maximizes contrast for colored street overlays. Zustand is minimal (1KB) with no re-render storms.

**Key findings**:
- **Performance**: `preferCanvas={true}` on `<MapContainer>` is critical — switches all vectors from DOM elements to a single canvas. Handles 500+ polylines smoothly
- **Bulk streets**: Use `<GeoJSON>` component for street segments (10K–50K features). Individual `<Polyline>` components for activity routes (≤500)
- **Layer management**: React conditional rendering over `<LayersControl>` for richer filter UX. `<GeoJSON key={dataHash}>` forces re-render on data change
- **Interactions**: `eventHandlers` on `<Polyline>`, `onEachFeature` on `<GeoJSON>`, `flyToBounds()` via headless bridge components using `useMap()` hook
- **State**: Zustand for app state (activities, filters, coverage data). Leaflet owns the viewport. Headless `<MapController>` component bridges React state → Leaflet map
- **Viewport optimization**: Only render features visible in current viewport bounds; hide street-level detail at low zoom levels

**Alternatives considered**:
- Mapbox GL JS (better vector tile performance, but requires API key and has free-tier limits)
- deck.gl (WebGL-powered, excellent for massive datasets, but more complex React integration)
- Redux (more boilerplate than Zustand for no benefit at this scale)
- React Context (causes re-render storms when map state changes frequently)

---

## 5. Open Questions Resolved

| Question | Resolution |
|----------|-----------|
| Authentication method | Strava OAuth2 only — no separate auth system |
| Geographic scope | Predefined: Seattle, Pittsburgh, Chicago, New York, San Francisco |
| Hosting | Local development only; hosting deferred |
| GPS matching threshold | 80% of street length via 15m buffer intersection |
| Neighborhood data source | Civic open data portals (not OSM) |
| Route generation | OSRM `/trip` with untraveled street midpoints as waypoints |
| Windows SpatiaLite | `mod_spatialite` available via conda-forge or pre-built binaries |
| Multi-activity cumulative coverage | Union all activity buffers first, then intersect per street |
