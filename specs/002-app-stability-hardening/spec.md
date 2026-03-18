# Feature Specification: Application Stability & Hardening

**Feature Branch**: `002-app-stability-hardening`  
**Created**: 2026-03-14  
**Status**: Draft  
**Input**: User description: "Scan the entire codebase and identify issues with the application's existing functionality for stability hardening"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reliable Error Feedback (Priority: P1)

As a user, when something goes wrong (API failure, network timeout, data loading error), I see a clear, helpful error message instead of a blank screen or silently broken UI. Today, dozens of error paths across both the backend and frontend are silently swallowed, leaving me confused about why data isn't showing.

**Why this priority**: This is the single most impactful usability problem. Users currently have no way to diagnose or report issues because failures are invisible. Every other improvement builds on the user's ability to see what's happening.

**Independent Test**: Can be fully tested by triggering known failure scenarios (disconnect network, revoke API token, submit invalid data) and verifying each produces a visible, actionable error message.

**Acceptance Scenarios**:

1. **Given** the backend returns a 500 error on any API call, **When** the frontend receives the error, **Then** the user sees a descriptive error notification (not a blank screen or stale data).
2. **Given** a Strava sync fails mid-import due to a token revocation, **When** the user checks their sync status, **Then** the status shows "revoked" (not stuck on "syncing") and a reconnect prompt is displayed.
3. **Given** coverage matching fails for an activity, **When** the user views their activities, **Then** the failed activity shows an error status (not falsely marked as "matched").
4. **Given** a webhook delivery from Strava fails to process, **When** the system encounters the error, **Then** an appropriate non-200 status is returned so Strava can retry delivery.

---

### User Story 2 - Accurate Per-User Data Isolation (Priority: P1)

As a user, I expect that my activities, coverage data, progress stats, and sync status belong only to me. No other user should see my data, and I should never see someone else's data. Currently, several backend endpoints lack user-scoped filtering, meaning data leaks between users.

**Why this priority**: Data isolation is a fundamental trust and privacy requirement. Without it, the application cannot safely serve multiple users.

**Independent Test**: Can be tested by authenticating as User A, requesting activities/coverage/progress, then authenticating as User B and verifying completely different datasets are returned. No cross-user data should ever appear.

**Acceptance Scenarios**:

1. **Given** User A is authenticated, **When** they request their activity list, **Then** only User A's activities are returned.
2. **Given** User A is authenticated, **When** they request coverage data or progress stats, **Then** only data computed from User A's activities is returned.
3. **Given** User A is authenticated, **When** they request GeoJSON activity data, **Then** only User A's GPS traces are included.
4. **Given** an unauthenticated request hits any data endpoint, **When** the server processes the request, **Then** it returns a 401 Unauthorized response.

---

### User Story 3 - Resilient Sync Lifecycle (Priority: P2)

As a user, when I trigger a Strava sync, I expect the process to complete reliably or clearly tell me what went wrong. Today, syncs can get stuck in a "syncing" state if the background task fails, the token is revoked, or the server restarts. I have no way to recover without developer intervention.

**Why this priority**: Sync is the primary data-ingestion pathway. If syncing breaks silently, the entire app becomes stale and useless. Users need confidence that their latest activities will appear.

**Independent Test**: Can be tested by triggering a sync, simulating token revocation mid-sync, and verifying the status transitions to an error/revoked state with a user-visible recovery action.

**Acceptance Scenarios**:

1. **Given** a sync is in progress and the Strava token is revoked, **When** the sync detects the revocation, **Then** the sync status is updated to "revoked" and the user sees a reconnect prompt.
2. **Given** a sync fails due to a transient error, **When** the failure is detected, **Then** the sync status is set to "error" with a message, and the user can retry.
3. **Given** the server restarts while a sync is in progress, **When** the server comes back up, **Then** stale "syncing" statuses are detected and reset to "error" so users can re-trigger.
4. **Given** a user triggers a sync, **When** another sync is already in progress for that user, **Then** the duplicate request is rejected with a clear message rather than starting a parallel sync.

---

### User Story 4 - Trustworthy Coverage & Progress Numbers (Priority: P2)

As a user, I rely on coverage percentages and progress statistics to track my street-exploration goals. When these numbers are wrong due to silent import failures, missing data, or calculation inconsistencies, I lose trust in the app. Coverage data must accurately reflect my actual activities.

**Why this priority**: Coverage accuracy is the core value proposition of the application. Incorrect numbers undermine the entire purpose of the product.

**Independent Test**: Can be tested by importing a known set of activities with known GPS traces, then verifying the resulting coverage percentages match expected values within a defined tolerance.

**Acceptance Scenarios**:

1. **Given** an activity import partially fails (e.g., GPS decoding error), **When** the import completes, **Then** the affected activity is flagged with a warning status rather than silently marked as successful.
2. **Given** a user has imported activities, **When** they view neighborhood coverage, **Then** the coverage percentage is computed from a single efficient query (not one query per neighborhood).
3. **Given** duplicate activities arrive (via webhook and manual sync), **When** the system processes them, **Then** duplicates are gracefully skipped without crashing or corrupting coverage data.

---

### User Story 5 - Responsive & Informative Frontend (Priority: P3)

As a user, when I navigate through the Coverage, Map, Progress, and Route pages, I expect to see loading indicators while data is fetching, clear error messages when something fails, and a responsive interface even with large datasets. Today, many pages render blank while loading, errors are invisible, and large GeoJSON datasets slow the map.

**Why this priority**: Polish and feedback are what separate a prototype from a usable product. Users need visual confirmation that the app is working.

**Independent Test**: Can be tested by navigating each page on a slow network connection and verifying loading spinners appear, error messages show for failures, and the map remains interactive with large datasets.

**Acceptance Scenarios**:

1. **Given** any page is loading data, **When** the user lands on the page, **Then** a loading indicator is visible until data arrives.
2. **Given** an API call fails on any page, **When** the error occurs, **Then** the user sees an error message with a suggestion (retry, check connection, etc.).
3. **Given** city or neighborhood selection changes, **When** the new data loads, **Then** the UI correctly resets dependent state (neighborhoods clear when city changes, coverage reloads).
4. **Given** a user changes route form inputs, **When** the city selection changes, **Then** the neighborhood list updates to reflect the new city.

---

### User Story 6 - Secure Input Handling (Priority: P3)

As a user, when I submit form data (coordinates, distances, filters), the system validates my input and gives me clear feedback if something is wrong. Today, invalid inputs (NaN coordinates, unbounded distances, invalid bbox values) are silently accepted or cause cryptic backend errors.

**Why this priority**: Input validation prevents confusing errors and protects against abuse (e.g., requesting impossibly large routes).

**Independent Test**: Can be tested by submitting boundary and invalid values for every user-facing input and verifying friendly validation messages appear.

**Acceptance Scenarios**:

1. **Given** a user enters invalid coordinates (e.g., latitude > 90), **When** they submit a route request, **Then** the form shows a validation error before the request is sent.
2. **Given** a user requests a route with an extremely large distance, **When** the request is submitted, **Then** the system rejects it with a maximum-distance message.
3. **Given** a user provides an invalid bounding box, **When** coverage data is requested, **Then** the system returns a 400 error with a descriptive message instead of silently returning empty data.

---

### Edge Cases

- What happens when a user's Strava token expires during a multi-page activity import (hundreds of activities)?
- How does the system behave if two OAuth callbacks arrive simultaneously for the same user?
- What happens when the SpatiaLite extension fails to load at startup?
- How does the frontend behave if the backend returns malformed GeoJSON?
- What happens when a user triggers coverage matching while a previous matching job is still running?
- How does the system handle a webhook event for a deleted or unknown user?
- What happens when the city bootstrap process is interrupted mid-way (server restart)?

## Clarifications

### Session 2026-03-14

- Q: How should API errors be displayed to the user? → A: Toast notifications (temporary pop-ups that auto-dismiss)
- Q: What is the maximum allowed route distance? → A: 50 km
- Q: How should the app handle the missing OSRM service in production? → A: Graceful degradation (detect unavailability, show user message, disable route form)
- Q: What are the valid sync status transitions? → A: idle → syncing → complete → idle (happy path), syncing → error → idle (on retry), syncing → revoked (requires re-auth)
- Q: What are the valid activity import status transitions? → A: pending → polyline_imported → streams_imported → matched (happy path); any state → error (on failure); polyline_imported → gps_quality_warning (GPS quality flag)

## Requirements *(mandatory)*

### Functional Requirements

**Error Visibility & Handling**

- **FR-001**: System MUST surface all API errors to the user as toast notifications (temporary pop-ups that auto-dismiss) rather than silently swallowing them.
- **FR-002**: System MUST log all caught exceptions at an appropriate severity level (ERROR for failures, WARNING for recoverable issues).
- **FR-003**: System MUST return non-200 status codes from webhook handlers when processing fails, allowing the upstream provider to retry.
- **FR-004**: System MUST differentiate error types in API responses (e.g., token revocation vs. transient failure vs. invalid input) so the frontend can display context-appropriate messages.

**Authentication & Data Isolation**

- **FR-005**: All data-returning endpoints (activities, coverage, progress, GeoJSON) MUST require authentication and filter results to the authenticated user only.
- **FR-006**: System MUST reject requests with a 401 status when no valid authentication is present.
- **FR-007**: System MUST emit a critical-level log warning when the development auth bypass is enabled.

**Sync Reliability**

