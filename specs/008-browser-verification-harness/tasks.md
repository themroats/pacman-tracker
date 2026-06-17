# Tasks: Local Browser-Based Verification Harness

**Input**: Design documents from `/specs/008-browser-verification-harness/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: The seed/reset scripts include pytest tasks (Constitution Principle II: Test-First, and the plan explicitly requests offline unit tests for them). The Playwright specs are the harness deliverable itself (implementation tasks), not optional tests.

**Organization**: Tasks are grouped by user story. The shared demo dataset serves all stories, so dataset creation (isolated DB + snapshot restore + seed) lives in Foundational; User Story 2 covers making it *repeatable/deterministic* (reset + warm-state clearing).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- All paths are repository-relative

## Path Conventions

- Backend scripts/tests: `backend/app/scripts/`, `backend/tests/unit/`
- Frontend harness: `frontend/tests/e2e/`, `frontend/playwright.config.ts`
- Launchers: `infra/`
- Snapshot artifact: `specs/008-browser-verification-harness/snapshot/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and tooling for the harness

- [X] T001 Create harness directory structure: `frontend/tests/e2e/helpers/`, `infra/` launcher placeholders, and `specs/008-browser-verification-harness/snapshot/` (with a `.gitkeep` or README noting the locally-generated, gitignored dump)
- [X] T002 [P] Add Playwright dev dependency and scripts to `frontend/package.json` (`@playwright/test`, `test:e2e` script) and install Chromium via `npx playwright install chromium`
- [X] T003 [P] Create `frontend/playwright.config.ts` with `baseURL=http://localhost:5173`, headless + headed projects, trace/screenshot on failure, `testDir=tests/e2e`
- [X] T004 [P] Add `pacman_verify` verification-DB configuration: extend `backend/.env.example` (and document in `backend/README.md`) with a `VERIFICATION_DATABASE_URL` defaulting to `postgresql://pacman:pacman_dev@localhost:5432/pacman_verify`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The isolated verification database, frozen snapshot tooling, and baseline seed that ALL user stories depend on (every story needs a reachable demo user with street data)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Implement DB-name safety guard helper in `backend/app/scripts/_verify_guard.py` that resolves the target DB name and raises/exits(4) if it is not the configured verification DB (`pacman_verify`), reused by all scripts (FR-004a)
- [X] T006 Implement `backend/app/scripts/snapshot_verification.py` `build` subcommand: `pg_dump` of `cities`, `neighborhoods`, `street_segments` only (no user/activity/coverage tables → no private data) to `--output` (FR-004b, FR-004c, FR-004d)
- [X] T007 Implement `backend/app/scripts/snapshot_verification.py` `restore` subcommand: drop/recreate snapshot tables and restore from `--input` into the verification DB, guarded by T005 (FR-004b)
- [X] T008 Build the frozen Seattle snapshot artifact at `specs/008-browser-verification-harness/snapshot/seattle.dump` using the `build` command against an existing PostGIS Seattle DB (one-time; deterministic re-seed source; gitignored, not committed) — built via container `pg_dump` (303k Seattle segments; cities/neighborhoods/street_segments only, no private data; 16.9 MB)
- [X] T009 Implement `backend/app/scripts/seed_verification.py`: insert exactly one demo `User` (id=1, synthetic `strava_athlete_id`, `sync_status="complete"`, placeholder encrypted tokens), sample `Activity` rows with `gps_trace` over real streets (`import_status="matched"`), and `UserStreetCoverage` + `CoverageSnapshot` rows; idempotent; guarded by T005 (FR-004, FR-004d)
- [X] T010 Implement `infra/verify-up.ps1` thin warm launcher: ensure `pacman_verify` exists with PostGIS, restore snapshot + seed if empty, start backend with `DATABASE_URL=pacman_verify` and `DEV_AUTH_BYPASS=1`, start Vite frontend; clear missing-prerequisite messaging (FR-013, FR-016)
- [X] T011 [P] Create `frontend/tests/e2e/helpers/auth.ts` `seedAuth(page, auth?)`: write `access_token`, `user_id`, `display_name` to localStorage using the exact keys from `frontend/src/store/index.ts` (FR-003)

**Checkpoint**: A developer/agent can run `verify-up.ps1`, and an authenticated demo user with street/coverage data exists in an isolated DB. User stories can now begin.

---

## Phase 3: User Story 1 - Verify a protected-page fix in a real browser without Strava OAuth (Priority: P1) 🎯 MVP

**Goal**: Land directly on a protected page as the demo user (no Strava login), exercise it, and get a clear pass/fail result with evidence.

**Independent Test**: Start the warm stack, open the coverage dashboard directly via the harness, confirm it renders the demo user's coverage without ever visiting the Strava login screen, and produce a verification result.

