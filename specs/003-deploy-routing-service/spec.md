# Feature Specification: Deploy Routing Service

**Feature Branch**: `003-deploy-routing-service`  
**Created**: 2026-03-17  
**Status**: Draft  
**Input**: User description: "I want to also deploy the routing service, since we haven't done that yet"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Route Suggestions Work in Production (Priority: P1)

A user opens the deployed application in their browser and requests a walking route suggestion for untraveled streets. The system returns a calculated route using the cloud-hosted routing service, just as it does in local development. Today, route suggestions are unavailable in production because the routing engine (OSRM) only runs locally.

**Why this priority**: This is the core value — without a deployed routing service, the route suggestion feature is completely non-functional in production. Users see "Route suggestions unavailable" for every request.

**Independent Test**: Navigate to the deployed app, select a neighborhood, and request a route suggestion. The system returns a valid walking route with turn-by-turn geometry instead of an OSRM_UNAVAILABLE error.

**Acceptance Scenarios**:

1. **Given** the application is deployed and the routing service is running, **When** a user requests a route suggestion, **Then** the system returns a walking route with geometry, distance, and duration.
2. **Given** the application is deployed and the routing service is running, **When** the backend health check endpoint is called, **Then** the response includes `osrm_available: true`.
3. **Given** the routing service is freshly deployed, **When** the first route request arrives, **Then** it completes successfully without requiring manual data preparation steps.

---

### User Story 2 - Routing Service Stays Available After Restarts (Priority: P2)

When the cloud environment restarts (due to maintenance, scaling events, or redeployment), the routing service recovers automatically and resumes serving route requests. Pre-processed map data persists across restarts so the service does not need to re-download and re-process gigabytes of OpenStreetMap data each time.

**Why this priority**: Without persistence, every restart triggers a multi-hour data preparation pipeline (download ~800 MB OSM file, extract, partition, customize), leaving route suggestions unavailable for an extended period.

**Independent Test**: After the routing service is running and serving requests, restart it. Verify that route requests succeed again within a few minutes without re-running the data preparation pipeline.

**Acceptance Scenarios**:

1. **Given** the routing service was previously running with prepared data, **When** the service restarts, **Then** it becomes available within 5 minutes using the previously prepared data.
2. **Given** the routing service has persistent storage, **When** a redeployment occurs, **Then** the pre-processed map data is not lost.

---

### User Story 3 - Backend Connects to Cloud Routing Service (Priority: P1)

The deployed backend API connects to the cloud-hosted routing service instead of localhost. The connection URL is configurable per environment, so local development continues to use the local Docker-based OSRM server while production uses the cloud instance.

**Why this priority**: Equal priority to US1 because without proper connectivity configuration, the backend cannot reach the routing service even if it's deployed.

**Independent Test**: Deploy the backend with the routing service URL configured. Call the `/health` endpoint and verify `osrm_available` is `true`. Then request a route suggestion and confirm it returns valid results.

**Acceptance Scenarios**:

1. **Given** the backend is deployed with the routing service URL configured, **When** the health endpoint is called, **Then** `osrm_available` returns `true`.
2. **Given** the backend is running locally, **When** OSRM_URL is set to `http://localhost:5000`, **Then** local development continues to work unchanged.
3. **Given** the routing service URL is misconfigured, **When** a route request is made, **Then** the existing graceful degradation (OSRM_UNAVAILABLE error) handles it cleanly.

---

### User Story 4 - Data Preparation Runs as a One-Time Setup Step (Priority: P2)

The map data preparation pipeline (downloading OSM data, extracting, partitioning, and customizing it for walking routes) runs as a separate one-time setup step before the routing service can serve requests. This step should be documented and repeatable — it only needs to re-run when the map data needs to be refreshed (e.g., when OSM data gets a major update).

**Why this priority**: Data preparation is a prerequisite for US1 but only needs to run once. The process is already well-defined from the local Docker setup.

**Independent Test**: Run the data preparation step from scratch. Verify the prepared data is stored persistently and the routing service can serve requests using it.

**Acceptance Scenarios**:

1. **Given** the deployment environment has no prepared map data, **When** the data preparation step is executed, **Then** it downloads, extracts, partitions, and customizes the Washington state OSM data for foot routing.
2. **Given** the data preparation step has completed, **When** the routing service starts, **Then** it loads the prepared data and begins serving requests.

---

### User Story 5 - Deployment Is Documented and Repeatable (Priority: P3)

The deployment process for the routing service is documented alongside the existing backend and frontend deployment guides. An operator can follow the documentation to deploy, update, or redeploy the routing service without tribal knowledge.

**Why this priority**: Important for maintainability but doesn't block end-user functionality. The existing deployment guide already covers the backend and frontend — this extends it.

**Independent Test**: A person unfamiliar with the routing service setup can follow the documentation to deploy it from scratch.

**Acceptance Scenarios**:

1. **Given** the deployment documentation exists, **When** an operator follows it step-by-step, **Then** the routing service is deployed and serving route requests.
2. **Given** the routing service needs to be redeployed, **When** the operator follows the redeployment section, **Then** the update completes without data loss.

---

### Edge Cases

