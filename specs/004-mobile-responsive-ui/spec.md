# Feature Specification: Mobile Responsive UI

**Feature Branch**: `004-mobile-responsive-ui`  
**Created**: 2026-03-22  
**Status**: Draft  
**Input**: User description: "Our next feature is on the mobile view! This does not render well at all in current form"

## Clarifications

### Session 2026-03-22

- Q: What mobile navigation pattern should be used on screens below 768px? → A: Hamburger menu (icon in top nav that opens a slide-out or dropdown menu)
- Q: On mobile, how should sidebar+map pages (Route, Coverage) present their content? → A: Stacked layout — form/summary sits above the map; user scrolls down to see the map
- Q: Should tablet screens (768–1024px) get any layout adaptation, or only screens below 768px? → A: Single breakpoint only — below 768px gets mobile layout, 768px+ stays desktop layout unchanged

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse Map on Phone (Priority: P1)

A runner opens the app on their phone to check their activity map while out on a run or during a break. They need to see the map at full screen, access filters without the controls blocking the view, and tap on activity traces to see details — all on a screen width of ~375px.

**Why this priority**: The interactive map is the core feature of the application. If it is unusable on mobile, the entire app is effectively broken for phone users.

**Independent Test**: Can be fully tested by loading the Map page on a phone-sized screen (375px wide), applying filters, tapping activities, and verifying all controls are reachable and the map is fully visible.

**Acceptance Scenarios**:

1. **Given** a user on a phone-sized screen (320–428px wide), **When** they open the Map page, **Then** the map fills the available viewport with no horizontal scrolling required.
2. **Given** the Map page on mobile, **When** the user wants to filter activities, **Then** they can open/close a filter panel that does not permanently obscure the map.
3. **Given** the Map page on mobile, **When** the user taps on an activity trace, **Then** the activity detail popup is fully visible within the viewport.
4. **Given** the Map page on mobile, **When** map overlays (filters, sync status, layer toggles) are displayed, **Then** they do not overlap each other and all remain tappable.

---

### User Story 2 - Navigate Between Pages on Phone (Priority: P1)

A user on their phone needs to switch between Map, Coverage, Routes, and Progress pages. The current horizontal navigation bar is too cramped on narrow screens. On mobile, a hamburger menu icon in the top nav bar opens a slide-out or dropdown menu containing all page links and the logout action.

**Why this priority**: Navigation is the gateway to every feature. If users cannot switch pages, no other mobile improvement matters.

**Independent Test**: Can be fully tested by loading the app on a phone-sized screen, verifying all navigation links are accessible, and switching between all pages.

**Acceptance Scenarios**:

1. **Given** a user on a phone-sized screen, **When** they view the navigation bar, **Then** all page links are accessible without horizontal overflow or text truncation.
2. **Given** mobile navigation, **When** the user taps a navigation trigger, **Then** they can see and reach all page links (Map, Coverage, Routes, Progress, Logout).
3. **Given** an active page, **When** the user views the mobile navigation, **Then** the currently active page is visually indicated.
4. **Given** the mobile navigation is open, **When** the user selects a page, **Then** the navigation closes and the selected page loads.

---

### User Story 3 - View Coverage Dashboard on Phone (Priority: P2)

A user wants to check their street coverage stats — city selector, coverage percentage, and neighborhood breakdown — on their phone. Currently the page has a sidebar-and-map layout that won't fit on a narrow screen, and the neighborhood data table is too wide. On mobile, the layout stacks vertically: coverage summary and selectors appear above the map, and the user scrolls down to see the map.

**Why this priority**: The coverage dashboard is the second most-used feature after the map. Users check progress frequently while on the go.

**Independent Test**: Can be fully tested by loading the Coverage page on a phone-sized screen, selecting a city, viewing coverage stats, scrolling the neighborhood list, and verifying the map is still accessible.

**Acceptance Scenarios**:

1. **Given** a user on a phone-sized screen, **When** they open the Coverage page, **Then** the coverage summary, city selector, and map are all accessible without horizontal scrolling.
2. **Given** the Coverage page on mobile, **When** the user views the neighborhood breakdown, **Then** the data is readable without requiring horizontal scrolling.
3. **Given** the Coverage page on mobile, **When** the user interacts with the map and coverage summary, **Then** the summary is stacked above the map and the user can scroll between them.

---

### User Story 4 - Generate Route on Phone (Priority: P2)

A user wants to generate a route suggestion before heading out for a run. The current Route page has a fixed 380px sidebar next to the map, which does not fit on any phone screen. On mobile, the layout stacks vertically: route form and results appear above the map, and the user scrolls down to see the map.

**Why this priority**: Route suggestions are a key differentiator of the app. Runners most often want routes right before heading out, when they are on their phone.

**Independent Test**: Can be fully tested by loading the Route page on a phone-sized screen, filling out the route form, generating a route, and viewing the result on the map.

**Acceptance Scenarios**:

1. **Given** a user on a phone-sized screen, **When** they open the Route page, **Then** the route form is fully visible and usable without horizontal scrolling.
2. **Given** the Route page on mobile, **When** the user generates a route, **Then** the route result (distance, duration, map preview) is displayed in a readable layout.
3. **Given** the Route page on mobile, **When** the route map and route details are both available, **Then** the user can view both without one blocking the other.