### Implementation for User Story 1

- [X] T012 [P] [US1] Create `frontend/tests/e2e/helpers/evidence.ts`: `startEvidence(page)` capturing console errors + network request→response outcomes, and `makeResult(evidence, assertion, notes?)` returning a pass/fail `VerificationResult` distinguishing expected vs. unexpected (FR-006, FR-007)
- [X] T013 [US1] Create `frontend/tests/e2e/smoke.protected-pages.spec.ts`: use `seedAuth` then navigate directly to a protected route (coverage dashboard, map) and assert it renders demo data without redirecting to login (FR-001, FR-002, FR-003; US1 acceptance 1)
- [X] T014 [US1] Extend the smoke spec to interact with a protected page (e.g., select a neighborhood / submit the route form) and assert the resulting UI state + backend interactions are observable (FR-005; US1 acceptance 2)
- [X] T015 [US1] Wire `startEvidence`/`makeResult` into the smoke spec so each run yields a pass/fail outcome with page content, visible errors, and network outcomes as evidence (FR-006, FR-007; US1 acceptance 3)
- [X] T016 [US1] Verify the backend emits the existing CRITICAL bypass log during a run and document the check in `frontend/tests/e2e/README.md` (FR-009; US1 acceptance 4)

**Checkpoint**: User Story 1 is fully functional — an agent can reach and exercise a protected page and report pass/fail with evidence, no human login. This is the MVP.

---

## Phase 4: User Story 2 - Establish a known, repeatable demo dataset (Priority: P2)

**Goal**: Create/reset the known dataset on demand so every verification run starts from the same deterministic baseline, including clearing process-local warm state.

**Independent Test**: Run the seed/reset action against the verification DB, confirm the demo user + sample data exist and that a previously-mutated dataset returns to the same known baseline.

### Tests for User Story 2 (Test-First — write FIRST, ensure they FAIL before implementation) ⚠️

- [X] T017 [P] [US2] Write failing `backend/tests/unit/test_seed_verification.py`: seed produces exactly one demo user, expected sample activities, and non-empty coverage; idempotent re-run yields no duplicates (offline)
- [X] T018 [P] [US2] Write failing `backend/tests/unit/test_reset_verification.py`: reset truncates run-accumulated + demo data, reseeds the fixed baseline, preserves snapshot tables, and keeps exactly one user (offline)

### Implementation for User Story 2

- [X] T019 [US2] Implement `backend/app/scripts/reset_verification.py` fast data-only reset: truncate run-accumulated tables (`routes`, `plans`, and any per-run suggestion tables — confirm exact set against `backend/app/models/route.py` and `backend/app/models/plan.py`) plus demo `activities`/`user_street_coverages`/`coverage_snapshots`, reseed via the seed data step, do NOT touch `cities`/`neighborhoods`/`street_segments`; guarded by T005 (FR-017, FR-018) — make T017/T018 pass
- [X] T020 [US2] Add process-local warm-state clearing to the reset path: reset `app.services.routing._osrm_available` (or `check_osrm_available(force=True)`) and call `clear_active_sync_jobs()` so state does not leak between warm runs (FR-018)
- [X] T021 [P] [US2] Implement `infra/verify-reset.ps1`: invoke `reset_verification` against `pacman_verify` and trigger warm-state clearing; clear "baseline missing" guidance pointing to `verify-up` (FR-017, FR-013)
- [X] T022 [P] [US2] Implement `infra/verify-clean.ps1`: stop warm services, drop/recreate `pacman_verify`, restore snapshot, seed, start backend (fresh startup path) + frontend (FR-019)
- [X] T023 [US2] Add idempotency assertions for `snapshot_verification.py restore` and `seed_verification.py` (re-running yields the same baseline with no duplicate users/activities), covered by the unit tests in T017/T018 (SC-003)

**Checkpoint**: The dataset is known, resettable, and deterministic; warm-loop iteration cannot leak state. User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - Verify error-state and edge-case UX deterministically (Priority: P3)

**Goal**: Force specific backend responses at the browser/network layer so error-state UI (session expired, routing unavailable, not found) appears reliably and can be confirmed.

**Independent Test**: Force a chosen error response for a page action, trigger that action in verification mode, and confirm the intended error UI appears.

### Implementation for User Story 3

