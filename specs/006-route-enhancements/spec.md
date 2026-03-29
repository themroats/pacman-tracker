# Feature Specification: Route Suggestion Enhancements

**Feature Branch**: `006-route-enhancements`
**Created**: 2026-03-28
**Updated**: 2026-03-29
**Status**: Implemented (partial)
**Input**: User description: "Brainstorm features related to route suggestions: randomized generation, route preferences, saved start points, complete-this-neighborhood mode, and optimal coverage planner"

### Implementation Summary

Features 1 (randomized routes) and 4 (coverage plans) were merged into a single greedy nearest-edge walk algorithm that replaces both the original deterministic waypoint selection and the proposed weighted random sampling. Feature 3 (saved start points) was implemented as designed. Features 2 (route preferences) and 5 (optimal coverage planner) are deferred.

Additional work completed: fixed `length_meters` data from US survey feet to true meters (Alembic migration), added OSRM `route_through()` for order-preserving routing, added chunked OSRM calls for >100 waypoints, and implemented coverage matching via 15m buffer with 80% threshold.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Greedy Coverage Walk ~~Randomized Route Generation~~ (Priority: P1) ✅ Implemented

As a runner, I want the app to generate routes that efficiently cover untraveled streets near my starting point, producing different routes each time by consuming available streets greedily.

**Original spec**: Weighted random sampling with a `variation` parameter. **What was built**: A greedy nearest-edge walk algorithm that starts from the user's chosen start point and repeatedly picks the nearest untraveled street by Euclidean distance. Each route in a plan consumes different streets, providing natural variety without explicit randomization. The `variation` parameter was prototyped and removed as unnecessary.

**Algorithm details**:
- Walks outbound until 80% of the target distance budget is consumed
- Stops adding streets at 120% of target distance
- Uses `length_meters` (now correctly stored in meters after data fix)
- Streets are credited as "covered" when `compute_coverage_ratio()` ≥ 80% (15m buffer)
- Subsequent routes in a plan skip streets already credited by earlier routes

**Acceptance Scenarios**:

1. **Given** a neighborhood with untraveled streets, **When** I generate a coverage plan, **Then** each route follows a greedy nearest-edge path from the start point.
2. **Given** a plan with multiple routes, **When** routes are generated sequentially, **Then** each route targets different streets than previous routes.
3. **Given** fewer untraveled streets than one route can cover, **When** I generate a plan, **Then** a single route covering everything is produced.
4. **Given** a target distance of 5km, **When** a route is generated, **Then** it uses approximately 80–120% of the target distance.

---

### User Story 2 — Route Preferences (Priority: P2) ⏸️ Deferred

> **Not implemented in this iteration.** Highway type preference weights remain a future enhancement. The greedy walk algorithm could incorporate preference weights as a multiplier on the distance score when selecting the next street.

---

### User Story 3 — Saved Favorite Start Points (Priority: P2) ✅ Implemented

As a runner, I want to save my home and other frequent starting locations so I don't have to click the map every time I want a route.

Implemented as designed. CRUD API for named start points with `is_default` flag. Start point is required when creating a coverage plan (`start_point_id` is a required field). Start points are displayed as markers on the coverage page map.

**Acceptance Scenarios**: All 5 original scenarios are met.

1. **Given** I click a point on the map, **When** I click "Save this point" and enter a name, **Then** the point is persisted and appears in my saved points dropdown.
2. **Given** I have a default start point, **When** I open the route suggestion page, **Then** my default start point coordinates are pre-populated.
3. **Given** I have 5 saved start points, **When** I view the dropdown, **Then** all 5 appear with their names and the default is highlighted.
4. **Given** I set a new point as default, **When** I confirm, **Then** the previous default is un-flagged and the new one is marked.
5. **Given** I delete a start point, **When** I confirm, **Then** it is removed and the dropdown updates.

---

### User Story 4 — "Complete This Neighborhood" Mode (Priority: P1) ✅ Implemented

As a runner trying to cover all of Fremont, I want the app to generate a series of routes that systematically cover all remaining untraveled streets, so I have a clear plan instead of generating one-off routes.

Implemented using a greedy nearest-edge walk (see US1) instead of the originally proposed spatial clustering approach. Routes are generated sequentially, each consuming streets not credited to previous routes. Up to 200 routes per plan.

