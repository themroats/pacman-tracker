# Implementation Plan: Deploy Routing Service

**Branch**: `003-deploy-routing-service` | **Date**: 2026-03-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-deploy-routing-service/spec.md`

## Summary

Deploy the OSRM routing service to Azure so route suggestions work in production. Currently, the backend and frontend are deployed (App Service + Static Web Apps) but OSRM only runs locally, so every production route request fails with OSRM_UNAVAILABLE. The solution: deploy OSRM as an Azure Container Instance in a VNet with persistent map data on an Azure File Share, connected to the backend via VNet Integration. No application code changes are required — only infrastructure and configuration.

## Technical Context

**Language/Version**: PowerShell (Azure CLI commands), Shell scripts (ACI entrypoints)
**Primary Dependencies**: Azure CLI, `osrm/osrm-backend:latest` container image
**Storage**: Azure File Share (Standard LRS, ~2.5 GB OSRM data)
**Testing**: Manual verification via `/health` endpoint (`osrm_available: true`)
**Target Platform**: Azure (ACI + VNet + Storage Account)
**Project Type**: Infrastructure deployment (no new application code)
**Performance Goals**: Route requests < 5 seconds e2e for routes up to 10 km (SC-006)
**Constraints**: ~$40/month additional cost (SC-005); VNet-isolated, no public exposure (FR-010)
**Scale/Scope**: Single ACI instance, single user PoC

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. API-First Design | **PASS** | No new API endpoints. Existing OSRM client code unchanged. |
| II. Test-First Development | **PASS (N/A)** | No new application code; verification is via health endpoint and manual routing test. |
| III. Data Privacy by Design | **PASS** | OSRM serves only public OSM data. No user data involved. VNet isolation prevents public access. |
| IV. Simplicity & Incremental Delivery | **PASS** | Uses standard Azure services (ACI, File Share, VNet). No custom abstractions. Each step is independently verifiable. |
| Technology Standards | **PASS** | No changes to Python/FastAPI/React stack. Uses existing `OSRM_URL` env var pattern. |
| Development Workflow | **PASS** | Feature branch `003-deploy-routing-service`. Changes are to infra scripts and docs only. |

**Gate result**: All principles pass. No violations to justify.

### Post-Phase-1 Re-check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. API-First Design | **PASS** | Confirmed: no new endpoints, no code changes. |
| II. Test-First Development | **PASS (N/A)** | Confirmed: infrastructure-only, verified by existing health check. |
| III. Data Privacy by Design | **PASS** | Confirmed: ACI in VNet, private IP only. |
| IV. Simplicity & Incremental Delivery | **PASS** | Deployment is 8 sequential CLI steps, each idempotent. |

## Project Structure

### Documentation (this feature)

```text
specs/003-deploy-routing-service/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: Azure ACI + VNet + File Share research
├── data-model.md        # Azure resource topology
├── quickstart.md        # Step-by-step deployment guide
├── contracts/
│   └── deployment.md    # Deployment script interface contract
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
# Files MODIFIED by this feature:
AZURE_DEPLOY.md                        # Add Section 2.5: Deploy Routing Service
infra/deploy-prod.ps1                  # Add OSRM deployment steps + verification

# Files CREATED by this feature:
infra/deploy-osrm.ps1                  # Standalone OSRM deployment script
infra/prep-osrm-data.ps1               # One-time data preparation script

# Files UNCHANGED:
backend/app/config.py                  # OSRM_URL already configurable
backend/app/services/routing.py        # OSRMClient already parameterized
backend/app/main.py                    # Health check already reports osrm_available
docker-compose.yml                     # Local dev unchanged
```

**Structure Decision**: This feature adds infrastructure scripts to the existing `infra/` directory and extends the existing deployment guide. No new application directories. The two new scripts (`deploy-osrm.ps1`, `prep-osrm-data.ps1`) follow the same pattern as the existing `deploy-prod.ps1`.

## Complexity Tracking

No constitution violations. This section is intentionally empty.
