# Contract: Seed / Reset / Snapshot CLI

**Feature**: `008-browser-verification-harness` | **Date**: 2026-06-15

These are the command-line contracts for the Python scripts that manage the verification database. They follow the existing `python -m app.scripts.<name>` pattern. All operate ONLY against the isolated verification database (`pacman_verify`); they MUST refuse to run against the dev/prod `DATABASE_URL`.

---

## `snapshot_verification.py` — build / restore the frozen Seattle snapshot

### Build (one-time, produces a local gitignored artifact)
```text
python -m app.scripts.snapshot_verification build \
    --output specs/008-browser-verification-harness/snapshot/seattle.dump
```
- **Precondition**: a PostGIS DB loaded with Seattle streets/neighborhoods/city (via existing `load_cities.py`).
- **Behavior**: `pg_dump` of `cities`, `neighborhoods`, `street_segments` ONLY (no user/activity/coverage tables → no private data).
- **Output**: snapshot artifact at `--output`. Deterministic: re-running `build` on the same source yields equivalent restorable data.
- **Exit codes**: `0` success; `2` source DB missing required tables; `3` dump failure.

### Restore (into verification DB)
```text
python -m app.scripts.snapshot_verification restore \
    --input specs/008-browser-verification-harness/snapshot/seattle.dump \
    --database-url postgresql://pacman:pacman_dev@localhost:5432/pacman_verify
```
- **Precondition**: target DB exists with PostGIS extension; URL is the verification DB.
- **Behavior**: clears existing snapshot rows (TRUNCATE ... CASCADE), then performs a data-only restore of street/neighborhood/city data into the migration-created tables. Idempotent: re-running yields the same baseline.
- **Guard**: refuses if target DB name is not the configured verification DB (default `pacman_verify`). Exit `4`.
- **Exit codes**: `0` success; `4` refused (not verification DB); `5` restore failure.

---

## `seed_verification.py` — layer demo user + sample data on a restored snapshot

```text
python -m app.scripts.seed_verification \
    --database-url postgresql://.../pacman_verify
```
- **Precondition**: snapshot already restored (city/neighborhoods/streets present); `users` empty (no non-demo users).
- **Behavior** (idempotent):
  0. Refuse (exit `8`) if any non-demo users already exist — `DEV_AUTH_BYPASS` authenticates as the first user, so determinism requires the demo user be the only one. The fix is to rebuild the verification DB (`infra/verify-clean.ps1`), not to delete rows.
  1. Insert exactly one demo `User` (id=1, synthetic `strava_athlete_id`, `sync_status="complete"`, placeholder encrypted tokens — never real).
  2. Insert N sample `Activity` rows with `gps_trace` over real Seattle streets, `import_status="matched"`.
  3. Insert `UserStreetCoverage` + `CoverageSnapshot` rows so dashboards render non-empty.
- **Postcondition**: `SELECT count(*) FROM users = 1`; protected pages have content.
- **Guard**: refuses to run unless target is the verification DB. Exit `4`.
- **Idempotency**: re-running yields the same baseline (no duplicate users/activities).
- **Exit codes**: `0` success; `4` refused (not verification DB); `6` snapshot tables missing; `8` refused (non-demo users present — rebuild the verification DB).

---

## `reset_verification.py` — fast data-only reset to baseline (warm loop)

```text
python -m app.scripts.reset_verification \
    --database-url postgresql://.../pacman_verify
```
- **Precondition**: snapshot + demo data already present (warm DB).
- **Behavior** (fast; does NOT touch snapshot tables):
  1. Truncate run-accumulated tables (e.g., generated routes/plans) and demo `activities` + coverage tables.
  2. Reseed the fixed sample activities + coverage (delegates to `seed_verification` data step).
  3. Does NOT truncate `cities`/`neighborhoods`/`street_segments`.
- **Postcondition**: dataset identical to the post-seed baseline; `users` still has exactly the demo user.
- **Note on process-local state**: this script resets DB state only. The launcher restart-free warm loop also clears process-local caches (`routing._osrm_available`, `clear_active_sync_jobs()`); if those run in the live backend process, the harness triggers them via the existing `force=True`/recovery paths or a backend restart in `verify-clean`.
- **Missing baseline**: if the demo user is absent it is re-established automatically (delegates to `ensure_demo_user`) rather than failing — there is no dedicated exit code for a missing baseline.
- **Guard**: refuses unless target is the verification DB. Exit `4`.
- **Exit codes**: `0` success; `4` refused (not verification DB); `8` refused (non-demo users present, surfaced via the re-establish path).

---

## Shared safety contract (all three scripts)

- MUST resolve the target DB name and **refuse** (exit `4`) if it is not the configured verification database name (default `pacman_verify`), preventing accidental mutation of the dev/prod DB (FR-004a).
- MUST NOT download from OpenStreetMap at runtime (FR-004b) — all street data comes from the snapshot.
- MUST NOT write any real person's private activity data (FR-004d).
- MUST pass `ruff check` / `ruff format` (constitution code style).
