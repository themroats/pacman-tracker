# Feature Specification: MCP Server for Copilot Integration

**Feature Branch**: `007-mcp-server`
**Created**: 2026-03-30
**Status**: Planning
**Input**: User description: "Build an MCP server that exposes pacman-tracker backend capabilities as tools for LLM/Copilot integration. Start with API wrapper approach, expand to direct analytics later."

## Overview

A standalone MCP (Model Context Protocol) server that exposes the pacman-tracker backend as tools and resources to any MCP-compatible client (Claude Desktop, VS Code Copilot Chat, custom apps). Uses the Python MCP SDK (`mcp[cli]`) with FastMCP. Communicates with the backend over HTTP via `httpx`.

### Architecture

- **Location**: `mcp-server/` (top-level, alongside `backend/` and `frontend/`)
- **Transport**: stdio (for Claude Desktop / VS Code integration)
- **Backend communication**: HTTP calls to FastAPI backend
- **Backend URL**: Configurable via `PACMAN_API_URL` env var (defaults to `http://localhost:8000`). Can point to production URL for normal use or localhost for testing.
- **Auth**: Automated Strava OAuth via temporary localhost HTTP server (see User Story 1). Token cached locally. Multi-token support via new `UserToken` table so MCP and frontend sessions coexist.

### Auth Design

The existing backend stores a single `access_token_hash` per user on the `User` model. If two clients (frontend + MCP) each do OAuth, the second overwrites the first, breaking it. To support concurrent sessions:

