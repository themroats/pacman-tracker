# Feature Specification: Local Browser-Based Verification Harness

**Feature Branch**: `008-browser-verification-harness`  
**Created**: 2026-06-15  
**Status**: Draft  
**Input**: User description: "Local browser-based verification harness that lets a developer (and an AI agent) drive the running web app in a real browser to confirm a fix or feature works before pushing, using a dev auth bypass and seeded demo user to reach protected pages without real Strava OAuth"

## Clarifications

### Session 2026-06-15

- Q: How do we guarantee the dev bypass ("first user") resolves to the seeded demo user and not a pre-existing real dev user? → A: Verification runs against a dedicated, isolated local verification database containing only the seeded demo user and its sample data; the developer's real dev database is untouched.
- Q: How rich should the seeded demo dataset be, and where does the street/coverage data come from? → A: Use a frozen snapshot of existing real Seattle street/neighborhood data (restored from a locally-generated, gitignored PostGIS-compatible dump, not re-downloaded from OSM), with a seeded demo user plus sample activities and coverage layered on top. Deterministic and realistic; no live OSM download.
- Q: How strongly should the auth bypass be prevented from leaking into shared/deployed environments? → A: Keep the existing CRITICAL-level log warning as the sole safeguard; no startup fail-safe or in-app banner is added by this feature. Visibility relies on the log and developer discipline.
- Q: Where are forced backend responses applied to reproduce error-state UI? → A: Intercept at the browser/network layer — the harness mocks the HTTP response the frontend receives, leaving the real backend unchanged. This proves the frontend's error-handling/UX for a given status and body.
- Q: Does this feature provide a way to launch the stack, and how is fast back-to-back iteration supported? → A: Provide a thin launcher that brings up the isolated verification DB, the backend with bypass enabled, and the frontend. Default fast loop keeps services warm and performs a fast data-only reset between runs; an on-demand clean full bring-up (rebuild from snapshot, fresh startup) is available for a final pre-push check. Full automatic teardown after every run is out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Verify a protected-page fix in a real browser without Strava OAuth (Priority: P1)

A developer (or an AI agent acting on their behalf) has just changed a protected page — for example the map, coverage dashboard, or route suggestion page — and wants to confirm the change actually works in a real browser before pushing. Today this requires completing a live Strava OAuth login, which is slow, depends on an external service, and cannot be automated. With this feature, the developer launches the app in a local "verification mode," lands directly on the protected page as a known demo user, exercises the change, and gets a clear pass/fail signal with supporting evidence (what was on screen, any errors, what the page requested from the backend).

**Why this priority**: This is the core value of the feature — the ability to reach and exercise protected UI quickly and repeatably is what unblocks fast, confident pre-push verification. Every other story builds on this capability.

**Independent Test**: Start the app in verification mode, open the coverage dashboard directly, confirm the page renders the demo user's coverage without ever visiting the Strava login screen, and produce a verification result. This alone delivers value even if no other story is implemented.

**Acceptance Scenarios**:

1. **Given** the app is running in local verification mode with a seeded demo user, **When** the developer opens a protected page directly, **Then** the page loads as the demo user without redirecting to the login screen.
2. **Given** a protected page is open in verification mode, **When** the developer interacts with it (e.g., selects a neighborhood, submits the route form), **Then** the resulting UI state and any backend interactions are observable and can be asserted against expected outcomes.
3. **Given** a verification run has completed, **When** the developer reviews the result, **Then** they receive a clear pass/fail outcome accompanied by evidence (page content, visible errors, and the network responses involved).
4. **Given** verification mode is active, **When** any verification run starts, **Then** the system makes it unambiguous that authentication is bypassed and this configuration is for local use only.

---

### User Story 2 - Establish a known, repeatable demo dataset (Priority: P2)

Before verifying anything, the developer needs the app to contain predictable data so results are deterministic: a demo user exists, and there is enough sample content (activities, coverage, at least one seeded city/neighborhood) for protected pages to render meaningfully. With this story, the developer can create or reset this known dataset on demand so each verification run starts from the same baseline.