**Implementation details**:
- Plan creation requires a `start_point_id` (saved start point) and `preferred_route_distance_m`
- Routes are generated via `RouteSuggestionEngine._generate_plan_routes()` using the greedy walk
- OSRM routing uses `route_through()` (order-preserving) with fallback to `trip()` and halved retry
- Waypoints >100 are chunked into 95-waypoint overlapping segments for OSRM compatibility
- Street coverage credited via `compute_coverage_ratio()` (15m buffer, ≥80% overlap)
- Plan status: `generating → ready | failed` (no in_progress/completed — route completion tracking was removed)
- "Show All Routes" button displays all plan routes on the map simultaneously
- Individual routes can be viewed on the map or exported as GPX

**Changes from original spec**:
- ~~Spatial clustering~~ → Greedy nearest-edge walk
- ~~Route completion marking~~ → Removed (was manual toggle with no coverage matching)
- ~~Progress bar~~ → Removed
- Status flow simplified: no `in_progress` or `completed` plan states

**Acceptance Scenarios** (updated):

1. **Given** a neighborhood with untraveled streets, **When** I create a plan with a preferred distance, **Then** the system generates multiple routes, each following a greedy walk targeting different streets. ✅
2. **Given** a generated plan, **When** I view it, **Then** I see each route's distance, estimated duration, and count of targeted untraveled streets. ✅
3. **Given** a plan, **When** I click "Show All Routes", **Then** all routes are displayed on the map. ✅
4. ~~**Given** I mark a route as completed~~ → **Removed**. Route completion tracking was cut.
5. **Given** I export a plan route as GPX, **When** I download it, **Then** the GPX file matches the existing export format. ✅
6. **Given** a neighborhood with very few untraveled streets, **When** I create a plan, **Then** the system generates a single short route. ✅
7. **Given** route generation encounters an OSRM error mid-plan, **When** generation fails, **Then** already-generated routes are preserved and the plan status is set to "failed". ✅

---

### User Story 5 — Optimal Coverage Planner (Priority: P3) ⏸️ Deferred

> **Not implemented in this iteration.** City-level coverage goals and cross-neighborhood planning remain a future enhancement. The `CoverageGoal` entity was not created. Feature 4 (single-neighborhood plans) provides the foundation for this.

---

### Edge Cases

- What if OSRM is unavailable when generating a multi-route plan? Fail gracefully — save any already-generated routes, mark plan as "failed". ✅ Implemented.
- What if a neighborhood has only 1–2 untraveled streets? Generate a single short route. ✅ Implemented.
- What if the user's preferred route distance exceeds the total untraveled distance in the neighborhood? Generate a single route covering everything, distance will be shorter than requested. ✅ Implemented.
- What if streets become traveled (via new Strava sync) after a plan is generated? The plan shows stale data. 🔮 Future: add "Refresh plan" action.
- ~~What if the user requests variation=0 in a multi-route plan?~~ N/A — variation parameter was removed.
- What if all saved start points are outside the target neighborhood? Start point is used as-is; the greedy walk will reach the nearest untraveled streets. ✅
- What if OSRM route has >100 waypoints? Chunked into 95-waypoint overlapping segments with geometry stitching. ✅ Implemented.
- What if `route_through()` fails? Falls back to `trip()`, then to halved `route_through()`. ✅ Implemented.

## Requirements *(mandatory)*

### Functional Requirements

