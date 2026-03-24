# Tasks: Mobile Responsive UI

**Input**: Design documents from `/specs/004-mobile-responsive-ui/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Per constitution Principle II (Test-First Development), responsive behavior tests are written before implementation in each priority tier (T003, T011, T018). Tests use the `matchMedia` mock from setup.ts to simulate mobile/desktop viewports.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test infrastructure and the shared `useIsMobile` hook that all user stories depend on

- [x] T001 Add `window.matchMedia` mock to frontend/tests/setup.ts
- [x] T002 Create `useIsMobile` hook in frontend/src/hooks/useIsMobile.ts

**Checkpoint**: `useIsMobile()` hook available for all components. Test setup can simulate mobile/desktop.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No additional foundational tasks beyond Phase 1 — the `useIsMobile` hook is the only shared dependency. User story implementation can begin immediately after Phase 1.

**⚠️ CRITICAL**: Phase 1 must be complete before any user story work begins.

**Checkpoint**: Foundation ready — user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 — Browse Map on Phone (Priority: P1) 🎯 MVP

**Goal**: Make the Map page fully usable on mobile: full-viewport map, collapsible filter panel, non-overlapping overlays, touch-friendly controls, and properly constrained activity popups.

**Independent Test**: Load MapPage at 375px wide. Open/close filter panel. Tap an activity trace. Verify no horizontal scroll, no overlay overlap, popup fully visible.

### Tests for P1 Stories (US1 + US2) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T003 [P] [US1] [US2] Create responsive behavior test file with failing tests for NavBar hamburger menu rendering and MapPage mobile layout in frontend/tests/components/test_responsive.tsx

### Implementation for User Story 1

- [x] T004 [US1] Make FilterPanel collapsible on mobile in frontend/src/components/ActivityList/FilterPanel.tsx
- [x] T005 [P] [US1] Reposition and compact SyncStatus on mobile in frontend/src/components/SyncStatus.tsx
- [x] T006 [P] [US1] Reposition LayerToggles on mobile to avoid overlay overlap in frontend/src/components/Map/LayerToggles.tsx
- [x] T007 [P] [US1] Constrain ActivityPopup width on mobile (set maxWidth, verify Leaflet autoPan handles viewport fitting) in frontend/src/components/Map/ActivityPopup.tsx
- [x] T008 [US1] Update MapPage overlay positioning for mobile layout in frontend/src/pages/MapPage.tsx

**Checkpoint**: Map page is fully functional on a 375px screen. Filter panel collapses, overlays don't overlap, popups fit viewport.

---

## Phase 4: User Story 2 — Navigate Between Pages on Phone (Priority: P1)

**Goal**: Replace the horizontal NavBar link row with a hamburger menu on mobile screens, providing access to all page links and logout in a dropdown overlay.

**Independent Test**: Load app at 375px wide. Verify hamburger icon visible, tap to open menu, see all links + logout, tap a link to navigate, menu closes.

### Implementation for User Story 2

- [x] T009 [US2] Convert NavBar to hamburger menu on mobile in frontend/src/components/Layout/NavBar.tsx
- [x] T010 [US2] Update AppLayout for mobile-aware nav height in frontend/src/components/Layout/AppLayout.tsx

**Checkpoint**: All pages accessible via hamburger menu on mobile. Desktop nav unchanged.

---

## Phase 5: User Story 3 — View Coverage Dashboard on Phone (Priority: P2)

**Goal**: Convert the Coverage page from a fixed sidebar+map layout to a stacked layout on mobile, with coverage summary and selectors above the map. Neighborhood table remains readable.

**Independent Test**: Load CoveragePage at 375px wide. Select a city. View coverage stats and neighborhood breakdown. Scroll down to see the map. No horizontal scrollbar.

### Tests for P2 Stories (US3 + US4) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T01$1 [P] [US3] [US4] Add failing tests for CoveragePage and RoutePage stacked mobile layouts in frontend/tests/components/test_responsive.tsx

### Implementation for User Story 3

- [x] T01$1 [P] [US3] Make AreaSelector full-width on mobile in frontend/src/components/CoverageDashboard/AreaSelector.tsx
- [x] T01$1 [P] [US3] Make CoverageSummary table responsive on mobile in frontend/src/components/CoverageDashboard/CoverageSummary.tsx
- [x] T01$1 [US3] Convert CoveragePage to stacked layout on mobile in frontend/src/pages/CoveragePage.tsx

**Checkpoint**: Coverage page stacks vertically on mobile. Neighborhood table is readable. Map visible at 60vh when scrolled.

---

## Phase 6: User Story 4 — Generate Route on Phone (Priority: P2)

**Goal**: Convert the Route page from its fixed 380px sidebar+map layout to a stacked layout on mobile, with the route form and results above the map.

**Independent Test**: Load RoutePage at 375px wide. Fill out route form. Generate a route. View result stats and map. No horizontal scrollbar.

### Implementation for User Story 4

- [x] T01$1 [P] [US4] Make RouteForm inputs full-width on mobile in frontend/src/components/RouteSuggestion/RouteForm.tsx
- [x] T01$1 [P] [US4] Make RouteDetail segment table responsive on mobile in frontend/src/components/RouteSuggestion/RouteDetail.tsx
- [x] T01$1 [US4] Convert RoutePage to stacked layout on mobile in frontend/src/pages/RoutePage.tsx

**Checkpoint**: Route page stacks vertically on mobile. Form usable, results readable, map visible at 60vh.

---

## Phase 7: User Story 5 — Check Progress on Phone (Priority: P3)

**Goal**: Polish the Progress page for mobile: ensure the SVG timeline chart fits the screen width, milestone badges wrap properly, and the stats grid adapts.

**Independent Test**: Load ProgressPage at 375px wide. Select a city. View timeline chart, milestones, and stats. No horizontal scrollbar.

### Tests for P3 Stories (US5 + US6) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T01$1 [P] [US5] [US6] Add failing tests for ProgressPage and HomePage mobile layouts in frontend/tests/components/test_responsive.tsx

### Implementation for User Story 5

- [x] T01$1 [P] [US5] Make TimelineChart SVG responsive to container width in frontend/src/components/ProgressTimeline/TimelineChart.tsx
- [x] T020 [P] [US5] Make MilestoneList badges smaller and wrap on mobile in frontend/src/components/ProgressTimeline/MilestoneList.tsx
- [x] T021 [P] [US5] Make StatsOverview grid stack on mobile in frontend/src/components/ProgressTimeline/StatsOverview.tsx
- [x] T022 [US5] Update ProgressPage responsive padding in frontend/src/pages/ProgressPage.tsx

**Checkpoint**: Progress page is readable on a 375px screen. Chart scales, badges wrap, stats stack.

---

## Phase 8: User Story 6 — Connect with Strava on Phone (Priority: P3)

**Goal**: Ensure the Home page landing and post-auth views are properly sized on mobile, and the toast container doesn't overflow the screen.

**Independent Test**: Load HomePage at 375px wide (unauthenticated). Verify button size and layout. Load authenticated view. Verify quick-action buttons fit.

### Implementation for User Story 6

- [x] T023 [P] [US6] Make HomePage buttons and layout responsive in frontend/src/pages/HomePage.tsx
- [x] T024 [P] [US6] Make ToastContainer full-width on mobile in frontend/src/components/common/ToastContainer.tsx

**Checkpoint**: Home page looks clean on mobile. Toasts are full-width and don't overflow.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Touch target sizing pass across all modified components, final validation

- [x] T025 Ensure all interactive elements meet 44px min touch target on mobile across all modified components
- [x] T026 Run quickstart.md manual validation: DevTools at 375px, navigate all pages, verify no horizontal scrollbar on any page; test portrait↔landscape orientation change on each page (FR-008, SC-006)
- [x] T027 Verify desktop layout unchanged: load all pages at 1024px+ and confirm no visual regressions (SC-005)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: N/A — Phase 1 is the only blocker
- **User Stories (Phases 3–8)**: All depend on Phase 1 completion (useIsMobile hook)
  - US1 and US2 can proceed in parallel (different files)
  - US3 and US4 can proceed in parallel (different files)
  - US5 and US6 can proceed in parallel (different files)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 1. No dependency on other stories.
- **US2 (P1)**: Depends only on Phase 1. No dependency on other stories.
- **US3 (P2)**: Depends only on Phase 1. No dependency on other stories.
- **US4 (P2)**: Depends only on Phase 1. No dependency on other stories.
- **US5 (P3)**: Depends only on Phase 1. No dependency on other stories.
- **US6 (P3)**: Depends only on Phase 1. No dependency on other stories.

### Within Each Priority Tier

- Test tasks MUST be written and FAIL before implementation tasks begin (constitution Principle II)
- Component-level changes (marked [P]) can proceed in parallel within each story
- Page-level changes should happen after their component dependencies are done
- Each story is independently testable after completion

### Parallel Opportunities

**Priority tier 1 (P1):**
```
T003 [US1+US2] Tests (FAIL first)
   │
   ├── T004 [US1] FilterPanel  ──┐
   ├── T005 [US1] SyncStatus   ──┤── parallel ──→ T008 [US1] MapPage
   ├── T006 [US1] LayerToggles ──┤
   ├── T007 [US1] ActivityPopup──┘
   │
   └── T009 [US2] NavBar ──→ T010 [US2] AppLayout
