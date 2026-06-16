# Contract: Verification Launcher CLI

**Feature**: `008-browser-verification-harness` | **Date**: 2026-06-15

PowerShell launcher scripts under `infra/`, alongside existing helpers (`run-local-backend.ps1`, `deploy-prod.ps1`). They orchestrate the local verification stack. Full automatic teardown after each run is OUT of scope (FR-016).

---

## `verify-up.ps1` — thin warm launcher (default entry point)

```powershell
infra\verify-up.ps1 [-Headed] [-Port 8000] [-FrontendPort 5173]
```
- **Behavior**:
  1. Ensure the isolated verification database (`pacman_verify`) exists (create + PostGIS extension if missing); restore snapshot + seed if empty.
  2. Start the backend pointed at `pacman_verify` with `DEV_AUTH_BYPASS=1` (emits the existing CRITICAL log — FR-009).
  3. Start the Vite frontend dev server.
  4. Leave all services **warm** for repeated runs.
- **Postcondition**: backend on `:8000` (bypass on), frontend on `:5173`, demo user reachable.
- **Idempotency**: if services are already up, reuse them (warm) rather than failing.
- **Exit codes**: `0` ready; non-zero with a clear message naming the missing prerequisite (Docker/Postgres/Node) — FR-013.

## `verify-reset.ps1` — fast data-only reset between runs

```powershell
infra\verify-reset.ps1
```
- **Behavior**: invoke `python -m app.scripts.reset_verification` against `pacman_verify`; clear process-local warm state where applicable (OSRM availability cache, active sync jobs).
- **Precondition**: stack already warm (from `verify-up`).
- **Postcondition**: dataset restored to baseline; back-to-back verification stays fast (seconds).
- **Exit codes**: `0` reset; `7` baseline missing (run `verify-up` first).

## `verify-clean.ps1` — clean full bring-up (final pre-push check)

```powershell
infra\verify-clean.ps1 [-Headed]
```
- **Behavior**:
  1. Stop any warm services.
  2. Drop/recreate `pacman_verify`, restore snapshot, run seed (fresh).
  3. Start backend (fresh startup path — exercises migrations/startup validation) + frontend.
- **Purpose**: catch startup/migration/schema regressions warm reuse would miss (FR-019).
- **Exit codes**: `0` ready fresh; non-zero with the failing stage named.

---

## Safety / environment contract

- The launchers MUST set `DATABASE_URL` to the verification DB for the backend process they spawn; they MUST NOT enable the bypass against the dev/prod DB.
- `DEV_AUTH_BYPASS` is set ONLY for the spawned verification backend process; the repo default stays `0` (FR-010, SC-006).
- Launchers are local-only and never invoked in CI/deployed environments.
