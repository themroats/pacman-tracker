# Data Model: Mobile Responsive UI

**Feature**: 004-mobile-responsive-ui  
**Date**: 2026-03-22

## Summary

This feature involves **no data model changes**. It is a frontend-only layout/styling change that does not add, modify, or remove any entities, API types, database tables, or state management slices.

## Existing Entities (unchanged)

No entities are affected. The Zustand store slices (Auth, Activity, Coverage, City, UI) remain unchanged. The TypeScript API types in `types/api.ts` remain unchanged.

## New State

| State | Location | Type | Purpose |
|-------|----------|------|---------|
| `isMobile` | `useIsMobile()` hook (derived from `matchMedia`) | `boolean` | Reactive flag indicating whether the viewport is below 768px. Not stored in Zustand — it's a derived browser state. |
| `isMenuOpen` | NavBar local `useState` | `boolean` | Controls hamburger menu open/close state. Local to NavBar component only. |
| `isFilterOpen` | FilterPanel or MapPage local `useState` | `boolean` | Controls collapsible filter panel on mobile. Local to the component. |

These are all component-local or hook-derived UI states — no persistence, no API surface, no store changes.