- ~~**FR-001**: Waypoint selection shall support weighted random sampling with a configurable variation parameter (0.0–1.0).~~ → Replaced by greedy nearest-edge walk. ✅
- **FR-002**: ⏸️ Deferred. Route preference weights not implemented.
- **FR-003**: Users shall be able to save up to 20 named start points with one optional default per user. ✅
- ~~**FR-004**: Coverage plans shall pre-generate all routes upfront using spatial clustering.~~ → Replaced by greedy nearest-edge walk with sequential street consumption. ✅
- **FR-005**: Coverage plan routes use the existing RouteSuggestion model, linked via a CoveragePlanRoute join table. ✅
- **FR-006**: Sequential route generation in a plan removes previously-credited streets from the candidate pool (via `compute_coverage_ratio` ≥ 80%). ✅
- **FR-007**: ⏸️ Deferred. Optimal coverage planner not implemented.
- **FR-008**: ⏸️ Deferred. Cross-neighborhood planning not implemented.
- **FR-009**: All generated routes are exportable as GPX via the existing export endpoint. ✅
- ~~**FR-010**: Plan generation status shall be trackable (generating → ready → in_progress → completed | failed).~~ → Simplified to `generating → ready | failed`. Route completion tracking removed. ✅
- **FR-011** (new): OSRM routing shall use `route_through()` for order-preserving waypoint routing, with fallback to `trip()` and halved retry. ✅
- **FR-012** (new): Routes with >100 waypoints shall be chunked into 95-waypoint overlapping OSRM calls with geometry stitching. ✅
- **FR-013** (new): Street coverage shall be credited using a 15m buffer with ≥80% overlap threshold (`compute_coverage_ratio`). ✅

### Key Entities

- **UserStartPoint**: Named geographic point (PostGIS POINT) belonging to a user, with optional `is_default` flag. Max 20 per user. ✅
- **CoveragePlan**: A plan to complete a specific neighborhood. Contains `preferred_route_distance_m`, `status` (generating/ready/failed), `initial_coverage_pct`/`target_coverage_pct`, `start_point_id` (required), and links to generated routes. ✅
- **CoveragePlanRoute**: Join between CoveragePlan and RouteSuggestion with `sequence_order` and `streets_targeted` count. ~~Status (pending/completed/skipped)~~ removed — no per-route completion tracking. ✅
- ~~**CoverageGoal**~~: ⏸️ Deferred. City-level goals not implemented.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- ~~**SC-001**: Requesting the same route 5 times with variation ≥ 0.3 produces at least 3 distinct waypoint sets.~~ → N/A, variation parameter removed.
- **SC-002**: ⏸️ Deferred (route preferences not implemented).
- **SC-003**: Saved start points load within 200ms on the route form page. ✅
- **SC-004**: A coverage plan generates all routes within 90 seconds (up to 200 routes). ✅
- **SC-005**: Coverage plan routes collectively target ≥ 90% of untraveled streets in the neighborhood. ✅
- **SC-006**: ⏸️ Deferred (optimal planner not implemented).
- **SC-007**: All existing route suggestion tests continue to pass. ✅ (133 backend, 107 frontend)
- **SC-008**: GPX export works identically for plan-generated routes as for standalone routes. ✅

## Assumptions

- OSRM remains the sole routing engine (foot profile). No need to support multiple routing backends.
- ~~The existing 12-waypoint limit per OSRM trip request is sufficient.~~ → OSRM has a ~100 coordinate limit. Resolved via chunked calls (95-waypoint segments with overlap).
- Neighborhoods have pre-computed `total_street_segments` and `total_street_length_m` fields (already exist on the Neighborhood model).
- Users interact with one city at a time for coverage planning.
- Sport type is always foot-based (running/walking). No cycling-specific route generation needed.
- `length_meters` in `street_segments` is stored in true meters (fixed via migration `c34f504e3f4d` from US survey feet).

## Scope Boundaries

### Implemented

- Greedy nearest-edge walk algorithm (replaced weighted random sampling)
- CRUD for saved start points with default selection
- Multi-route coverage plan generation for a single neighborhood (up to 200 routes)
- OSRM `route_through()` for order-preserving routing with fallback chain
- Chunked OSRM calls for >100 waypoints
- Coverage matching via 15m buffer with ≥80% overlap threshold
- Plan status tracking (`generating → ready | failed`)
- GPX export for all generated routes
- Frontend UI: coverage page, plan creation, plan detail, route viewing, "Show All Routes"
- `length_meters` data fix (US survey feet → true meters)

### Deferred

- Highway type preference weights (US2)
- City-level optimal coverage planner with neighborhood ranking (US5)
- `CoverageGoal` entity
- Route completion marking (prototyped and intentionally removed)

### Out of Scope

- Collaborative/shared plans between users
- Elevation-aware or terrain-aware routing
- Cycling-specific routing profiles
- Real-time route tracking or live GPS integration
- Automatic plan completion detection from Strava sync
- Turn-by-turn text directions
- Calendar integration or scheduling
- Point-to-point (non-roundtrip) routes