**Why this priority**: Verification is only trustworthy if the underlying data is known and stable. Without a repeatable baseline, a "failure" may just be missing or stale data. This directly supports P1 but is separable because P1 can run against any pre-existing user.

**Independent Test**: Run the seed/reset action against a local database, then confirm the demo user and sample data exist and that protected pages have content to display. Delivers value by making any verification deterministic.

**Acceptance Scenarios**:

1. **Given** an empty or inconsistent local database, **When** the developer runs the seed action, **Then** a known demo user and sample dataset exist afterward.
2. **Given** a previously seeded database, **When** the developer runs the reset action, **Then** the dataset returns to the same known baseline regardless of prior verification activity.
3. **Given** the demo dataset exists, **When** a protected page that depends on user data is opened in verification mode, **Then** the page displays the seeded content rather than an empty state.

---

### User Story 3 - Verify error-state and edge-case UX deterministically (Priority: P3)

Some fixes are specifically about how the UI behaves when the backend returns errors — for example, a session-expired message, a "routing service unavailable" banner, or a "no streets found" message. These states are hard to reproduce with a healthy backend. With this story, the developer can force specific backend responses for a verification run so the corresponding UI state appears reliably and can be confirmed.

**Why this priority**: Error-state UX is a common source of bugs and a frequent fix target, but it is the hardest to reproduce on demand. This is high-value but secondary to being able to reach and exercise the page at all.

**Independent Test**: Force a chosen error response for a specific page action, trigger that action in verification mode, and confirm the intended error UI appears. Delivers value by making otherwise-unreproducible states verifiable.

**Acceptance Scenarios**:

1. **Given** verification mode is active, **When** a specific backend response (e.g., an authorization failure or a service-unavailable result) is forced for a page action, **Then** triggering that action displays the matching user-facing message.
2. **Given** a forced error response, **When** the verification run completes, **Then** the result distinguishes "the expected error UI appeared" from "an unexpected error occurred."

---

### Edge Cases

