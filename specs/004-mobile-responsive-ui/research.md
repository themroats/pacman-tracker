# Research: Mobile Responsive UI

**Feature**: 004-mobile-responsive-ui  
**Date**: 2026-03-22

## R1: Responsive Strategy with Inline Styles

**Context**: The project uses 100% inline React.CSSProperties for all styling. There are no CSS files, no Tailwind, no styled-components, no CSS modules. Media queries cannot be expressed in inline styles.

**Decision**: Use a `useIsMobile()` custom hook that calls `window.matchMedia("(max-width: 767px)")` and listens for changes. Components consume the boolean and conditionally apply mobile vs desktop style objects.

**Rationale**:
- Zero new dependencies — uses only the browser `matchMedia` API.
- Consistent with the project's existing pattern of inline styles via CSSProperties objects.
- Simple conditional: `const style = isMobile ? mobileStyle : desktopStyle`.
- Automatically responds to orientation changes and window resizes (matchMedia fires the `change` event).
- A single shared hook avoids each component reimplementing the query.

**Alternatives considered**:
- **Global CSS file with media queries**: Would fragment the styling approach (some inline, some in CSS). All existing components use inline styles — adding a parallel system increases cognitive overhead.
- **CSS-in-JS library (styled-components, emotion)**: Would require a new dependency and a migration of affected components. Overkill for a single breakpoint.
- **Tailwind CSS**: Would require installing the full Tailwind toolchain and converting all existing inline styles. Massive scope increase.
- **Container queries**: Not needed — the breakpoint is based on viewport width, which is exactly what `matchMedia` provides.

## R2: Hamburger Menu Pattern in React

**Context**: NavBar currently renders horizontal links in a flex row. On mobile (<768px), it needs to collapse into a hamburger icon that opens a dropdown/slide-out menu.

**Decision**: Add local `useState` to NavBar for `isMenuOpen`. When `isMobile` is true, render a hamburger icon button (three horizontal lines via a simple SVG or span-based CSS icon) instead of the link row. Toggling the button shows/hides a vertical dropdown positioned below the nav bar. Clicking a link or tapping outside closes the menu.

**Rationale**:
- No library needed — a hamburger menu is a simple toggle pattern.
- Local component state (`isMenuOpen`) is sufficient; no global store changes needed.
- The dropdown renders as `position: absolute` below the nav bar, overlaying page content.
- Close-on-navigate is handled by `useLocation` change detection (the hook already used for active link highlighting).

**Alternatives considered**:
- **Bottom tab bar**: Steals vertical space from the map, which is the primary content. Rejected per clarification session.
- **Third-party menu library (react-burger-menu, headless-ui)**: Adds a dependency for a pattern that takes ~30 lines to implement. Violates constitution principle IV (no speculative dependencies).
- **Collapsible top bar**: Pushes page content down when expanded, causing layout shift on the map. Less clean than an overlay.

## R3: Leaflet Map Height in Stacked Layouts

**Context**: On desktop, map pages (Map, Coverage, Route) use `height: 100vh` or `flex: 1` to fill the viewport. In a stacked mobile layout where form/summary content sits above the map, the map needs a defined height since `flex: 1` won't work in a scrollable stacked container.

**Decision**: On mobile, give the map container a fixed height using `height: 60vh` (60% of the viewport height). This ensures the map is tall enough to be useful while leaving room for the user to scroll up to form/summary content above.

**Rationale**:
- `vh` units are relative to the actual viewport, so the map adapts to different phone sizes.
- 60vh provides roughly 400px on a typical phone (667px viewport), which is practical for map interaction.
- On the MapPage (where the map is the primary content and there's minimal content above), the map can remain at `100%` of the remaining space after the collapsible filter panel.
- The stacked layout for CoveragePage and RoutePage becomes a normal scrolling page: [controls] → [map at 60vh] → [additional content if any].

**Alternatives considered**:
- **Full viewport height map with overlay panels**: More complex to implement; requires z-index management and potentially gesture conflicts with the map.
- **CSS `calc(100vh - headerHeight)`**: Fragile — depends on knowing the exact header/form height which varies with content.
- **Percentage of parent**: Doesn't work when the parent is a scrollable column.

## R4: Testing Responsive Behavior in Vitest/jsdom

**Context**: Tests run in jsdom, which does not implement `window.matchMedia` by default. The `useIsMobile` hook depends on it.

**Decision**: Mock `window.matchMedia` in the test setup file (`frontend/tests/setup.ts`). Provide a helper that lets tests control the simulated screen width. Use `@testing-library/react` `renderHook` for hook-level tests and `render` for component-level responsive tests.

**Rationale**:
- The mock is a standard pattern for testing responsive hooks in jsdom.
- A centralized mock in setup.ts means all tests get it automatically.
- Tests can override the mock per-test to simulate mobile vs desktop.

**Implementation sketch**:
```typescript
// In tests/setup.ts, add:
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false, // default: desktop
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
```

**Alternatives considered**:
- **Skip responsive tests**: Would violate constitution principle II (test-first). Rejected.
- **Use a real browser (Playwright/Cypress)**: Heavier, slower, and not the project's current test strategy. Could be added later as E2E tests but not needed for unit/component coverage.

## R5: Touch Target Sizing

**Context**: FR-007 requires all interactive elements to have a minimum touch target of 44x44 points (Apple HIG standard). Current buttons and links use small padding (e.g., `padding: 4px 12px`).

**Decision**: On mobile, increase `minHeight` and `minWidth` of all interactive elements (buttons, links, select dropdowns, checkboxes) to 44px. Apply this through the `isMobile` conditional in each component. Checkboxes get a larger `accentColor` target area via wrapping label padding.

**Rationale**:
- 44px is the Apple Human Interface Guidelines minimum; Google Material uses 48dp. 44px is a reasonable compromise.
- Increasing size only on mobile avoids changing the desktop aesthetic.
- Wrapping labels (already used by LayerToggles) are the standard approach for enlarging checkbox targets.

**Alternatives considered**:
- **Global CSS rule for all buttons**: Would require a CSS file and contradict the inline-styles pattern.
- **Always 44px on all platforms**: Would alter the desktop design unnecessarily and fail SC-005 (desktop unchanged).
