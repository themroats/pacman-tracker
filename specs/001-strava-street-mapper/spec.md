# Feature Specification: Strava Street Mapper

**Feature Branch**: `001-strava-street-mapper`  
**Created**: 2026-02-28  
**Status**: Draft  
**Input**: User description: "Create a webapp that tracks Strava exercises and compares with the street map. The overall goal will be to see previous exercises, compare with how many streets in a neighborhood have been traveled and suggest runs to keep mapping the whole city."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect Strava & View Exercise History (Priority: P1)

As a runner, I want to connect my Strava account and see all my past activities displayed on a city map, so I can visualize where I've already run.

After signing in, the user authorizes the app to read their Strava activities. The app imports all GPS-traced activities (runs, walks, bike rides) and renders each route on an interactive city map. The user can filter by activity type, date range, and view individual activity details (distance, duration, date). All previously recorded routes are shown as colored overlays on the map.

**Why this priority**: Without importing and displaying activities, no other feature (coverage analysis, route suggestions) is possible. This is the foundational data pipeline and the core value proposition — seeing your running history on a map.

**Independent Test**: Can be fully tested by connecting a Strava account, importing activities, and verifying that routes appear correctly on the interactive map. Delivers immediate value by letting users visually explore their exercise history.

**Acceptance Scenarios**:

1. **Given** a user with a Strava account, **When** they authorize the app, **Then** all their GPS-traced activities are imported and displayed as summary polyline route overlays on a city map within 2 minutes for up to 500 activities. Full GPS precision for street matching is available after background processing completes.
2. **Given** imported activities on the map, **When** the user filters by activity type (e.g., "Run"), **Then** only matching activities are shown and the map updates immediately.
3. **Given** imported activities on the map, **When** the user clicks on a specific route, **Then** activity details (name, date, distance, duration, pace) are displayed.
4. **Given** a user who has already connected Strava, **When** they return to the app later, **Then** any new activities since the last sync are automatically imported.

---

### User Story 2 - Street Coverage Dashboard (Priority: P2)

As a runner, I want to see which streets in my city (or a specific neighborhood) I have already run on and what percentage of the total streets I've covered, so I can track my progress toward mapping the entire city.

The user selects a city or neighborhood boundary on the map. The system compares the user's activity GPS traces against the known street network within that boundary. Streets are color-coded: green for "traveled" and grey for "not yet traveled." A coverage dashboard shows the percentage of streets completed for the selected area, broken down by neighborhood if viewing the whole city.

**Why this priority**: This is the core differentiator of the app — turning raw activity data into a street coverage analysis. It builds directly on Story 1 and provides the motivational "gamification" loop that keeps users engaged.

**Independent Test**: Can be tested by selecting a neighborhood, verifying that streets are correctly classified as traveled/untraveled based on imported activities, and confirming the coverage percentage is accurate.

**Acceptance Scenarios**:

1. **Given** a user with imported activities, **When** they select a neighborhood on the map, **Then** streets are color-coded (green = traveled, grey = untraveled) and a coverage percentage is displayed.
2. **Given** a user viewing the full city, **When** they open the coverage dashboard, **Then** a breakdown of coverage percentage per neighborhood is shown.
3. **Given** a user who has run on a street, **When** the system matches their GPS trace against the street network, **Then** a street is marked as "traveled" if the user's trace passes along at least 80% of the street's length.
4. **Given** a user with no activities in a selected neighborhood, **When** they view that neighborhood, **Then** 0% coverage is shown and all streets appear grey.

---

### User Story 3 - Route Suggestions for Unmapped Streets (Priority: P3)

As a runner, I want the app to suggest routes that prioritize streets I haven't run on yet, so I can efficiently work toward covering the entire city.

The user requests a route suggestion by specifying a starting point (or using their current location), a desired distance or duration, and optionally a target neighborhood. The system generates a route that maximizes coverage of untraveled streets while respecting the distance/duration preference. Suggested routes are shown on the map with untraveled street segments highlighted.

