# Tasks: Deploy Routing Service

**Input**: Design documents from `/specs/003-deploy-routing-service/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: No application-level tests — this is an infrastructure-only feature. Verification uses the existing `/health` endpoint and manual route requests.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the deployment scripts skeleton and define shared variables used across all deployment steps.

- [x] T001 Create deployment script skeleton with shared variables and helper functions in infra/deploy-osrm.ps1
- [x] T002 [P] Create data preparation script skeleton with shared variables and helper functions in infra/prep-osrm-data.ps1

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Provision the Azure resources (Storage, VNet, subnets) that ALL user stories depend on. No OSRM container can be deployed until these exist.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Add Storage Account creation (Standard LRS) + File Share creation (osrm-data, 10 GB quota) + storage key retrieval to infra/deploy-osrm.ps1
- [x] T004 Add VNet creation (pacman-vnet, 10.0.0.0/16) with aci-subnet (10.0.1.0/24, delegated to Microsoft.ContainerInstance) and app-subnet (10.0.2.0/24) to infra/deploy-osrm.ps1
- [x] T005 [P] Add idempotency checks to T003 and T004 sections — skip creation if resources already exist using `az storage account show` and `az network vnet show` in infra/deploy-osrm.ps1

**Checkpoint**: Storage Account, File Share, VNet, and subnets exist in `pacman-tracker-rg`. All subsequent tasks can reference these resources.

---

## Phase 3: User Story 4 - Data Preparation Runs as One-Time Setup Step (Priority: P2) 🎯 Prerequisite

**Goal**: Run the OSRM data preparation pipeline as a one-time ACI job that downloads Washington state OSM data, extracts, partitions, and customizes it for foot routing, writing output to the Azure File Share.

**Independent Test**: After the prep job completes, list files on the Azure File Share and confirm `washington-latest.osrm` and associated files exist (~2-4 GB total).

> Note: US4 is P2 but must run before US1/US3 because the routing server needs prepared data. Placed here as a blocking prerequisite.

### Implementation for User Story 4

- [x] T006 [US4] Add data prep ACI creation command to infra/prep-osrm-data.ps1 — use `osrm/osrm-backend:latest` image, 2 vCPU, 4 GB RAM, mount osrm-data file share at /data, --restart-policy Never, command-line that downloads PBF then runs osrm-extract/partition/customize
- [x] T007 [US4] Add idempotency to prep script — check if /data/washington-latest.osrm already exists on the file share before running (verify file size > minimum threshold to detect partial downloads), skip if present and valid, in infra/prep-osrm-data.ps1
- [x] T008 [US4] Add progress monitoring and completion waiting to infra/prep-osrm-data.ps1 — poll `az container show --query instanceView.state` until Terminated, check exit code, stream logs with `az container logs --follow`
- [x] T009 [US4] Add cleanup step to infra/prep-osrm-data.ps1 — delete the prep ACI container group after successful completion to avoid idle billing

**Checkpoint**: US4 complete — Azure File Share contains prepared OSRM data files. Prep ACI has exited and been cleaned up.

---

## Phase 4: User Story 1 + User Story 3 - Route Suggestions Work in Production + Backend Connects to Cloud Routing Service (Priority: P1) 🎯 MVP

**Goal**: Deploy the OSRM routing server ACI and connect the backend to it so route suggestions work end-to-end in production.

**Independent Test**: Call `GET /health` on the deployed backend — `osrm_available` should be `true`. Then request a route suggestion and confirm a valid walking route is returned.

> Note: US1 and US3 are combined into a single phase because they are both P1 and deeply interdependent — the routing server (US1) is useless without backend connectivity (US3), and connectivity (US3) is useless without the server running (US1).

### Implementation for User Story 1 (Routing Server Deployment)

- [x] T010 [US1] Add OSRM routing server ACI creation to infra/deploy-osrm.ps1 — pre-flight check that washington-latest.osrm exists on the file share (abort with descriptive error if missing), then use `osrm/osrm-backend:latest` image, 1 vCPU, 2 GB RAM, mount osrm-data file share at /data, --restart-policy Always, command `osrm-routed --algorithm mld /data/washington-latest.osrm`, port 5000, deploy into aci-subnet
- [x] T011 [US1] Add ACI startup verification to infra/deploy-osrm.ps1 — wait for container state Running, retrieve private IP with `az container show --query ipAddress.ip`

### Implementation for User Story 3 (Backend Connectivity)

- [x] T012 [US3] Add App Service VNet Integration to infra/deploy-osrm.ps1 — `az webapp vnet-integration add` connecting backend to app-subnet
- [x] T013 [US3] Add OSRM_URL update to infra/deploy-osrm.ps1 — set backend app setting `OSRM_URL=http://<aci-private-ip>:5000` using `az webapp config appsettings set`, then restart backend with `az webapp restart`

