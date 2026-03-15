# Tasks: Application Stability & Hardening

**Input**: Design documents from `/specs/002-app-stability-hardening/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-changes.md, quickstart.md

**Tests**: Constitution principle II requires acceptance-level tests before implementation. Test tasks are included per user story.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1–US6) this task belongs to
- All file paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Schema changes, infrastructure, and shared utilities that all stories depend on

- [ ] T001 Add `access_token_hash` (String(64), unique, indexed) and `sync_started_at` (DateTime, nullable) columns to User model in backend/app/models/user.py
- [ ] T002 Add `"error"` and `"gps_quality_warning"` to `VALID_IMPORT_STATUSES` set in backend/app/models/activity.py
- [ ] T003 Add `"complete"` to `VALID_SYNC_STATUSES` and implement `transition_sync_status()` method with allowed-transitions map in backend/app/models/user.py
- [ ] T004 Add `PRAGMA foreign_keys = ON` to SQLAlchemy connect event listener in backend/app/database.py
- [ ] T004a Validate existing data consistency before enabling FK enforcement — query for orphaned records (activities without users, coverage without streets) and delete/fix them in backend/app/scripts/validate_fk_integrity.py
- [ ] T004b Fail-fast if SpatiaLite extension cannot be loaded at startup — raise exception instead of logging warning and continuing in backend/app/database.py
- [ ] T005 [P] Add `compute_token_hash()` helper (SHA-256 hex digest) to backend/app/services/crypto.py
- [ ] T006 [P] Create one-time migration script to backfill `access_token_hash` for existing users in backend/app/scripts/backfill_token_hash.py
- [ ] T007 [P] Add DEV_AUTH_BYPASS critical-level log warning on startup in backend/app/api/deps.py

**Checkpoint**: Schema and infrastructure ready — user story work can begin

- [ ] T007a Run `pytest` and `vitest` to verify existing test suites still pass after Phase 1 changes

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Toast system and API client error hook that ALL frontend stories depend on; O(1) auth lookup that all backend stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T008 Rewrite `get_current_user()` in backend/app/api/deps.py to use single `WHERE access_token_hash = ?` query instead of O(n) decrypt-all loop
- [ ] T009 Update `strava_callback()` in backend/app/api/auth.py to compute and store `access_token_hash` on login and token refresh
- [ ] T010 [P] Add toast state slice (`toasts: Toast[]`, `addToast`, `removeToast`) to Zustand store in frontend/src/store/index.ts
- [ ] T011 [P] Create `<ToastContainer>` component (fixed position, auto-dismiss 5s, CSS transitions) in frontend/src/components/common/ToastContainer.tsx
- [ ] T012 Mount `<ToastContainer>` in frontend/src/App.tsx
- [ ] T013 Add global `onError` callback hook to API client `request()` function that calls `addToast` on any `ApiClientError` in frontend/src/api/client.ts — this is the **primary** error-to-toast pathway; individual `.catch` blocks should only remove empty handlers, not add duplicate toast calls

**Checkpoint**: Foundation ready — O(1) auth, toast notifications wired up. All frontend error catches will now produce visible toasts.

- [ ] T013a Run `pytest` and `vitest` to verify existing test suites still pass after Phase 2 changes

---

## Phase 3: User Story 1 — Reliable Error Feedback (Priority: P1) 🎯 MVP

**Goal**: Every API failure, import error, and exception is either shown to the user as a toast or logged at ERROR level. Zero silent catch blocks.

**Independent Test**: Stop the backend → navigate any page → toast appears. Revoke token → sync shows "revoked." Webhook fails → returns non-200.

### Backend Error Logging

- [ ] T014 [P] [US1] Replace `except Exception: pass` with `logger.exception(...)` in coverage matching try/except in backend/app/services/importer.py
- [ ] T016 [P] [US1] Replace `except Exception: pass` with `logger.exception(...)` in GeoJSON serialization in backend/app/api/coverage.py
- [ ] T017 [P] [US1] Replace `except Exception: continue` with `logger.warning(...)` in polyline decoding loop in backend/app/services/importer.py
- [ ] T018 [P] [US1] Replace `except Exception: continue` with `logger.warning(...)` in auth token decryption fallback in backend/app/api/deps.py
- [ ] T019 [P] [US1] Add `logger.exception(...)` to geometry serialization catch in backend/app/api/cities.py

### Webhook Non-200 on Failure

- [ ] T020 [US1] Replace bare `except Exception: pass` in `handle_webhook_event()` with `logger.exception(...)` and re-raise to let transient errors propagate — combines logging visibility with non-200 failure signaling in backend/app/services/webhook.py
- [ ] T021 [US1] Wrap `handle_webhook_event()` call in route handler with try/except that catches `TokenRevokedError` → mark user revoked + return 200, lets other exceptions → return 500 in backend/app/api/webhook.py

### Frontend Silent Catch Replacement

- [ ] T022 [P] [US1] Remove all empty `.catch(() => {})` in CoveragePage.tsx (8 instances) — global onError hook (T013) handles toasts; empty catches just need removal so errors propagate to the hook in frontend/src/pages/CoveragePage.tsx
- [ ] T023 [P] [US1] Remove empty `.catch(() => {})` in RoutePage.tsx in frontend/src/pages/RoutePage.tsx
- [ ] T024 [P] [US1] Remove empty `.catch(() => {})` in ProgressPage.tsx (2 instances) in frontend/src/pages/ProgressPage.tsx
- [ ] T025 [P] [US1] Remove empty `.catch()` in MapPage.tsx in frontend/src/pages/MapPage.tsx
- [ ] T026 [P] [US1] Remove silent `catch {}` in SyncStatus.tsx polling — let errors propagate to global hook in frontend/src/components/SyncStatus.tsx

**Checkpoint**: US1 complete — all error paths visible. Every catch block either shows a toast or logs at ERROR level.

- [ ] T026a [US1] (Test) Integration test: simulate backend 500 → verify ApiClientError propagates and global onError hook fires in frontend/tests/api/test_error_handling.tsx
- [ ] T026b [US1] (Test) Grep audit: verify zero remaining `except.*pass` in backend/app/ and zero `.catch(() => {})` in frontend/src/ — verifies SC-001

---

## Phase 4: User Story 2 — Accurate Per-User Data Isolation (Priority: P1)

**Goal**: All data endpoints require auth and return only the authenticated user's data. No cross-user data leaks.

**Independent Test**: Auth as User A → see only A's data. Auth as User B → see only B's data. No auth → 401 on all endpoints.

### Add Auth Dependencies

- [ ] T027 [P] [US2] Add `user: User = Depends(get_current_user)` to `list_activities()` and filter query by `user_id` in backend/app/api/activities.py
- [ ] T028 [P] [US2] Add `user: User = Depends(get_current_user)` to `activities_geojson()` and filter query by `user_id` in backend/app/api/activities.py
- [ ] T029 [P] [US2] Replace `PLACEHOLDER_USER_ID = 1` with `user: User = Depends(get_current_user)` in `progress_city()` in backend/app/api/progress.py
- [ ] T030 [P] [US2] Replace hardcoded user_id with `user: User = Depends(get_current_user)` in `progress_stats()` in backend/app/api/progress.py

### Fix Sync Status User Filter

- [ ] T031 [US2] Fix `imported` count query in `sync_status()` to include `.filter_by(user_id=user.id)` in backend/app/api/sync.py

**Checkpoint**: US2 complete — every data endpoint requires auth, filters by user. No cross-user leakage.

- [ ] T031a [US2] (Test) Integration test: create two test users, import activities for each, verify `GET /activities` returns only the requesting user's data; verify 401 when unauthenticated — verifies SC-002 in backend/tests/integration/test_user_isolation.py

---

## Phase 5: User Story 3 — Resilient Sync Lifecycle (Priority: P2)

**Goal**: Sync state machine is enforced, stale syncs recover on startup, token revocation is detected and surfaced, duplicate syncs rejected.

**Independent Test**: Trigger sync → revoke token → status shows "revoked." Restart server during sync → status resets to "error." Double-trigger sync → second request rejected.

### Sync State Machine

- [ ] T032 [US3] Update `trigger_sync()` to use `user.transition_sync_status("syncing")`, set `sync_started_at`, and catch `ValueError` from invalid transition → raise `AppError("SYNC_IN_PROGRESS", "Sync already in progress", 409)` in backend/app/api/sync.py
- [ ] T033 [US3] Update `_run_background_sync()` to transition to "complete" on success, "error" on failure, "revoked" on `TokenRevokedError` in backend/app/api/sync.py
- [ ] T034 [US3] Update `sync_status()` endpoint to auto-transition "complete" → "idle" when polled — on the first poll that observes "complete", server transitions to "idle" and returns "complete" so the frontend sees it once; next poll returns "idle" — in backend/app/api/sync.py

### Stale Sync Recovery

- [ ] T035 [US3] Update `recover_stale_sync_status()` to also check `sync_started_at` > 5 minutes as a stale indicator in backend/app/services/sync_runtime.py
- [ ] T036 [US3] Add startup recovery query in lifespan: reset all `sync_status IN ('syncing', 'importing')` to "error" in backend/app/main.py — also migrate any legacy `"importing"` values to `"syncing"` to align with the defined state machine

### Duplicate Activity Import

- [ ] T037 [P] [US3] Wrap activity INSERT in `import_phase_a()` with try/except for `IntegrityError` → skip gracefully in backend/app/services/importer.py

### Frontend Sync Status Handling

- [ ] T038 [US3] Update SyncStatus.tsx to handle "complete" state: show success toast, continue polling one more cycle to observe the server-side transition to "idle", then stop polling in frontend/src/components/SyncStatus.tsx

**Checkpoint**: US3 complete — sync never gets stuck. Token revocation, server restart, duplicate triggers all handled.

- [ ] T038a [US3] (Test) Integration test: import same activity set twice → verify IntegrityError is caught and no DB constraint violation — verifies SC-004 in backend/tests/integration/test_duplicate_import.py
- [ ] T038b [US3] (Test) Integration test: simulate stale sync status on startup → verify recovery to "error" and sync_started_at timeout — verifies SC-003 in backend/tests/integration/test_sync_recovery.py

---

## Phase 6: User Story 4 — Trustworthy Coverage & Progress Numbers (Priority: P2)

**Goal**: Coverage queries are efficient (≤2 queries), import failures flagged, coverage data accurate.

**Independent Test**: Import activities → verify coverage percentages. Import duplicates → zero crashes. View coverage for 50-neighborhood city → ≤2 DB queries.

### N+1 Coverage Query Fix

- [ ] T040 [US4] Replace N+1 `_neighborhood_coverage()` loop with single GROUP BY query in `city_coverage()` in backend/app/api/coverage.py

### Import Status Flagging

- [ ] T041 [P] [US4] Update `_process_phase_b_activity()` to set `import_status = "error"` on coverage matching failure instead of silent pass in backend/app/services/importer.py
- [ ] T042 [P] [US4] Update `_check_gps_quality()` to set `import_status = "gps_quality_warning"` on the activity record in backend/app/services/importer.py

**Checkpoint**: US4 complete — coverage data accurate, queries efficient, import failures flagged.

- [ ] T042a [US4] (Test) Unit test: call batched coverage query for a city with N neighborhoods, assert ≤2 DB queries executed — verifies SC-007 in backend/tests/unit/test_coverage_batch.py

---

## Phase 7: User Story 5 — Responsive & Informative Frontend (Priority: P3)

**Goal**: All pages show loading indicators, errors produce toasts (already wired from US1), state resets correctly on selection changes.

**Independent Test**: Navigate each page on throttled network → spinners visible. Change city → neighborhoods reset. Change route city → neighborhoods reload.

### Loading States

- [ ] T043 [P] [US5] Add loading spinner to CoveragePage.tsx data fetch sections in frontend/src/pages/CoveragePage.tsx
- [ ] T044 [P] [US5] Add loading spinner to MapPage.tsx while activities GeoJSON loads in frontend/src/pages/MapPage.tsx
- [ ] T045 [P] [US5] Add loading spinner to ProgressPage.tsx while stats and timeline load in frontend/src/pages/ProgressPage.tsx
- [ ] T046 [P] [US5] Add loading spinner to RoutePage.tsx while route suggestion is processing in frontend/src/pages/RoutePage.tsx

### State Reset on Selection Change

- [ ] T047 [US5] Fix CoveragePage.tsx city/neighborhood selection to clear dependent state and reload data when parent changes in frontend/src/pages/CoveragePage.tsx
- [ ] T048 [US5] Fix RouteForm.tsx useEffect dependency array to reload neighborhoods when cityId prop changes in frontend/src/components/RouteSuggestion/RouteForm.tsx
- [ ] T049 [US5] Fix FilterPanel.tsx local state sync — update local dates when parent filters prop changes in frontend/src/components/ActivityList/FilterPanel.tsx

### Error Boundary Integration

- [ ] T050 [US5] Wrap main route outlet in App.tsx with existing `<ErrorBoundary>` component in frontend/src/App.tsx

**Checkpoint**: US5 complete — every page has loading feedback, state resets correctly, render errors caught.

---

## Phase 8: User Story 6 — Secure Input Handling (Priority: P3)

**Goal**: All user inputs validated on both frontend and backend with friendly error messages.

**Independent Test**: Submit lat=999 → validation error. Request 999km route → rejected. Invalid bbox → 400.

### Backend Validation

- [ ] T050a [US6] Standardize backend error codes per contracts/api-changes.md — ensure `OSRM_UNAVAILABLE`, `SYNC_IN_PROGRESS`, `TOKEN_REVOKED`, `VALIDATION_ERROR` codes are used consistently across all relevant endpoints in backend/app/api/*.py

- [ ] T051 [P] [US6] Add `le=50000` to `distance_meters` field in `RouteSuggestRequest` schema in backend/app/schemas/route.py
- [ ] T052 [P] [US6] Replace dict `start_point` with typed Pydantic model with `lng: float = Field(ge=-180, le=180)` and `lat: float = Field(ge=-90, le=90)` in backend/app/schemas/route.py
- [ ] T053 [P] [US6] Add bbox validation to coverage streets endpoint — parse, validate ranges, return 400 on invalid in backend/app/api/coverage.py
- [ ] T054 [P] [US6] Add `gt=0` validation to `city_id` and `neighborhood_id` path parameters across all endpoints in backend/app/api/routes.py and backend/app/api/coverage.py

### OSRM Graceful Degradation

- [ ] T055 [US6] Add OSRM health check function (ping OSRM /health, cache result, re-check every 60s) in backend/app/services/routing.py
- [ ] T056 [US6] Add `osrm_available` field to `/health` endpoint response in backend/app/main.py
- [ ] T057 [US6] Add OSRM availability guard at start of route suggest endpoint — raise `AppError("OSRM_UNAVAILABLE", ...)` when down in backend/app/api/routes.py

### Frontend Validation

- [ ] T058 [P] [US6] Add coordinate range validation (lat -90..90, lng -180..180) to RouteForm.tsx with inline error display in frontend/src/components/RouteSuggestion/RouteForm.tsx
- [ ] T059 [P] [US6] Add distance validation (max 50 km) to RouteForm.tsx with inline error display in frontend/src/components/RouteSuggestion/RouteForm.tsx
- [ ] T060 [US6] Add `osrmAvailable` flag to Zustand store, fetch from `/health` endpoint, disable route form when false with "Route suggestions unavailable" message in frontend/src/store/index.ts and frontend/src/pages/RoutePage.tsx

**Checkpoint**: US6 complete — all inputs validated, OSRM degrades gracefully, friendly error messages shown.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [ ] T061 [P] Audit all backend catch blocks — verify zero remaining silent `except: pass` patterns across backend/app/
- [ ] T062 [P] Audit all frontend `.catch` calls — verify zero remaining empty catch handlers across frontend/src/
- [ ] T063 Run quickstart.md verification scenarios end-to-end
- [ ] T064 Run `ruff check` and `ruff format` on all modified backend files
- [ ] T065 Run `eslint` and `prettier` on all modified frontend files

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (T001, T005 for auth; T010–T011 for toasts)
- **Phase 3 (US1)**: Depends on Phase 2 (toast system, O(1) auth)
- **Phase 4 (US2)**: Depends on Phase 2 (O(1) auth). Can run parallel with US1.
- **Phase 5 (US3)**: Depends on Phase 1 (T003 state machine). Can run parallel with US1/US2.
- **Phase 6 (US4)**: Depends on Phase 1 (T002 status values). Can run parallel with US1–US3.
- **Phase 7 (US5)**: Depends on Phase 2 (toast system). Can run parallel with US1–US4.
- **Phase 8 (US6)**: Depends on Phase 2 (toast system). Can run parallel with US1–US5.
- **Phase 9 (Polish)**: Depends on all user stories complete

### User Story Independence

| Story | Backend Deps | Frontend Deps | Can Parallel With |
|-------|-------------|---------------|-------------------|
| US1 (Error Feedback) | Phase 2 auth | Phase 2 toasts | US2, US3, US4, US5, US6 |
| US2 (Data Isolation) | Phase 2 auth | None | US1, US3, US4, US5, US6 |
| US3 (Sync Lifecycle) | Phase 1 T003 | Phase 2 toasts | US1, US2, US4, US5, US6 |
| US4 (Coverage Numbers) | Phase 1 T002 | None | US1, US2, US3, US5, US6 |
| US5 (Frontend UX) | None | Phase 2 toasts | US1, US2, US3, US4, US6 |
| US6 (Input Validation) | None | Phase 2 toasts | US1, US2, US3, US4, US5 |

### Within Each User Story

- Backend parallelizable tasks (marked [P]) can run simultaneously
- Frontend parallelizable tasks (marked [P]) can run simultaneously
- State machine and data flow tasks must be sequential within the story

### Parallel Opportunities

```text
# Phase 1 — all can run in parallel:
T001, T002, T003, T004, T004a, T004b, T005, T006, T007