```

**Priority tier 2 (P2):**
```
T011 [US3+US4] Tests (FAIL first)
   │
   ├── T012 [US3] AreaSelector    ──┐── parallel ──→ T014 [US3] CoveragePage
   ├── T013 [US3] CoverageSummary ──┘
   │
   ├── T015 [US4] RouteForm   ──┐── parallel ──→ T017 [US4] RoutePage
   └── T016 [US4] RouteDetail  ──┘
```

**Priority tier 3 (P3):**
```
T018 [US5+US6] Tests (FAIL first)
   │
   ├── T019 [US5] TimelineChart ──┐
   ├── T020 [US5] MilestoneList ──┤── parallel ──→ T022 [US5] ProgressPage
   ├── T021 [US5] StatsOverview ──┘
   │
   ├── T023 [US6] HomePage       ──┐── parallel (independent)
   └── T024 [US6] ToastContainer ──┘
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Write P1 tests (T003) — verify they FAIL
3. Complete Phase 3: US1 — Map page mobile (T004–T008)
4. Complete Phase 4: US2 — Hamburger nav (T009–T010)
5. **STOP and VALIDATE**: Navigate to Map page on 375px screen via hamburger menu. Verify P1 tests pass.
6. Deploy/demo if ready

### Incremental Delivery