1. **New `UserToken` model**: stores multiple active token hashes per user, each tagged with a `client_name` ("frontend", "mcp", etc.).
2. **Updated `get_current_user`**: queries `UserToken.token_hash` instead of `User.access_token_hash`.
3. **MCP OAuth flow**: MCP server spins up a temporary localhost HTTP server, initiates Strava OAuth directly (using the app's client_id/secret), receives the callback, exchanges the code via the backend, and caches the token locally.

Strava validates `redirect_uri` against the app's **Authorization Callback Domain**, not a specific URL. Since `localhost` is whitelisted by default, the MCP server can use any localhost port as its redirect URI without any Strava configuration changes.

Token expiry (~6 hours) is acceptable. If the token expires, the MCP server detects the 401 and prompts the user to re-authenticate (browser opens, one click).

## User Scenarios & Testing

### User Story 1 — Backend Auth: Multi-Token Support (Priority: P0)

As a developer, I want the backend to support multiple active access tokens per user, so that the MCP server and frontend can be authenticated simultaneously without invalidating each other.

**Why this priority**: Without this, the MCP server's OAuth login would invalidate the frontend's session. This is the foundational change that enables MCP auth.

**Implementation**:
- New `UserToken` model: `id`, `user_id` (FK → User), `token_hash` (String(64), unique, indexed), `client_name` (String), `created_at` (datetime)
- Alembic migration: create `user_tokens` table, migrate existing `User.access_token_hash` data into it (with `client_name="frontend"`), drop `access_token_hash` column from `User`
- Update `get_current_user` in `deps.py`: query `UserToken` instead of `User`, load user via relationship
- Update auth callback in `auth.py`: INSERT into `UserToken(client_name="frontend")` instead of setting `User.access_token_hash`
- Update logout: DELETE the `UserToken` row for the current token

**Acceptance Scenarios**:

1. **Given** a user logged in via the frontend (token_A), **When** the MCP server authenticates and stores token_B, **Then** both tokens are valid and both clients can make API calls simultaneously.
2. **Given** two active tokens for a user, **When** the frontend logs out, **Then** only the frontend's token is invalidated; the MCP token continues to work.
3. **Given** a user with no tokens, **When** they authenticate via the frontend, **Then** a `UserToken` row is created with `client_name="frontend"`.
4. **Given** the existing database with `User.access_token_hash` data, **When** the migration runs, **Then** existing hashes are migrated to `UserToken` rows and the column is dropped.

---

### User Story 2 — MCP Server Scaffolding (Priority: P0)

As a developer, I want a working MCP server package that connects to the backend API, so that I can build tools on top of it.

**Why this priority**: Foundation for all MCP tools.

**Implementation**:
- New `mcp-server/` directory with `pyproject.toml` (deps: `mcp[cli]`, `httpx`), `src/pacman_mcp/` package
- `config.py`: reads `PACMAN_API_URL` (default `http://localhost:8000`) from environment
- `client.py`: `PacmanClient` class — async httpx wrapper with bearer token auth, timeout handling, friendly error messages on connection failure / non-200 responses
- `server.py`: FastMCP instance ("Pacman Tracker"), stdio entry point
- `.vscode/mcp.json`: VS Code MCP server config pointing to `uv run --directory mcp-server mcp run src/pacman_mcp/server.py`

**Acceptance Scenarios**:

1. **Given** the MCP server is configured in VS Code, **When** Copilot Chat starts, **Then** the server connects via stdio and tools are discoverable.
2. **Given** `PACMAN_API_URL` points to a running backend, **When** any tool is called, **Then** the server authenticates with the bearer token and returns data.
3. **Given** the backend is unreachable, **When** a tool is called, **Then** a clear error message is returned (not a stack trace).

---

### User Story 3 — MCP Auth Flow (Priority: P0)

As a user, I want the MCP server to automatically authenticate me via Strava when I first use it, so I don't have to manually copy tokens.

**Why this priority**: Without auth, no tools work. The automated flow removes friction.

**Implementation**:
- `auth.py` in MCP server: CLI auth command and auto-auth on first tool call
- On auth trigger:
  1. Start a temporary HTTP server on a fixed localhost port (e.g., 8585)
  2. Build the Strava authorize URL directly (using `STRAVA_CLIENT_ID` from env, `redirect_uri=http://localhost:8585/callback`)
  3. Open user's browser to the Strava authorize URL
  4. Receive callback with `code` and `scope` at the temp server
  5. Exchange the code for tokens by calling `POST https://www.strava.com/oauth/token` with client_id, client_secret, code, grant_type
  6. Call the backend to register the token: `POST /api/v1/auth/mcp/register` with the access token → backend creates `UserToken(client_name="mcp")`
  7. Cache the access token in `~/.pacman-mcp/credentials.json`
  8. Show "Auth successful — you can close this tab" in browser
  9. Shut down temp server
- On subsequent starts: read cached token, validate with a lightweight backend call. If 401 → re-run auth flow.
- New backend endpoint: `POST /api/v1/auth/mcp/register` — accepts a valid Strava access token, looks up the user by Strava athlete info, creates a `UserToken` row with `client_name="mcp"`, returns user info.

**Acceptance Scenarios**:

1. **Given** no cached credentials, **When** the MCP server starts and a tool is called, **Then** the browser opens to Strava authorization, and after one click the token is cached and the tool call succeeds.
2. **Given** a valid cached token, **When** the MCP server starts, **Then** no browser interaction is needed and tools work immediately.
3. **Given** an expired cached token, **When** a tool call returns 401, **Then** the auth flow re-triggers automatically and the user sees the browser prompt.
4. **Given** the user is already authorized on Strava for this app, **When** the auth flow runs, **Then** Strava auto-approves (no manual click needed) and the flow completes in seconds.

---

### User Story 4 — `lookup_location` Tool (Priority: P1)

As a user talking to an LLM, I want to refer to cities and neighborhoods by name, and have the MCP server resolve them to IDs, so I can interact naturally.

**Why this priority**: Critical dependency for all other tools — the LLM says "Capitol Hill" not ID 42.

**Implementation**:
- Fetches `GET /api/v1/cities` and `GET /api/v1/cities/{id}/neighborhoods`
- Case-insensitive substring matching on city and neighborhood names
- Returns matches with IDs, names, and current coverage %

**Input**: `query` (string) — e.g. "capitol hill", "fremont", "seattle"
**Output**: List of matching cities and/or neighborhoods with IDs, names, coverage %

**Acceptance Scenarios**:

1. **Given** a city named "Seattle" exists, **When** I call `lookup_location("seattle")`, **Then** it returns the city with its ID and coverage %.
2. **Given** neighborhoods "Fremont" and "Freemont Park" exist, **When** I call `lookup_location("fremont")`, **Then** both appear ranked by match quality.
3. **Given** no match exists, **When** I call `lookup_location("narnia")`, **Then** an empty result with a helpful message is returned.

---

### User Story 5 — `get_coverage_summary` Tool (Priority: P1)

As a user, I want to ask about my street coverage in natural language and get a summary, so I can track my progress conversationally.

**Why this priority**: The core value proposition of the MCP integration — "How much of Capitol Hill have I covered?"

**Implementation**:
- Accepts optional `city` and `neighborhood` string params (natural language names)
- Resolves names to IDs internally (same logic as `lookup_location`)
- Calls `GET /api/v1/coverage/city/{id}` or `GET /api/v1/coverage/neighborhood/{id}`
- Formats response: coverage %, streets traveled/total, distance traveled/total, neighborhood breakdown (if city-level), milestone proximity

**Input**: `city` (string, optional), `neighborhood` (string, optional)
**Output**: Coverage stats with milestone proximity

**Acceptance Scenarios**:

1. **Given** a city with 60% coverage, **When** I call `get_coverage_summary(city="Seattle")`, **Then** it returns city-level stats plus per-neighborhood breakdown.
2. **Given** a neighborhood with 73% coverage, **When** I call `get_coverage_summary(neighborhood="Fremont")`, **Then** it returns street counts, distance, and "2% from 75% milestone".
3. **Given** neither city nor neighborhood is provided, **When** I call `get_coverage_summary()`, **Then** it returns a summary across all cities.

---

### User Story 6 — `user://profile` Resource (Priority: P1)

As an LLM client, I want ambient context about the user, so I can give informed responses without the user repeating themselves.

**Why this priority**: Resources provide passive context — the LLM always knows who you are.

**Implementation**:
- MCP resource at URI `user://profile`
- Calls `GET /api/v1/progress/stats` and `GET /api/v1/cities`
- Returns: user display name, total activities, total distance, cities with coverage %, last sync time

**Acceptance Scenarios**:

1. **Given** a user with activities, **When** the LLM reads the `user://profile` resource, **Then** it contains the user's name, total stats, and per-city coverage.
2. **Given** the backend is unreachable, **When** the resource is read, **Then** a graceful error message is returned.

---

## Implemented Tools & Resources

| Tool/Resource | Status | Notes |
|---------------|--------|-------|
| `lookup_location` | ✅ Done | City/neighborhood name resolution |
| `get_coverage_summary` | ✅ Done | City or neighborhood coverage stats + milestone proximity |
| `get_untraveled_streets` | ✅ Done | Untraveled streets grouped by name, sorted by length |
| `get_progress_summary` | ✅ Done | Timeline, milestones, growth rate |
| `get_neighborhood_priority` | ✅ Done | Ranked by fewest streets to next milestone |
| `user://profile` | ✅ Done | Ambient user context with overall stats |

## Feature Backlog (Future Stories)

### Phase 2 — Routes & Planning (requires write operations)

| Feature | Tool | Priority | Endpoint | Notes |
|---------|------|----------|----------|-------|
| Suggest route | `suggest_route` | P2 | `POST /api/v1/routes/suggest` | NL params: distance, start point, preferences, variation |
| Create plan | `create_coverage_plan` | P2 | `POST /api/v1/plans/neighborhood` | Multi-route plan for a neighborhood |
| Plan status | `get_plan_status` | P2 | `GET /api/v1/plans/{id}` | Progress through an active plan |
| Export GPX | `export_route_gpx` | P3 | `GET /api/v1/routes/{id}/export/gpx` | GPX file content for watch upload |

### Phase 3 — Analytics (requires new backend endpoints)

| Feature | Tool | Priority | Notes |
|---------|------|----------|-------|
| Activity impact | `get_activity_impact` | P2 | What did yesterday's run cover? Needs new endpoint |
| Projected completion | `get_projected_completion` | P3 | Linear regression on CoverageSnapshot data. Needs new endpoint |
| Habit analysis | `get_habit_analysis` | P3 | Activity frequency by day/time, streaks. Needs new endpoint |
| Personal records | `get_personal_records` | P3 | Longest run, fastest pace, most streets in one run. Needs new endpoint |

### Phase 4 — Advanced

| Feature | Tool | Priority | Notes |
|---------|------|----------|-------|
| Compare routes | `compare_route_options` | P4 | Side-by-side coverage impact comparison |
| Street clusters | `get_street_completion_clusters` | P4 | PostGIS ST_ClusterDBSCAN on untraveled streets |

### MCP Resources (Future)

| Resource URI | Content | Phase |
|---|---|---|
| `user://recent-activities` | Last 10 activities with basic stats | Phase 2 |
| `user://active-plans` | Current coverage plans and progress | Phase 2 |
| `city://{name}/coverage` | Neighborhood breakdown for a city | Phase 2 |

## Technical Requirements

- Python package in `mcp-server/` using `mcp[cli]` SDK with FastMCP
- `httpx` for async HTTP calls to backend
- stdio transport for VS Code / Claude Desktop
- Environment variables: `PACMAN_API_URL`, `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`
- Credential caching in `~/.pacman-mcp/credentials.json`
- Error handling: backend errors → user-friendly MCP tool error messages (no tracebacks)
- VS Code MCP configuration in `.vscode/mcp.json`

## Key Files

### New (MCP server)
- `mcp-server/pyproject.toml`
- `mcp-server/src/pacman_mcp/__init__.py`
- `mcp-server/src/pacman_mcp/server.py` — FastMCP instance, tool/resource definitions, entry point
- `mcp-server/src/pacman_mcp/client.py` — `PacmanClient` async httpx wrapper
- `mcp-server/src/pacman_mcp/config.py` — env var configuration
- `mcp-server/src/pacman_mcp/auth.py` — OAuth flow with temp HTTP server, credential caching
- `.vscode/mcp.json` — VS Code MCP server registration

### Modified (Backend)
- `backend/app/models/` — new `UserToken` model
- `backend/app/api/deps.py` — `get_current_user` queries `UserToken`
- `backend/app/api/auth.py` — creates `UserToken` rows, new `/mcp/register` endpoint
- `backend/alembic/versions/` — migration for `user_tokens` table