### End-to-End Verification

- [x] T014 [US1] Add health check verification to infra/deploy-osrm.ps1 — call backend `/health` endpoint, assert `osrm_available` is `true`, retry with backoff

**Checkpoint**: US1 + US3 complete — Route suggestions work in production. `/health` reports `osrm_available: true`. Backend reaches OSRM via VNet private IP.

---

## Phase 5: User Story 2 - Routing Service Stays Available After Restarts (Priority: P2)

**Goal**: Ensure prepared map data persists across ACI restarts and the routing service recovers automatically.

**Independent Test**: Restart the routing ACI with `az container restart`. Wait up to 5 minutes, then call `/health` and confirm `osrm_available: true` again.

> Note: Most of US2 is already satisfied by the Azure File Share architecture (data persists independently of ACI lifecycle). This phase adds the restart verification and monitoring alert.

### Implementation for User Story 2

- [x] T015 [US2] Add ACI restart verification step to infra/deploy-osrm.ps1 — restart the OSRM ACI, wait for Running state, re-verify `/health` returns `osrm_available: true`
- [x] T016 [US2] Add Azure Monitor action group creation (pacman-alerts, email notification) to infra/deploy-osrm.ps1
- [x] T017 [US2] Add Azure Monitor metric alert on ACI RestartCount > 3 in 5-minute window to infra/deploy-osrm.ps1 — scoped to the OSRM ACI resource ID, triggering the pacman-alerts action group

**Checkpoint**: US2 complete — ACI restart recovers automatically, monitoring alerts catch crash loops.

---

## Phase 6: User Story 5 - Deployment Is Documented and Repeatable (Priority: P3)

**Goal**: Document the routing service deployment in the existing deployment guide so operators can deploy, redeploy, or troubleshoot without tribal knowledge.

**Independent Test**: A reader unfamiliar with the routing service can follow the documented steps to deploy from scratch.

### Implementation for User Story 5

- [x] T018 [P] [US5] Add "2.5 Deploy Routing Service (OSRM)" section to AZURE_DEPLOY.md — covering variables, prerequisites, storage setup, VNet setup, data preparation, server deployment, backend connectivity, monitoring, and verification
- [x] T019 [P] [US5] Add "Redeploying — Routing Service" subsection to the existing Redeploying section in AZURE_DEPLOY.md — covering restart, data refresh, and cost notes
- [x] T020 [P] [US5] Update cost estimate table in AZURE_DEPLOY.md — add ACI (~$20-40/month), Storage Account (~$0.20/month), total updated from ~$18 to ~$38-58/month
- [x] T021 [US5] Add OSRM deployment and verification steps to infra/deploy-prod.ps1 — integrate calls to deploy-osrm.ps1 and prep-osrm-data.ps1 with appropriate flags (skip if already deployed), add OSRM health verification after backend deployment

**Checkpoint**: US5 complete — Deployment guide covers routing service end-to-end. `deploy-prod.ps1` handles OSRM as part of the full deployment pipeline.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, cleanup, and documentation polish.