---

### User Story 5 - Check Progress on Phone (Priority: P3)

A user wants to review their progress timeline, milestones, and stats on their phone. The progress page currently uses a max-width container that mostly works, but milestone badges and the timeline chart may be cramped.

**Why this priority**: The progress page is the least complex layout and already partially works on mobile, but still needs polish for a good experience.

**Independent Test**: Can be fully tested by loading the Progress page on a phone-sized screen, selecting a city, and verifying the chart, milestones, and stats are all readable.

**Acceptance Scenarios**:

1. **Given** a user on a phone-sized screen, **When** they open the Progress page, **Then** the city selector, coverage percentage, timeline chart, and milestones are all readable without horizontal scrolling.
2. **Given** the Progress page on mobile, **When** milestone badges wrap to multiple rows, **Then** they remain visually aligned and readable.

---

### User Story 6 - Connect with Strava on Phone (Priority: P3)

A new user opens the app for the first time on their phone. They need to see the landing page, understand what the app does, and tap "Connect with Strava" to authenticate. After authentication, the home page quick-action buttons must be easily tappable.

**Why this priority**: First impressions matter, but the landing page is relatively simple and likely already usable. This is lower priority than the complex pages.

**Independent Test**: Can be fully tested by loading the Home page on a phone-sized screen before and after authentication, and verifying elements are properly sized and reachable.

**Acceptance Scenarios**:

1. **Given** an unauthenticated user on a phone-sized screen, **When** they view the Home page, **Then** the description and "Connect with Strava" button are centered, readable, and easily tappable.
2. **Given** an authenticated user on a phone-sized screen, **When** they view the Home page, **Then** the quick-action buttons ("View Map", "Coverage Dashboard") are appropriately sized and don't overflow.

---

### Edge Cases

- What happens when a user rotates their phone from portrait to landscape? The layout should adapt smoothly without content being cut off or overlapping.
- How does the app behave on very small screens (320px wide, e.g., iPhone SE)? All critical content must remain accessible.
- What happens when the virtual keyboard opens (e.g., during filter date input or route form entry)? Input fields must not be hidden behind the keyboard.
- How do map popups and tooltips behave on touch devices? They must be dismissible and not lock the user out of the map.
- What happens to long text content (e.g., long neighborhood names in the coverage table) on narrow screens? Text should truncate or wrap gracefully, not cause horizontal scrolling.
- How do touch targets behave? All interactive elements (buttons, links, checkboxes) must be easily tappable without accidental mis-taps.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application MUST render all pages without horizontal scrolling on screens 320px to 428px wide (standard phone range).
- **FR-002**: The navigation MUST use a hamburger menu on screens below 768px, replacing the horizontal link bar with an icon that opens a slide-out or dropdown menu containing all page links and logout.
- **FR-003**: Pages that currently use side-by-side layouts (Route page sidebar, Coverage page panels) MUST reorganize to a stacked layout on narrow screens, with form/summary content above the map.
- **FR-004**: Map overlay controls (filter panel, sync status, layer toggles) MUST not overlap each other on narrow screens and MUST remain interactive.
- **FR-005**: The filter panel on the Map page MUST be collapsible on mobile so the map is visible beneath it.
- **FR-006**: Data tables (e.g., neighborhood coverage breakdown) MUST remain readable on narrow screens — either by reformatting, allowing contained horizontal scroll, or switching to a card/list layout.
- **FR-007**: All interactive elements (buttons, links, form inputs, checkboxes) MUST have touch-friendly target sizes (minimum 44x44 points).
- **FR-008**: The layout MUST adapt when the device orientation changes between portrait and landscape.
- **FR-009**: Map popups (activity detail) MUST be fully visible within the mobile viewport when displayed.
- **FR-010**: The app MUST continue to function correctly on desktop/tablet screens — mobile improvements must not degrade the existing desktop experience.

## Assumptions

- The mobile breakpoint is a single threshold at 768px. Below 768px gets the mobile layout; 768px and above retains the current desktop layout unchanged. No intermediate tablet breakpoint is needed.
- "Mobile view" refers to responsive layout changes for narrow screens, not a separate mobile app or native wrapper.
- The existing viewport meta tag (`width=device-width, initial-scale=1.0`) is already present and correct.
- Touch interaction support (swipe, tap) is limited to standard browser touch events — no custom gesture handling is needed for this feature.
- Performance on mobile devices (rendering speed, memory) is not in scope for this feature — the focus is on layout and usability.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All five main pages (Home, Map, Coverage, Route, Progress) render fully within the viewport on a 375px-wide screen with no horizontal scrollbar.
- **SC-002**: Users can navigate to all pages on a 375px-wide screen within 2 taps from any page.
- **SC-003**: Users can complete the primary task on each page (view map, check coverage, generate route, view progress) on a phone-sized screen without needing to pinch-zoom.
- **SC-004**: All interactive elements meet a minimum touch target size of 44x44 points.
- **SC-005**: Existing desktop layout (screens 768px and wider) remains visually identical to the current experience.
- **SC-006**: The app correctly adapts layout when the device rotates between portrait and landscape without requiring a page reload.