**Why this priority**: This is the "smart" feature that ties coverage data to actionable next steps. It depends on both the activity data (Story 1) and street coverage analysis (Story 2) being in place.

**Independent Test**: Can be tested by requesting a route suggestion for a partially-covered neighborhood, verifying the route prioritizes untraveled streets, and confirming it respects the requested distance constraint.

**Acceptance Scenarios**:

1. **Given** a user with partial street coverage in a neighborhood, **When** they request a route suggestion with a 5 km distance, **Then** the system generates a route that prioritizes untraveled streets and is approximately 5 km long (within 10% tolerance).
2. **Given** a user specifying a starting point and target neighborhood, **When** a route is generated, **Then** the route starts from the specified point and focuses on untraveled streets within the target neighborhood.
3. **Given** a neighborhood where the user has 100% street coverage, **When** they request a suggestion for that neighborhood, **Then** the system informs them that all streets are covered and suggests a neighboring area instead.

---

### User Story 4 - Progress Tracking Over Time (Priority: P4)

As a runner, I want to see how my street coverage has grown over time, so I can stay motivated and track my city-mapping journey.

The user accesses a progress view that shows coverage milestones (e.g., 25%, 50%, 75% of a neighborhood) with the dates they were achieved. A timeline or chart visualizes coverage growth. The user can see their all-time stats: total unique streets covered, total distance, number of activities, and estimated percentage of the city completed.

**Why this priority**: Provides long-term engagement and motivation. While not essential for core functionality, it significantly enhances the user experience and retention.

**Independent Test**: Can be tested by verifying that coverage milestones are recorded with correct dates and that the progress chart accurately reflects historical coverage growth.

**Acceptance Scenarios**:

1. **Given** a user with activities spanning multiple months, **When** they view the progress timeline, **Then** a chart shows coverage percentage growth over time.
2. **Given** a user who just reached 50% coverage in a neighborhood, **When** the milestone is reached, **Then** the system records and displays the achievement with the date.
3. **Given** a user viewing their overall stats, **When** the stats page loads, **Then** total unique streets, total distance, activity count, and city-wide coverage percentage are displayed.

---

### Edge Cases

- What happens when a Strava activity has poor GPS quality (drift, tunnels, gaps)? The system should apply a reasonable tolerance when matching GPS traces to streets and flag activities with significant GPS gaps for user review.
- What happens when the user revokes Strava access? The app retains previously imported data but stops syncing new activities and prompts the user to reconnect.
- What happens when a street network changes (new roads, closures)? The system should periodically refresh its street data and re-calculate coverage accordingly.
- What happens when a user runs on a path/trail that is not part of the road network (parks, river paths)? These traces are displayed on the map but do not count toward street coverage percentage.
- What happens when two users share an account or device? Each user account has independent activity data and coverage tracking.
- What happens when Strava rate limits are reached during initial import of a large activity history? The system queues remaining imports and completes them incrementally, notifying the user of progress.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow users to authenticate via Strava OAuth2 with `activity:read_all` scope to access all GPS-traced activities including those with private visibility.
- **FR-002**: System MUST import all GPS-traced activities (runs, walks, rides) from the user's Strava account, including historical data.
- **FR-003**: System MUST incrementally sync new Strava activities after the initial import without re-importing existing data.
- **FR-004**: System MUST display imported activity routes as colored overlays on an interactive city map.
- **FR-005**: System MUST allow users to filter displayed activities by sport type (Run, Walk, Ride), date range, and distance.
- **FR-006**: System MUST show activity details (name, date, distance, duration, pace) when a user selects a specific route.
- **FR-007**: System MUST compare user GPS traces against the street network and classify each street as "traveled" or "untraveled" using a fixed matching threshold of 80% of street length covered within a 15-meter spatial buffer.
- **FR-008**: System MUST display a color-coded map view where traveled streets are green and untraveled streets are grey.
- **FR-009**: System MUST calculate and display a street coverage percentage for any user-selected area (neighborhood or full city).
- **FR-010**: System MUST show a neighborhood-by-neighborhood coverage breakdown when viewing the full city.
- **FR-011**: System MUST generate route suggestions that prioritize untraveled streets given a starting point, desired distance/duration, and optional target area.
- **FR-012**: System MUST ensure suggested routes are runnable (follow sidewalks/roads, no impassable segments) and approximately match the requested distance (within 10% tolerance).
- **FR-013**: System MUST record coverage milestones with timestamps and display them on a progress timeline.
- **FR-014**: System MUST display overall user statistics: total unique streets, total distance, activity count, and city coverage percentage.
- **FR-015**: System MUST retain previously imported activity data if the user revokes Strava access, while ceasing new syncs.
- **FR-016**: System MUST handle GPS trace imperfections by applying a reasonable spatial tolerance when matching traces to streets.
- **FR-017**: System MUST distinguish between on-street activities (count toward coverage) and off-road activities (displayed but not counted).
- **FR-018**: System MUST support selecting and viewing coverage for a predefined set of launch cities: Seattle, Pittsburgh, Chicago, New York, and San Francisco. Additional cities may be added in future releases.