- [X] T024 [P] [US3] Create `frontend/tests/e2e/helpers/intercept.ts`: `forceResponse(page, scenario)` using Playwright `page.route()` to fulfill matching requests with a synthetic status/body (backend untouched), plus `ErrorPresets` for 401/503/404 (FR-008)
- [X] T025 [US3] Create `frontend/tests/e2e/error-states.spec.ts`: force a 401 (session expired) for a protected call and assert the session-expired UI appears (US3 acceptance 1; SC-004)
- [X] T026 [US3] Extend `error-states.spec.ts` with a 503 routing-unavailable case asserting the "routing unavailable" UI/path is shown and distinguishable from a real routed result (FR-011; SC-004)
- [X] T027 [US3] Extend `error-states.spec.ts` with a 404/empty NOT_FOUND case asserting the empty/not-found UI appears, and use `makeResult` to distinguish "expected error UI appeared" from "unexpected error" (US3 acceptance 2; SC-004)

**Checkpoint**: All three priority error states are reproducible on demand; all user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, guardrails, and quality gates spanning all stories

- [X] T028 [P] Add a pytest guard test `backend/tests/unit/test_verify_guard.py` asserting (a) the scripts refuse to run against a non-verification DB name (exit 4), and (b) the repo default `DEV_AUTH_BYPASS` remains `0` in `backend/.env`/`config.py` so the bypass is never on by default (FR-004a, FR-010, SC-006)
- [X] T029 [P] Document the "auth/session/token changes are out of scope under bypass — use real-auth path" warning in `frontend/tests/e2e/README.md` and `quickstart.md` (FR-012; edge case)
- [X] T030 [P] Run `ruff check` / `ruff format` on the new `backend/app/scripts/*` and tests, and `eslint` on `frontend/tests/e2e/*` to satisfy code-style standards
- [X] T031 Validate the end-to-end quickstart manually: `verify-up` → smoke spec → `verify-reset` → error-states spec → `verify-clean`, confirming SC-001/002/003/004/005/006/007 hold — verified: 12/12 Playwright tests pass (smoke + error-states, headless+headed); warm stack reached protected pages with no OAuth; reset preserves snapshot; bypass authenticates tokenless requests as the demo user (SC-005 also unit-covered); repo default DEV_AUTH_BYPASS=0
- [X] T032 [P] Add a short "Local Verification Harness" section to the repo `README.md` linking to `specs/008-browser-verification-harness/quickstart.md`

---

## Dependencies & Execution Order

### Phase dependencies
- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup. **BLOCKS all user stories.** T008 (build snapshot) depends on T006; T007/T009/T010 depend on T005; restore (T007) before seed-in-launcher (T010).
- **User Story 1 (Phase 3)**: depends on Foundational (needs `seedAuth` T011, launcher T010, seeded data T009). The MVP.
- **User Story 2 (Phase 4)**: depends on Foundational (seed T009, snapshot T006/T007). Independent of US1.
- **User Story 3 (Phase 5)**: depends on Foundational + US1's `evidence.ts` (T012) for `makeResult`. Independent of US2.
- **Polish (Phase 6)**: depends on all targeted stories being complete.

### Story independence
- US1 and US2 are independent of each other (both depend only on Foundational).
- US3 reuses `evidence.ts` from US1 (T012) but is otherwise independent of US2.

### Within-story parallel opportunities
- **Setup**: T002, T003, T004 in parallel (different files) after T001.
- **Foundational**: T011 (`auth.ts`, frontend) runs parallel to backend snapshot/seed work (T005–T009). T010 launcher after T007+T009.
- **US1**: T012 (`evidence.ts`) parallel to nothing blocking; T013→T014→T015 sequential (same spec file); T016 after T013.
- **US2**: T017, T018 (test files) in parallel first; T021, T022 (separate launcher files) in parallel after T019/T020.
- **US3**: T024 first; T025→T026→T027 sequential (same spec file).
- **Polish**: T028, T029, T030, T032 in parallel; T031 last.

### Parallel execution example (Foundational)
```text
# After T005 (guard) and T006 (snapshot build) land:
T011  Create frontend/tests/e2e/helpers/auth.ts        # frontend, independent
T007  Implement snapshot restore                        # backend
# then T008 (build dump) → T009 (seed) → T010 (launcher)
```

---

## Implementation Strategy

### MVP first (User Story 1 only)
1. Complete Phase 1 (Setup) + Phase 2 (Foundational).
2. Complete Phase 3 (US1).
3. **STOP and validate**: an agent reaches the coverage dashboard without OAuth and reports pass/fail with evidence. This alone delivers the core value.

### Incremental delivery
1. Setup + Foundational → smoke-reachable demo user. 
2. Add US1 → MVP: agent-driven protected-page verification.
3. Add US2 → deterministic, repeatable baseline + fast/clean loops.
4. Add US3 → error-state UX verification.
5. Polish → guards, docs, style, full quickstart validation.

### Format validation
All tasks follow `- [ ] [TaskID] [P?] [Story?] Description with file path`. Setup/Foundational/Polish tasks carry no story label; US1/US2/US3 tasks carry their label. Every task names concrete file paths.
