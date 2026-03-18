# Data Model Changes: Application Stability & Hardening

**Feature**: 002-app-stability-hardening | **Date**: 2026-03-14

This document describes **changes** to the existing data model, not the full model. Only entities being modified are listed.

## Entity Changes

### User (modified)

**New columns:**

| Column | Type | Nullable | Default | Index | Purpose |
|--------|------|----------|---------|-------|---------|
| `access_token_hash` | `String(64)` | False | — | Unique | SHA-256 hex digest of the plaintext Strava access token. Enables O(1) auth lookup. |
| `sync_started_at` | `DateTime` | True | null | No | Timestamp when current sync began. Used for stale-sync detection (>5 min = stale). |

**Modified columns:**

| Column | Change | Reason |
|--------|--------|--------|
| `sync_status` | Add `"complete"` to `VALID_SYNC_STATUSES` | Transient success state in the state machine |

**New methods:**

| Method | Signature | Purpose |
|--------|-----------|---------|
| `transition_sync_status` | `(new_status: str) -> None` | Validates state transitions against allowed transitions map; raises `ValueError` on invalid transition |

**Sync status state machine:**

```
idle → syncing → complete → idle     (happy path)
syncing → error                       (on failure)
error → idle                          (on retry trigger)
syncing → revoked                     (token revoked during sync)
revoked → idle                        (after re-auth)
```

> **Legacy note**: The existing codebase also uses `"importing"` as an active sync state. On startup, all `"importing"` values are migrated to `"syncing"` (and then reset to `"error"` as stale). `"importing"` is not a valid state in the new state machine.

### Activity (modified)

**Modified columns:**

| Column | Change | Reason |
|--------|--------|--------|
| `import_status` | Add `"error"` and `"gps_quality_warning"` to `VALID_IMPORT_STATUSES` | Track failed/flagged activities instead of silently marking as matched |

**Import status lifecycle:**

```
pending → polyline_imported → streams_imported → matched    (happy path)
any state → error                                            (on failure)
polyline_imported → gps_quality_warning                      (GPS quality flag)
```

### No New Entities

This hardening pass does not introduce new tables or entities. All changes are column additions or constraint tightening on existing models.

## Database Constraints

### Foreign Key Enforcement

SQLite requires `PRAGMA foreign_keys = ON` per connection. Add this to the SQLAlchemy `connect` event listener in `database.py`.

### Unique Constraints

| Table | Constraint | Purpose |
|-------|-----------|---------|
| `users` | `UNIQUE(access_token_hash)` | Indexed O(1) auth lookup |
| `activities` | `UNIQUE(strava_activity_id)` — already exists | Dedup safety net for concurrent imports |

## Frontend State Changes

### Zustand Store Additions

| Slice | Field | Type | Purpose |
|-------|-------|------|---------|
| UI | `toasts` | `Toast[]` | Array of active toast notifications |
| UI | `osrmAvailable` | `boolean \| null` | OSRM health flag from backend; null = unknown |

### Toast Type

```typescript
interface Toast {
  id: string;
  message: string;
  type: 'error' | 'warning' | 'success' | 'info';
  createdAt: number;
}
```

## Migration Notes

- `access_token_hash` must be backfilled for existing users by decrypting each token and computing SHA-256. This is a one-time migration script.
- `sync_started_at` defaults to null (no backfill needed).
- `VALID_IMPORT_STATUSES` and `VALID_SYNC_STATUSES` are Python-level sets; no schema migration needed for the set itself.
- `PRAGMA foreign_keys = ON` only affects new connections; existing data must already be referentially consistent.
