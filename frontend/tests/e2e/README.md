# Browser Verification Harness

Local-only Playwright harness that drives the running web app in a real browser to
confirm a fix works **before pushing**, without completing real Strava OAuth. It
uses the backend dev auth bypass (`DEV_AUTH_BYPASS=1`) and a seeded demo user in an
isolated verification database.

> **LOCAL ONLY.** When the bypass authenticates a request the backend emits a
> **CRITICAL** log line. Never enable `DEV_AUTH_BYPASS` in a shared or deployed
> environment.

## Prerequisites

1. A running Postgres + PostGIS. The Docker DB started by `docker compose up -d db`
   (container `pacman-tracker-db-1`) is sufficient — the launchers fall back to
   the container's `psql`/`pg_restore`, so **host PostgreSQL client tools are not
   required**. Override the container name with `VERIFY_DB_CONTAINER` if needed.
   The launchers create the isolated `pacman_verify` database and apply
   migrations automatically.
2. Install Playwright + browser (one-time):
   ```powershell
   cd frontend
   npm install
   npx playwright install chromium
   ```
3. Build the frozen Seattle snapshot once (see `specs/008-browser-verification-harness/snapshot/README.md`).

## Run

```powershell
# 1. Bring up the warm verification stack (isolated DB + backend bypass + frontend)
infra\verify-up.ps1

# 2. Drive the browser
cd frontend
npm run test:e2e            # headless
npm run test:e2e:headed     # watch it run

# 3. Between back-to-back runs, fast-reset the data baseline
infra\verify-reset.ps1

# Final pre-push check: clean full bring-up
infra\verify-clean.ps1
```

## Verifying the bypass CRITICAL log

When `verify-up.ps1` starts the backend with `DEV_AUTH_BYPASS=1`, the first
authenticated request emits a CRITICAL warning in the backend console, e.g.:

```
CRITICAL ... DEV_AUTH_BYPASS is enabled — authentication is bypassed ...
```

Confirm this line appears in the backend terminal during a verification run. Its
presence is the sole safeguard (by design) that the bypass is active.

## Helpers

- `helpers/auth.ts` — `seedAuth(page)` seeds localStorage (`access_token`,
  `user_id`, `display_name`) so protected pages load without a login redirect.
- `helpers/intercept.ts` — `forceResponse(page, scenario)` / `ErrorPresets` mock
  backend responses at the browser layer (backend untouched) to reproduce
  error-state UI.
- `helpers/evidence.ts` — `startEvidence(page)` + `makeResult(...)` capture page
  content, console errors, and network outcomes and produce a pass/fail result.

## Out of scope — authentication changes

The bypass disables real authentication, so **auth/session/token changes cannot be
validly verified with this harness**. Verifying those requires a separate real-auth
path (with a mocked Strava token exchange), which this feature does not provide. If
your change touches login, sessions, or token handling, do not rely on these
bypass-based runs.