- **FR-008**: System MUST update sync status to an error or revoked state when a background sync fails, rather than leaving it in a "syncing" state.
- **FR-009**: System MUST detect and recover stale sync statuses on startup (e.g., processes that were "syncing" when the server last shut down).
- **FR-010**: System MUST prevent duplicate concurrent syncs for the same user.
- **FR-011**: System MUST handle duplicate activity imports gracefully (skip without crashing).

**Data Integrity**

- **FR-012**: System MUST flag activities with import warnings (e.g., GPS quality issues, partial decode failures) rather than silently marking them as successfully imported.
- **FR-013**: System MUST validate activity import status values against a defined set of valid statuses.
- **FR-014**: System MUST enforce referential integrity (foreign key constraints) in the database.

**Input Validation**

- **FR-015**: System MUST validate coordinate inputs are within valid geographic ranges (latitude -90 to 90, longitude -180 to 180).
- **FR-016**: System MUST enforce a maximum route distance of 50 km.
- **FR-017**: System MUST validate bounding box parameters and return descriptive 400 errors for invalid values.
- **FR-018**: System MUST validate that entity ID parameters are positive integers.

**Frontend Reliability**

- **FR-019**: All pages MUST display a loading indicator while data is being fetched.
- **FR-020**: All pages MUST display a toast notification when an API call fails.
- **FR-021**: City/neighborhood selectors MUST correctly reset dependent state when the parent selection changes.
- **FR-022**: Form inputs MUST validate values before submission and show inline validation errors.

**Performance**

- **FR-023**: Neighborhood coverage queries MUST be batched into a single query rather than executing one query per neighborhood.
- **FR-024**: User authentication MUST NOT require iterating through all users in the database.
- **FR-025**: System MUST detect when the route suggestion service (OSRM) is unavailable and display a clear "Route suggestions unavailable" message to the user, disabling the route form rather than failing with a cryptic error.

### Key Entities

- **User**: Authenticated account linked to Strava. Owns activities, coverage data, and sync state.
- **Activity**: A Strava activity with GPS trace, sport type, and import status. Belongs to one user. Valid import statuses: pending, polyline_imported, streams_imported, matched, error, gps_quality_warning. Transitions: pending → polyline_imported → streams_imported → matched (happy path); any state → error (on failure); polyline_imported → gps_quality_warning (GPS quality flag).
- **Sync Status**: Tracks the state of a user's Strava data import. Valid states: idle, syncing, complete, error, revoked. Legacy state `"importing"` is migrated to `"syncing"` on startup. Transitions: idle → syncing → complete → idle (happy path); syncing → error → idle (on retry); syncing → revoked (token revoked, requires re-auth). "Complete" is a transient success state that resets to idle.
- **Street Coverage**: Per-user, per-street record of how much of a street segment has been traversed. Derived from activity GPS traces.
- **Neighborhood/City**: Geographic regions containing street segments. Used for coverage aggregation and filtering.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero silent error paths — every API failure, import error, and exception is either shown to the user or logged at ERROR level. Verified by audit of all catch blocks.
- **SC-002**: 100% of data endpoints enforce user authentication and return only the authenticated user's data. Verified by integration tests with multiple test users.
- **SC-003**: Sync status never remains stuck in "syncing" for more than 5 minutes after a failure. Verified by simulating token revocation, server restart, and transient errors during sync.
- **SC-004**: Duplicate activity imports are handled gracefully with zero database constraint violation errors. Verified by importing the same activity set twice.
- **SC-005**: Every page shows a loading indicator within 200ms of navigation. Verified by manual testing on a throttled connection.
- **SC-006**: Every page displays an error message within 1 second when an API call fails. Verified by simulating backend unavailability.
- **SC-007**: Coverage page loads neighborhood coverage data using at most 2 database queries (one for neighborhoods, one for coverage) regardless of neighborhood count. Verified by query-count profiling.
- **SC-008**: All user-facing form inputs reject invalid values with inline feedback before the request is sent. Verified by submitting boundary values (empty, NaN, out-of-range).
- **SC-009**: Authentication lookups complete in constant time relative to user count. Verified by benchmarking with 100 vs 10,000 users.

## Assumptions

- This is a single-user or small-scale application currently backed by SQLite with SpatiaLite. Multi-worker deployment and horizontal scaling are not in scope for this hardening pass.
- The existing Strava OAuth2 flow is the sole authentication mechanism and will remain so.
- The frontend uses Zustand for state management and Mapbox/MapLibre for map rendering — these choices are retained.
- This spec focuses on fixing existing functionality, not adding new features. Scope is limited to making what exists work correctly and reliably.
- Industry-standard error handling practices apply: log all exceptions, show user-friendly messages, never silently discard failures.
- Performance improvements target the most egregious issues (N+1 queries, O(n) auth lookup) rather than comprehensive optimization.