- **No demo user present**: Verification mode is active but the database has no user. The system must fail with a clear, actionable message rather than a confusing authorization error or blank page.
- **Stack not running**: A verification run is requested but the app or its dependencies are not started. The system must report which prerequisite is missing rather than producing an ambiguous failure.
- **Routing-dependent verification without routing service**: A route-generation page is verified while the external routing service is not running. The system must make clear that the result reflects the "routing unavailable" path, not a real routed result.
- **Auth-related change under bypass**: A developer attempts to verify an authentication/session change while the auth bypass is enabled. The system must warn that the bypass invalidates this category of verification and that real-auth verification is required instead.
- **Verification configuration leakage**: The bypass/verification configuration must never be the active mode in a shared or deployed environment, and the system must make an enabled bypass loudly visible so it cannot be left on unintentionally.
- **Non-deterministic data drift**: Repeated verification runs mutate the dataset (e.g., generated routes accumulate). The baseline must be restorable so later runs are not affected by earlier ones.
- **Warm-state leakage between runs**: In the fast (warm) loop, process-local or cached state (e.g., routing-availability cache, sync job tracking) could carry over between runs. The data-only reset must clear such state, and a clean full bring-up must be available when warm reuse is insufficient.
- **Stale warm services after an impactful change**: A change that alters the schema, the snapshot, or backend code that is not hot-reloaded could make warm services stale and produce a misleading result. The clean full bring-up path must be used in these cases.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a local "verification mode" in which protected pages can be reached and exercised in a real browser without completing real third-party (Strava) OAuth.
- **FR-002**: The system MUST authenticate verification sessions as a known demo user so that protected pages behave as if a real user is logged in.
- **FR-003**: The system MUST allow the frontend application state to be initialized as authenticated so the application does not redirect away from protected pages during a verification run.
- **FR-004**: The system MUST provide a repeatable way to create and reset a known demo dataset (at minimum a demo user; ideally enough sample activities, coverage, and city/neighborhood data for protected pages to render meaningfully).
- **FR-004a**: Verification MUST run against a dedicated, isolated local verification database that contains only the seeded demo user and its associated sample data, so that the development authentication bypass deterministically resolves to the demo user. The developer's primary local/dev database MUST NOT be used or mutated by verification runs.
- **FR-004b**: The demo dataset's street and neighborhood data MUST come from a frozen, locally-generated (gitignored, not committed) snapshot of existing real Seattle data restored into the verification database, NOT from a live re-download of OpenStreetMap data at seed time. Re-seeding from the snapshot MUST produce identical street/neighborhood data every time.
- **FR-004c**: The frozen snapshot MUST be in a form compatible with the production geospatial database (PostGIS), so that geometry and coverage calculations behave identically to production rather than relying on a non-PostGIS substitute.
- **FR-004d**: The seed process MUST layer a demo user plus sample activities and coverage records on top of the restored street snapshot, and MUST NOT include any real person's private activity data.
- **FR-005**: The system MUST allow a verification run to interact with pages the way a user would (navigating, clicking, entering values, toggling controls).
- **FR-006**: The system MUST capture verification evidence, including visible page content, user-facing errors, and the backend interactions (requests and their response outcomes) relevant to the action under test.
- **FR-007**: The system MUST produce a clear pass/fail result for each verification run, distinguishing expected outcomes from unexpected failures.
- **FR-008**: The system MUST allow specific backend responses to be forced for a verification run by intercepting at the browser/network layer (mocking the HTTP response the frontend receives), without modifying the real backend, so that error-state and edge-case UI can be reproduced deterministically.
- **FR-009**: The system MUST make an active authentication bypass visible whenever verification mode is in use, via a CRITICAL-level log warning emitted when the bypass authenticates a request (the existing safeguard). No additional in-app banner or startup fail-safe is required by this feature.
- **FR-010**: The verification/bypass configuration MUST be disabled by default and is intended strictly for local use; preventing its activation in shared or deployed environments relies on the default-off setting plus the CRITICAL log warning and developer discipline, not on an automated startup block.
- **FR-011**: The system MUST clearly communicate, for verification runs that depend on the external routing service, whether the result reflects a real routed outcome or the "routing unavailable" path.
- **FR-012**: The system MUST document that authentication, session, and token-related changes cannot be validly verified while the auth bypass is enabled, and MUST direct such verification to a real-auth path instead.
- **FR-013**: The system MUST fail with clear, actionable messages when prerequisites are missing (no demo user, stack not running, missing dependency) rather than producing ambiguous errors.
- **FR-014**: The verification capability MUST be usable both by a developer directly and by an AI agent performing the verification on the developer's behalf.
- **FR-015**: The system MUST support on-demand, agent-driven verification performed fresh per change as the primary mode, AND MUST provide a thin reusable scaffold (a shared authenticated-session/seed foundation) so that high-value flows can be promoted into saved, re-runnable scenarios over time. Authoring a full saved-scenario regression suite upfront is out of scope; the scaffold only needs to make such promotion possible later.
- **FR-016**: The system MUST provide a thin launcher that brings up the isolated verification database, the backend with the bypass enabled, and the frontend, so verification can be run on demand. Managing the full lifecycle of all optional services (e.g., automatic teardown after each run) is out of scope.
- **FR-017**: The system MUST support a fast iteration loop in which services are kept running (warm) between verification runs and only a fast data-only reset is performed to restore the demo baseline, so back-to-back verification of multiple changes stays quick.
- **FR-018**: The fast data-only reset MUST restore the demo baseline deterministically, including clearing run-accumulated data (e.g., generated route suggestions) and any process-local/cached state that would otherwise leak between runs (e.g., routing-availability cache, sync job tracking).
- **FR-019**: The system MUST also provide an on-demand clean full bring-up (rebuild the verification database from the snapshot and start services fresh, exercising the normal startup path) for use as a final pre-push check.

