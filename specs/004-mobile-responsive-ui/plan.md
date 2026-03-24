# Implementation Plan: Mobile Responsive UI

**Branch**: `004-mobile-responsive-ui` | **Date**: 2026-03-22 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-mobile-responsive-ui/spec.md`

## Summary

Make the Pacman Tracker frontend usable on mobile phones (screens below 768px) by introducing a CSS media-query breakpoint, converting the NavBar to a hamburger menu, converting sidebar+map layouts to stacked layouts, making overlay controls non-overlapping and collapsible, and ensuring touch-friendly target sizes — all without degrading the existing desktop experience.

## Technical Context

**Language/Version**: TypeScript ~5.6, React 18.3, Vite 6.0  
**Primary Dependencies**: react-router-dom 6.22, zustand 4.5, leaflet 1.9.4, react-leaflet 4.2.1  
**Storage**: N/A (frontend-only changes, no data model changes)  
**Testing**: Vitest 2.0 + @testing-library/react 14.2 (jsdom environment)  
**Target Platform**: Mobile browsers (320–428px width) and desktop browsers (768px+)  
**Project Type**: Web SPA (React frontend only — no backend changes)  
**Performance Goals**: N/A (layout and usability only, not rendering performance)  
**Constraints**: Single breakpoint at 768px; must not introduce CSS libraries or build-tool changes; must not alter any backend code  
**Scale/Scope**: 6 pages, ~20 components, all currently using inline styles (React.CSSProperties)

**Styling approach**: The project uses 100% inline styles via `React.CSSProperties` objects. There is no CSS framework (no Tailwind, no styled-components, no CSS modules). The only external CSS is Leaflet's CDN stylesheet. Media queries cannot be expressed in inline styles, so the responsive strategy must use one of:
1. A `useMediaQuery` hook that reads `window.matchMedia` and returns a boolean  
2. A small global CSS file with media-query rules  
3. CSS-in-JS conditional logic based on a hook

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. API-First Design | PASS | No API changes; frontend-only feature |
| II. Test-First Development | PASS | Responsive behavior tests written per priority tier (T003, T011, T018) and must fail before implementation tasks begin. Tests use matchMedia mock in jsdom. |
| III. Data Privacy by Design | PASS | No auth/token/data changes |
| IV. Simplicity & Incremental Delivery | PASS | Each page can be made responsive independently as a vertical slice; no new libraries required; no speculative patterns |
| Technology Standards (backend) | PASS | No backend changes |
| Technology Standards (frontend) | PASS | React 18 + TypeScript + Vite; no new dependencies |
| Code Style | PASS | Must pass ESLint and Prettier |
| Development Workflow | PASS | Work on feature branch `004-mobile-responsive-ui` |

**Gate result: PASS** — no violations.

**Post-design re-check (after Phase 1): PASS** — No new violations. The design introduces one hook (`useIsMobile`), zero npm dependencies, and zero architectural patterns. Each page is responsive independently (vertical slices). Tests planned before implementation.

## Project Structure

### Documentation (this feature)

```text
specs/004-mobile-responsive-ui/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (minimal — no data changes)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (N/A — no external interfaces added)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── hooks/
│   │   ├── useCityCatalog.ts          # existing
│   │   └── useIsMobile.ts             # NEW: media-query hook (< 768px)
│   ├── components/
│   │   ├── Layout/
│   │   │   ├── AppLayout.tsx          # MODIFIED: pass isMobile to NavBar
│   │   │   └── NavBar.tsx             # MODIFIED: hamburger menu on mobile
│   │   ├── ActivityList/
│   │   │   └── FilterPanel.tsx        # MODIFIED: collapsible on mobile
│   │   ├── Map/
│   │   │   ├── LayerToggles.tsx       # MODIFIED: repositioned on mobile
│   │   │   └── ActivityPopup.tsx      # MODIFIED: constrained width on mobile
│   │   ├── CoverageDashboard/
│   │   │   ├── CoverageSummary.tsx    # MODIFIED: table → card layout on mobile
│   │   │   └── AreaSelector.tsx       # MODIFIED: full-width on mobile
│   │   ├── ProgressTimeline/
│   │   │   ├── MilestoneList.tsx      # MODIFIED: smaller badges on mobile
│   │   │   ├── StatsOverview.tsx      # MODIFIED: responsive grid
│   │   │   └── TimelineChart.tsx      # MODIFIED: container-width SVG
│   │   ├── RouteSuggestion/
│   │   │   ├── RouteForm.tsx          # MODIFIED: full-width inputs
│   │   │   └── RouteDetail.tsx        # MODIFIED: responsive segment table
│   │   ├── common/
│   │   │   └── ToastContainer.tsx     # MODIFIED: full-width on mobile
│   │   └── SyncStatus.tsx             # MODIFIED: compact on mobile
│   └── pages/
│       ├── HomePage.tsx               # MODIFIED: stacked buttons
│       ├── MapPage.tsx                # MODIFIED: overlay positioning
│       ├── CoveragePage.tsx           # MODIFIED: stacked layout
│       ├── RoutePage.tsx              # MODIFIED: stacked layout (remove 380px sidebar)
│       └── ProgressPage.tsx           # MODIFIED: responsive padding
├── tests/
│   ├── components/
│   │   └── test_responsive.tsx        # NEW: responsive behavior tests
│   └── setup.ts                       # MODIFIED: add matchMedia mock
```

**Structure Decision**: Frontend-only changes. One new hook file (`useIsMobile.ts`), one new test file (`test_responsive.tsx`), and modifications to ~20 existing component/page files. No new directories needed.

## Complexity Tracking

No violations — table not needed.
