# Quickstart: Local Browser-Based Verification Harness

**Feature**: `008-browser-verification-harness` | **Date**: 2026-06-15

This guide shows how a developer or an AI agent verifies a fix in a real browser without Strava OAuth. It assumes the implementation tasks are complete.

> Verification is local-only. The backend runs with `DEV_AUTH_BYPASS=1`, which logs a CRITICAL warning. Never enable the bypass in a shared or deployed environment.

> Database tooling: the launchers use host `psql`/`pg_restore` when present, and otherwise fall back to the Docker DB container (`pacman-tracker-db-1`, override via `VERIFY_DB_CONTAINER`). They create the isolated `pacman_verify` database and run `alembic upgrade head` automatically — no host PostgreSQL client tools are required.

---

## One-time setup

1. Install Playwright (frontend dev dependency):
   ```powershell
   cd frontend
   npm install
   npx playwright install chromium
   ```
2. Build the frozen Seattle snapshot once (requires a PostGIS DB already loaded via `load_cities.py`):
   ```powershell
   cd backend
   python -m app.scripts.snapshot_verification build --output ..\specs\008-browser-verification-harness\snapshot\seattle.dump
   ```
   The snapshot stays local (it is gitignored, **not** committed); each developer builds it once. Re-seeding from it is deterministic and OSM is never re-downloaded.

---

## Fast loop (default): warm services + data-only reset

1. Bring up the warm verification stack (isolated DB + backend with bypass + frontend):
   ```powershell
   infra\verify-up.ps1
   ```
2. Drive the browser to verify a change (agent or developer):
   ```powershell
   cd frontend
   npx playwright test tests/e2e/smoke.protected-pages.spec.ts --headed
   ```
3. Between back-to-back runs, fast-reset the data to baseline:
   ```powershell
   infra\verify-reset.ps1
   ```

Repeat steps 2–3 for each change. Services stay warm, so each iteration is quick.

---

## Final pre-push check: clean full bring-up

Before pushing, run a clean bring-up to catch startup/migration/schema regressions that warm reuse misses:
```powershell
infra\verify-clean.ps1
cd frontend
npx playwright test tests/e2e
```

---

## Verifying an error-state UI (e.g., session expired, routing unavailable)

Use the browser-layer interception helpers — the backend is unchanged:
```ts
import { seedAuth } from "./helpers/auth";
import { forceResponse, ErrorPresets } from "./helpers/intercept";

await seedAuth(page);
// RoutePage reads availability from /health; force it to report OSRM down.
await page.route("**/health", (route) =>
  route.fulfill({ status: 200, body: JSON.stringify({ status: "ok", osrm_available: false }) }),
);
await page.goto("/route");
await expect(page.getByText(/route suggestions unavailable/i)).toBeVisible();
```

> **Authentication is out of scope (FR-012).** This harness only *seeds an
> existing authenticated session* via `DEV_AUTH_BYPASS` + `seedAuth`. It does
> not modify, replace, or verify the real Strava OAuth login flow. Do not use it
> to validate authentication itself.

---

## Agent verification flow (no human login)

An AI agent performs a protected-page verification end-to-end:
1. `seedAuth(page)` — seed localStorage (`access_token`, `user_id`, `display_name`).
2. `page.goto("/coverage")` — lands on the protected page (no login redirect).
3. Interact (select neighborhood, submit form).
4. `makeResult(evidence, assertion)` — produce pass/fail with captured evidence (page content, console errors, network outcomes).
5. Report outcome. No human completes any Strava login step (SC-007).

---

## Acceptance mapping

| Success criterion | How this quickstart satisfies it |
|-------------------|----------------------------------|
| SC-001 (< 1 min to protected page, warm) | `verify-up` keeps services warm; `seedAuth` + `goto` reach the page immediately |
| SC-002 (< 2 min pass/fail) | `playwright test` + `makeResult` produce a result quickly |
| SC-003 (deterministic ≥95%) | Frozen snapshot + `verify-reset` baseline |
| SC-004 (3 error states) | `ErrorPresets`: 401 / 503 / 404 |
| SC-005 (bypass logs CRITICAL) | Backend started with `DEV_AUTH_BYPASS=1` emits the existing CRITICAL log |
| SC-006 (off by default) | Repo default `DEV_AUTH_BYPASS=0`; set only for the spawned verification backend |
| SC-007 (agent self-serve) | Agent flow above runs without human login |

---

## Troubleshooting (FR-013)

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Page redirects to login | localStorage not seeded | Run `seedAuth` before `goto` |
| "No demo user" / 401 from backend | Verification DB empty | Re-run `verify-up` (restores snapshot + seeds) |
| Route page shows "unavailable" unexpectedly | OSRM not running | Start OSRM, or treat result as the routing-unavailable path |
| Reset didn't clear prior run's routes | Process-local cache | Use `verify-reset`; if stale, use `verify-clean` |
| Script refuses to run | Pointed at non-verification DB | Ensure `DATABASE_URL` targets `pacman_verify` |