- [x] T022 [P] Add `--help` flag documentation and parameter validation to infra/deploy-osrm.ps1 and infra/prep-osrm-data.ps1
- [x] T023 [P] Add error handling with descriptive messages to infra/deploy-osrm.ps1 — catch Azure CLI failures, surface actionable error messages (e.g., "Storage account name taken", "Subnet delegation conflict")
- [ ] T024 Run quickstart.md validation — execute the quickstart steps against a live Azure subscription and verify end-to-end route suggestion works
- [ ] T025 [US4] Verify local dev unchanged (FR-009) — run `docker compose up osrm -d`, confirm OSRM responds at localhost:5000, run backend test suite to confirm no regressions from infrastructure changes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US4 Data Prep (Phase 3)**: Depends on Foundational — BLOCKS US1/US3 (routing server needs data)
- **US1 + US3 Routing + Connectivity (Phase 4)**: Depends on US4 completion (data must be prepared)
- **US2 Persistence + Monitoring (Phase 5)**: Depends on Phase 4 (ACI must exist to restart/monitor)
- **US5 Documentation (Phase 6)**: Can start after Phase 4, runs in parallel with Phase 5
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US4 (P2)**: Blocking prerequisite — must complete before US1/US3 despite P2 priority
- **US1 + US3 (P1)**: Combined phase — interdependent, cannot test US1 without US3 or vice versa
- **US2 (P2)**: Depends on US1 (ACI must be running to restart and monitor)
- **US5 (P3)**: Mostly independent of US2 — can run in parallel after Phase 4

### Within Each Phase

- Tasks without [P] marker execute sequentially in listed order
- Tasks with [P] marker can execute in parallel with other [P] tasks in the same phase
- T010-T011 (server) must complete before T012-T013 (connectivity) — need the ACI IP
- T014 (verification) must be last in Phase 4

### Parallel Opportunities

- T001 and T002 can run in parallel (different script files)
- T018, T019, T020 can run in parallel (different sections of AZURE_DEPLOY.md)
- T022 and T023 can run in parallel (different concerns)
- Phase 5 (US2) and Phase 6 (US5) can overlap after Phase 4 completes

---

## Parallel Example: Phase 1 (Setup)

```text
Task T001: Create deployment script skeleton in infra/deploy-osrm.ps1
Task T002: Create data preparation script skeleton in infra/prep-osrm-data.ps1
→ Both create different files, no dependencies between them
```

## Parallel Example: Phase 6 (Documentation)

```text
Task T018: Add deployment section to AZURE_DEPLOY.md
Task T019: Add redeployment section to AZURE_DEPLOY.md
Task T020: Update cost estimate in AZURE_DEPLOY.md
→ All modify AZURE_DEPLOY.md but different sections — can be parallelized with careful merging
```

---

## Implementation Strategy

### MVP First (US4 + US1 + US3 — Phases 1-4)

1. Complete Phase 1: Setup (script skeletons)
2. Complete Phase 2: Foundational (Storage + VNet)
3. Complete Phase 3: US4 Data Preparation (one-time ACI job)
4. Complete Phase 4: US1 + US3 (routing server + backend connectivity)
5. **STOP and VALIDATE**: `/health` returns `osrm_available: true`, route suggestion returns valid geometry

### Incremental Delivery

1. Complete Phases 1-4 → **MVP: Route suggestions work in production**
2. Add Phase 5 (US2) → Restart resilience verified, crash-loop alert active
3. Add Phase 6 (US5) → Deployment guide complete for operators
4. Add Phase 7 → Scripts polished with error handling and help text

### Execution Notes

- This feature is **infrastructure-only** — no application code changes
- All tasks produce PowerShell scripts or documentation, not Python/TypeScript code
- The existing backend OSRM client code, health check, and graceful degradation work unchanged
- The `OSRM_URL` environment variable is the only configuration change to the running backend
- Local development with Docker Compose is completely unaffected

---

## Notes

- [P] tasks = different files or sections, no dependencies
- [Story] label maps task to specific user story for traceability
- US4 (data prep) is P2 but placed before P1 stories because it's a blocking prerequisite
- US1 and US3 are combined into one phase because they're inseparable for end-to-end verification
- No application test tasks — verification is via existing health endpoint and manual route requests
- Commit after each task or logical phase
- Stop at any checkpoint to validate independently
