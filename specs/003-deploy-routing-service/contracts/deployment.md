# Deployment Contract: OSRM Routing Service

**Feature**: 003-deploy-routing-service  
**Date**: 2026-03-17

This feature adds no new application API endpoints. The "contracts" are the deployment script interface and the Azure resource configuration that operators interact with.

## Deployment Script Interface

### New Variables (added to AZURE_DEPLOY.md and deploy-prod.ps1)

| Variable | Default | Description |
|----------|---------|-------------|
| `$storageAccountName` | `"pacmantrackersa"` | Azure Storage Account for OSRM file share |
| `$vnetName` | `"pacman-vnet"` | VNet containing ACI and App Service subnets |
| `$aciSubnet` | `"aci-subnet"` | Subnet delegated to ACI (10.0.1.0/24) |
| `$appSubnet` | `"app-subnet"` | Subnet for App Service VNet Integration (10.0.2.0/24) |
| `$osrmAciName` | `"pacman-osrm"` | ACI container group name for OSRM routing server |
| `$osrmPrepAciName` | `"pacman-osrm-prep"` | ACI container group name for one-time data prep job |
| `$osrmFileShare` | `"osrm-data"` | Azure File Share name for OSRM data |

### Existing Variable Changes

| Variable | Current Value | New Value | Reason |
|----------|--------------|-----------|--------|
| `OSRM_URL` (production) | Not set | `http://<aci-private-ip>:5000` | Backend needs to reach cloud OSRM |
| `OSRM_URL` (local dev) | `http://localhost:5000` | Unchanged | Local dev unaffected |

## Deployment Steps Contract

### First-Time Setup (sequential, idempotent)

```
Step 1: Create Storage Account + File Share
Step 2: Create VNet + subnets (aci-subnet delegated to ACI, app-subnet for App Service)
Step 3: Run Data Prep ACI job (mount file share, download + extract + partition + customize, exit)
Step 4: Wait for prep ACI to complete (az container show --query instanceView.state)
Step 5: Deploy Routing Server ACI (mount file share, osrm-routed, restart-policy Always)
Step 6: Add App Service VNet Integration (connect backend to app-subnet)
Step 7: Update backend OSRM_URL to ACI private IP
Step 8: Create Azure Monitor alert on ACI RestartCount
Step 9: Verify: call /health endpoint, confirm osrm_available: true
```

### Redeployment (routing service only)

```
Step 1: az container restart --resource-group $rg --name pacman-osrm
Step 2: Verify: call /health endpoint, confirm osrm_available: true
```

### Data Refresh (when OSM data needs updating)

```
Step 1: Delete old prep data from file share (optional, prep script is idempotent)
Step 2: Re-run Data Prep ACI job
Step 3: Restart Routing Server ACI to pick up new data
```

## Health Check Contract (existing, unchanged)

The backend's existing health check and route suggestion error handling remain as-is:

| Endpoint | Field | Value When OSRM Up | Value When OSRM Down |
|----------|-------|--------------------|--------------------|
| `GET /health` | `osrm_available` | `true` | `false` |
| `POST /api/v1/routes/suggest` | error | N/A (returns route) | `{"error": {"code": "OSRM_UNAVAILABLE", ...}}` (503) |

No changes to application code are required.