### Key Entities *(include if feature involves data)*

- **Demo User**: A known, non-real user that verification sessions authenticate as. Represents "the logged-in user" for protected pages; has just enough profile/identity for pages to render.
- **Demo Dataset**: The collection of sample content tied to the demo user (activities, coverage records, at least one city/neighborhood) that gives protected pages something meaningful to display. Built by restoring a frozen snapshot of real Seattle street/neighborhood data and layering a demo user plus sample activities and coverage on top. Must be creatable and resettable to a known baseline, and lives in a dedicated isolated verification database separate from the developer's primary dev database.
- **Street Snapshot**: A frozen, locally-generated (gitignored, not committed) export of existing real Seattle street and neighborhood data in a PostGIS-compatible form. Provides realistic geometry without a live OSM download; restored into the verification database during seeding and never re-downloaded.
- **Verification Run**: A single attempt to confirm a fix/feature works, consisting of the page(s) exercised, the actions taken, any forced backend responses, the captured evidence, and the resulting pass/fail outcome.
- **Forced Response Scenario**: A configured HTTP response (e.g., an error status and body) injected at the browser/network layer for a verification run to deterministically produce a specific UI state, without changing the real backend.
- **Verification Result**: The outcome record of a run — pass/fail plus supporting evidence (page content, visible errors, backend interaction outcomes).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can reach and begin exercising any protected page in verification mode in under 1 minute from an already-running stack, without visiting the third-party login screen.
- **SC-002**: A verification run for a typical UI change yields a clear pass/fail result with supporting evidence in under 2 minutes.
- **SC-003**: Repeating the same verification run against the same baseline produces the same result at least 95% of the time (deterministic outcomes), with data drift eliminated by reset.
- **SC-004**: At least the three most common error-state UX conditions (authorization failure, routing/service unavailable, empty/not-found result) can be reproduced on demand and confirmed.
- **SC-005**: 100% of verification runs in which the auth bypass is active emit the CRITICAL-level log warning indicating that authentication is bypassed.
- **SC-006**: The verification/bypass configuration is off by default in all environments, and no shared or deployed environment is configured to enable it.
- **SC-007**: An AI agent can independently complete a protected-page verification (reach the page, perform an action, report pass/fail with evidence) without a human completing any login step.

## Assumptions

- Verification runs against a locally running stack (web app, backend, database). This feature provides a thin launcher to bring up that stack (isolated verification DB + backend with bypass + frontend), but does not own full lifecycle orchestration such as automatic teardown after each run.
- The default workflow keeps services warm and uses a fast data-only reset between runs for quick back-to-back iteration; a clean full bring-up from the snapshot is used for a final pre-push check and to catch startup/migration/schema regressions that warm reuse would miss.
- The existing development authentication bypass (returning the first user) and the existing frontend authentication state are the foundation for reaching protected pages; this feature coordinates and packages them for verification rather than inventing a new auth mechanism.
- A minimal seeded demo user is sufficient for many verifications; richer sample data (activities, coverage) improves realism and is included where feasible.
- The street/neighborhood baseline is a frozen snapshot of existing real Seattle data restored from a locally-generated, gitignored PostGIS-compatible dump; it is never re-downloaded from OSM at seed time, which keeps re-seeding deterministic.
- A PostGIS-compatible snapshot (e.g., a database dump) is the source of truth for street geometry; non-PostGIS local artifacts are not used as the verification baseline because coverage math depends on PostGIS behavior.
- The external routing service is optional; by default, routing-dependent pages are verified for their behavior, including the "routing unavailable" path, unless the routing service is explicitly running.
- Authentication/session/token changes are explicitly out of scope for bypass-based verification and are expected to be verified through a separate real-auth path.
- This capability is for local pre-push verification only and is intentionally never part of any shared continuous-integration or deployed environment.
