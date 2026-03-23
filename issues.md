# Issues Discovered During 003-deploy-routing-service

Filed from observations during OSRM routing service deployment and end-to-end testing.

---

## Issue 1: Strava token expiry causes silent route suggestion failures

**Type**: Bug
**Priority**: High
**Labels**: `bug`, `auth`, `frontend`

**Description**:
When the Strava access token expires during a session, API calls to `/api/v1/routes/suggest` return 401 Unauthorized. The frontend catches this as a generic error and displays "Failed to generate route. Please try again." with no indication that re-authentication is needed.

**Steps to reproduce**:
1. Log in via Strava OAuth on the deployed app
2. Wait for the access token to expire (or manually clear it from localStorage)
3. Navigate to Routes → click "Suggest Route"
4. See "Failed to generate route" instead of a login prompt

**Expected behavior**:
- The frontend should detect 401 responses and redirect to the login flow, or show "Session expired — please log in again"
- The API client's error handler should distinguish auth errors from route generation errors

**Relevant code**:
- `frontend/src/pages/RoutePage.tsx` — `handleSubmit` catch block shows generic error
- `frontend/src/api/client.ts` — `request()` function throws `ApiClientError` with the code, but `RoutePage` doesn't check it

---

## Issue 2: Route suggestion algorithm intermittently fails for certain waypoint combinations

**Type**: Bug / Enhancement
**Priority**: Medium
**Labels**: `bug`, `routing`, `backend`

**Description**:
The `RouteSuggestionEngine.build_route()` method calls OSRM `/trip` with selected waypoints. When OSRM can't solve the TSP (e.g., waypoints on disconnected foot paths, dead-end trails, or points too far apart for the foot profile), the trip returns `None` and the user sees "Failed to generate route."

**Observed behavior**:
- Route suggest works reliably with "Any" neighborhood (bbox-scoped, ~2km radius)
- Fails more often with specific neighborhoods that have fragmented street networks
- No retry or fallback to `/route` (A→B) when `/trip` (TSP) fails

**Relevant code**:
- `backend/app/services/routing.py` — `build_route()` returns `None` when OSRM trip fails
- `backend/app/services/routing.py` — `select_waypoints()` picks midpoints of untraveled streets without checking foot-routability

**Potential fixes**:
- Add retry with fewer waypoints when trip fails
- Fall back to simple A→B `/route` calls between pairs of waypoints
- Pre-filter waypoints by snapping to nearest routable point via OSRM `/nearest` before calling `/trip`
- Add better error messaging: "Could not find a walkable route through these streets. Try a different starting point or neighborhood."

---

## Issue 3: ACI deployment fails intermittently due to Docker Hub rate limiting

**Type**: Infrastructure
**Priority**: Low (workaround in place)
**Labels**: `infra`, `azure`, `docker`

**Description**:
Azure Container Instance `az container create` fails with `RegistryErrorResponse` when pulling images from Docker Hub (`index.docker.io`). This is a [known Azure CLI issue](https://github.com/Azure/azure-cli/issues/29300) (open since Jul 2024, 24+ comments, unresolved).

**Workaround applied**:
Images are pushed to Azure Container Registry (ACR) at `pacmantrackercr.azurecr.io` and ACI pulls from there instead. Both `prep-osrm-data.ps1` and `deploy-osrm.ps1` use ACR image references.

**Impact**:
- No current impact (workaround is in place)
- New images (e.g., if OSRM version is updated) must be pushed to ACR before deploying

**Maintenance note**:
To update the OSRM image:
```powershell
docker pull osrm/osrm-backend:latest
docker tag osrm/osrm-backend:latest pacmantrackercr.azurecr.io/osrm-backend:latest
docker push pacmantrackercr.azurecr.io/osrm-backend:latest
```

---

## Issue 4: Frontend health check should use the API client instead of raw fetch

**Type**: Tech debt
**Priority**: Low
**Labels**: `tech-debt`, `frontend`

**Description**:
The OSRM availability check in `RoutePage.tsx` constructs its own URL by stripping `/api/v1` from `VITE_API_URL` and appending `/health`. This is fragile and was the cause of the "Route suggestions unavailable" banner showing on the deployed site even though OSRM was running.

**Current code** (fixed in this branch but still fragile):
```tsx
const apiBase = import.meta.env.VITE_API_URL || "/api/v1";
const healthUrl = apiBase.replace(/\/api\/v1\/?$/, "/health");
fetch(healthUrl)
```

**Better approach**:
- Add a `health()` method to the API client that calls the correct URL
- Or add a `/api/v1/status` endpoint that includes `osrm_available` so the existing API client base URL works without string manipulation

---

## Issue 5: Route suggestion error messages are too generic

**Type**: Enhancement
**Priority**: Medium
**Labels**: `ux`, `frontend`

**Description**:
When route generation fails for any reason, the frontend shows "Failed to generate route. Please try again." This covers at least 4 different failure modes with different user actions:

| Actual Error | Current Message | Better Message |
|-------------|----------------|----------------|
| 401 Unauthorized | Failed to generate route | Session expired. Please log in again. |
| OSRM trip returns no route | Failed to generate route | Could not find a walkable route. Try a different starting point. |
| No streets in area (NOT_FOUND) | Failed to generate route | No streets found in this area. Try selecting a different neighborhood. |
| OSRM unavailable (503) | Failed to generate route | Route service temporarily unavailable. Try again in a minute. |

**Fix**: Check the `ApiClientError.code` field in the `handleSubmit` catch block and display appropriate messages.
