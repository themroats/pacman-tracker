# Quickstart: Mobile Responsive UI

**Feature**: 004-mobile-responsive-ui  
**Branch**: `004-mobile-responsive-ui`

## Prerequisites

- Node.js 18+
- npm or equivalent package manager
- No new dependencies are introduced by this feature

## Setup

```bash
cd frontend
npm install          # unchanged — no new packages
npm run dev          # starts Vite dev server on http://localhost:5173
```

## Testing Responsive Changes

### Browser DevTools (manual)

1. Open `http://localhost:5173` in Chrome/Edge/Firefox
2. Open DevTools → Toggle Device Toolbar (Ctrl+Shift+M)
3. Select a phone preset (e.g., iPhone 12 Pro, 390×844) or set custom width below 768px
4. Navigate through all pages: Home → Map → Coverage → Route → Progress
5. Verify: no horizontal scrollbar, hamburger menu works, stacked layouts, collapsible panels

### Automated Tests

```bash
cd frontend
npm test                    # runs all Vitest tests
npm test -- test_responsive # runs only responsive behavior tests
```

### Key test scenarios

- `useIsMobile` hook returns `true` when matchMedia matches `(max-width: 767px)`
- `useIsMobile` hook returns `false` for desktop widths
- NavBar renders hamburger icon when `isMobile` is true
- NavBar renders horizontal links when `isMobile` is false
- FilterPanel starts collapsed on mobile
- RoutePage renders stacked layout (no sidebar) when `isMobile` is true
- CoveragePage renders stacked layout when `isMobile` is true

## File Change Summary

| Category | Files |
|----------|-------|
| New hook | `src/hooks/useIsMobile.ts` |
| New tests | `tests/components/test_responsive.tsx` |
| Modified layout | `src/components/Layout/NavBar.tsx`, `AppLayout.tsx` |
| Modified pages | `HomePage.tsx`, `MapPage.tsx`, `CoveragePage.tsx`, `RoutePage.tsx`, `ProgressPage.tsx` |
| Modified components | `FilterPanel.tsx`, `LayerToggles.tsx`, `ActivityPopup.tsx`, `CoverageSummary.tsx`, `AreaSelector.tsx`, `MilestoneList.tsx`, `StatsOverview.tsx`, `TimelineChart.tsx`, `RouteForm.tsx`, `RouteDetail.tsx`, `ToastContainer.tsx`, `SyncStatus.tsx` |
| Modified test setup | `tests/setup.ts` (add matchMedia mock) |

## Architecture Notes

- **Single breakpoint**: `768px`. Below = mobile, above = desktop.
- **Strategy**: `useIsMobile()` hook → components conditionally apply mobile/desktop style objects.
- **No CSS files added**: Stays consistent with project's inline-style approach.
- **No new npm dependencies**: Pure React + browser APIs.