1. Phase 1 → Setup done
2. T003 (P1 tests) → US1 + US2 → Map and navigation work on mobile → Deploy (MVP!)
3. T011 (P2 tests) → US3 → Coverage dashboard works on mobile → Deploy
4. US4 → Route suggestions work on mobile → Deploy
5. T018 (P3 tests) → US5 + US6 → Progress and Home pages polished → Deploy
6. Phase 9 → Touch targets and final validation → Deploy

### Parallel Single-Developer Strategy

1. T001 + T002 (Setup — sequential, quick)
2. T003 (P1 tests — write and verify they fail)
3. T004–T007 in parallel, then T008 (US1 components then page)
4. T009–T010 (US2 — sequential, NavBar then AppLayout)
5. T011 (P2 tests — write and verify they fail)
6. T012–T013 in parallel, then T014 (US3)
7. T015–T016 in parallel, then T017 (US4)
8. T018 (P3 tests — write and verify they fail)
9. T019–T021 in parallel, then T022 (US5)
10. T023–T024 in parallel (US6)
11. T025–T027 (Polish — sequential)

---

## Notes

- [P] tasks = different files, no dependencies on other tasks in the same story
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- All changes use the `useIsMobile()` hook for conditional styling — no CSS files added
- Desktop layout must remain visually identical (SC-005) — always test at 1024px+ after changes
- Commit after each task or logical group