### Key Entities

- **User**: A person who connects their Strava account. Has a unique identity, authentication tokens, sync status, and preferences (home city, preferred activity types).
- **Activity**: A single exercise session imported from Strava. Has GPS trace data (series of coordinates), sport type (Run/Walk/Ride), date, distance, duration, pace, and a reference to the source Strava activity.
- **Street Segment**: A section of road/sidewalk in the street network. Has a geographic path, name, neighborhood association, and length. Can be classified as "traveled" or "untraveled" per user.
- **Neighborhood**: A named geographic boundary within a city. Contains a set of street segments and aggregate coverage statistics per user.
- **City**: A top-level geographic boundary. Contains neighborhoods and provides city-wide coverage statistics.
- **Coverage Snapshot**: A point-in-time record of a user's street coverage for a given area. Used to build the progress timeline and detect milestones.
- **Route Suggestion**: A generated route for a user. Has a starting point, sequence of street segments (prioritizing untraveled ones), total distance, and estimated duration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can connect their Strava account and see their activity history (summary polylines) on the map within 2 minutes of first sign-in (for accounts with up to 500 activities). Full GPS precision for street matching is available after background processing completes.
- **SC-002**: Street coverage percentages are accurate to within 2% when compared against manual verification of traveled streets.
- **SC-003**: 90% of users can successfully view their street coverage for a neighborhood within 3 clicks of landing on the app.
- **SC-004**: Route suggestions include at least 60% untraveled streets (by distance) when untraveled streets are available in the target area.
- **SC-005**: New activities synced from Strava appear on the map within 5 minutes of Strava webhook delivery. The system subscribes to Strava push notifications and falls back to manual sync if webhooks are unavailable.
- **SC-006** *(product goal, not acceptance criterion)*: Users who engage with the route suggestion feature are expected to increase their street coverage by at least 20% more per month compared to users who do not. This will be validated through usage analytics once multi-user hosting is available.
- **SC-007**: The progress timeline correctly reflects all historical coverage milestones without gaps or inaccuracies.

## Assumptions

- Users have active Strava accounts with GPS-traced activities available for import.
- Street/road network data is available from an open data source (e.g., OpenStreetMap) for the user's city.
- Standard OAuth2 flow is used for Strava authentication — no custom login or password-based auth.
- "Street" includes roads, sidewalks, and shared-use paths that are part of the mapped road network; trails and park paths outside the road network are excluded from coverage.
- The app is designed for individual use; there are no social, team, or competitive features in scope.
- Activity import from Strava is read-only — the app never writes back to Strava.
- The default GPS-to-street matching threshold (80%) is a fixed value providing a reasonable balance between precision and tolerance for GPS drift.