- What happens when the routing service runs out of memory while loading map data?
- How does the system behave when the routing service is deployed but data preparation hasn't been run yet?
- What happens if the OSM data download fails partway through during data preparation?
- How does the backend behave if the routing service becomes unreachable after initially being available? (Already handled by existing OSRM health check with 60-second cache.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The routing service MUST be deployed as an Azure Container Instance in the same resource group as the existing backend and frontend services, with 1 vCPU and 2 GB RAM (may be reduced to 0.5 vCPU / 1.5 GB if monthly cost exceeds SC-005 budget).
- **FR-002**: The routing service MUST serve OSRM-compatible HTTP routing requests using the foot (walking) profile.
- **FR-003**: The routing service MUST support the `/nearest`, `/trip`, and `/route` OSRM endpoints that the backend already consumes.
- **FR-004**: The routing service MUST use pre-processed Washington state OpenStreetMap data with the MLD algorithm.
- **FR-005**: The routing service MUST have pre-processed map data stored on an Azure File Share that is mounted into the ACI, surviving restarts and redeployments.
- **FR-006**: The backend MUST be configurable to point at the cloud-hosted routing service URL via the existing `OSRM_URL` environment variable.
- **FR-007**: The data preparation pipeline (download, extract, partition, customize) MUST be executable as a one-time ACI job that mounts the same Azure File Share as the routing service, writes the prepared data, and exits on completion.
- **FR-008**: The deployment process MUST be documented in the existing deployment guide, covering initial setup, data preparation, and redeployment.
- **FR-009**: Local development MUST continue to work unchanged using the existing Docker Compose-based OSRM setup.
- **FR-010**: The routing service MUST be deployed into a VNet with a private IP, accessible only to the backend via VNet integration. It MUST NOT be exposed to the public internet.
- **FR-011**: The deployment MUST include an Azure Monitor alert on ACI restart count to detect crash loops. The existing backend health check (60-second cache, `osrm_available` flag) serves as the primary availability signal.

### Key Entities

- **Routing Service**: The OSRM routing engine instance running in the cloud, serving HTTP routing requests on a known port/URL.
- **Map Data**: Pre-processed OpenStreetMap data (Washington state, foot profile, MLD algorithm) stored on an Azure File Share and mounted into the ACI. Approximately 2-4 GB when prepared.
- **Data Preparation Pipeline**: A short-lived ACI container that runs the sequence (download OSM PBF → osrm-extract → osrm-partition → osrm-customize), writes output to the shared Azure File Share, then exits. Mirrors the existing Docker Compose `prepare` profile.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Route suggestions return valid walking routes in the deployed application (zero OSRM_UNAVAILABLE errors during normal operation).
- **SC-002**: The `/health` endpoint reports `osrm_available: true` when the routing service is deployed and running.
- **SC-003**: The routing service recovers from a restart and resumes serving requests within 5 minutes without re-running data preparation.
- **SC-004**: The data preparation pipeline completes successfully in a single execution without manual intervention beyond launching it.
- **SC-005**: The deployment adds ~$40/month to the existing cloud hosting costs (~$18/month previously, ~$58/month total). ACI at 1 vCPU / 2 GB runs ~$40/month; can be reduced to 0.5 vCPU / 1.5 GB (~$22/month) if needed.
- **SC-006**: Route suggestion requests complete within 5 seconds end-to-end (user request to response) for routes up to 10 km.

## Clarifications

### Session 2026-03-17

- Q: How should the routing service be hosted (same App Service, ACI, or separate plan)? → A: Azure Container Instance (separate container, ~1 vCPU / 2 GB RAM)
- Q: What network exposure is acceptable for the routing service (public IP or VNet-integrated)? → A: VNet-integrated — private IP, only reachable from the backend's VNet
- Q: Where should prepared map data be stored for persistence across ACI restarts? → A: Azure File Share mounted into the ACI
- Q: How should the one-time data preparation pipeline be executed in the cloud? → A: One-time ACI job that mounts the same file share, runs the pipeline, then exits
- Q: What observability is needed for the routing service? → A: Existing backend health check plus ACI restart count monitoring via Azure Monitor basic alerts

## Assumptions

- The existing Azure resource group from the current deployment guide will be reused. The routing service runs on its own Azure Container Instance, not on the shared App Service plan.
- Washington state foot-profile OSM data is sufficient for all current users (the app currently focuses on Seattle-area coverage).
- The OSRM container image (`osrm/osrm-backend:latest`) is suitable for cloud deployment.
- The existing backend OSRM client code (OSRMClient class) requires no changes — only the `OSRM_URL` configuration value needs to change for production.
- The existing graceful degradation (OSRM health check, OSRM_UNAVAILABLE error handling) will continue to function as-is with the cloud-hosted routing service.
- Persistent storage for map data is available in the cloud environment.
- The backend App Service B1 tier supports Regional VNet Integration natively; no tier upgrade is needed (confirmed in research R2).

## Scope Boundaries

### In Scope

- Deploying the OSRM routing service to the cloud
- Persistent storage for pre-processed map data
- Running the data preparation pipeline in the cloud
- Configuring the backend to connect to the cloud routing service
- Updating deployment documentation
- Cost-effective hosting appropriate for a PoC

### Out of Scope

- Multi-region OSRM deployment or geographic load balancing
- Automated OSM data refresh schedules
- Support for routing profiles other than foot/walking
- Support for map data beyond Washington state
- Auto-scaling the routing service based on load
- CI/CD pipeline integration for the routing service
- Custom OSRM profiles or configuration tuning