# Phase 2 — backend and frontend can run in parallel:
Backend: T008, T009
Frontend: T010, T011, T012, T013

# Phase 3 (US1) — backend error logging all parallel:
T014, T016, T017, T018, T019  (all [P])
# Then webhook fix sequential: T020 → T021
# Frontend silent catch removal all parallel:
T022, T023, T024, T025, T026  (all [P])

# Phase 4 (US2) — all auth additions parallel:
T027, T028, T029, T030  (all [P])
# Then T031

# Phase 5 (US3) — sequential state machine:
T032 → T033 → T034 → T035 → T036
# T037 parallel with above, T038 sequential

# Phase 6 (US4):
T040 (sequential), T041, T042 (parallel)

# Phase 7 (US5) — loading states all parallel:
T043, T044, T045, T046  (all [P])
# Then state resets: T047, T048, T049, T050

# Phase 8 (US6) — backend validation all parallel:
T050a, T051, T052, T053, T054  (all [P])
# OSRM sequential: T055 → T056 → T057
# Frontend validation parallel: T058, T059 (then T060)
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup (schema changes, utilities)
2. Complete Phase 2: Foundational (O(1) auth, toast system)
3. Complete Phase 3: US1 — Error Feedback (replace all silent catches)
4. Complete Phase 4: US2 — Data Isolation (add auth to all endpoints)
5. **STOP and VALIDATE**: Toast errors visible, data isolated per-user
6. This delivers the two P1 stories — most critical fixes shipped

### Incremental Delivery

1. Setup + Foundational → Infrastructure ready
2. US1 (Error Feedback) → Users see errors → Deploy
3. US2 (Data Isolation) → Data secure → Deploy
4. US3 (Sync Lifecycle) → Sync reliable → Deploy
5. US4 (Coverage Numbers) → Numbers accurate → Deploy
6. US5 (Frontend UX) → Polish → Deploy
7. US6 (Input Validation) → Hardened → Deploy
8. Each increment is independently valuable and testable

---

## Notes

- [P] tasks = different files, no shared state dependencies
- [USn] label maps task to specific user story
- No new libraries added — toast system built on existing Zustand
- All changes modify existing files except T006 (migration script) and T011 (ToastContainer)
- Commit after each completed task or logical group
