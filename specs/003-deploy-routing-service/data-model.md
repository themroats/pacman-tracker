# Data Model: Deploy Routing Service

**Feature**: 003-deploy-routing-service  
**Date**: 2026-03-17

This feature is an infrastructure deployment — it introduces no new code-level entities, database tables, or application models. The "data model" below describes the Azure resources and their relationships.

## Azure Resource Topology

```
pacman-tracker-rg (Resource Group)
│
├── pacman-vnet (VNet: 10.0.0.0/16)
│   ├── aci-subnet (10.0.1.0/24) ─── delegated to Microsoft.ContainerInstance
│   │   └── pacman-osrm (ACI: 1 vCPU, 2 GB, private IP 10.0.1.x)
│   │       ├── image: osrm/osrm-backend:latest
│   │       ├── command: osrm-routed --algorithm mld /data/washington-latest.osrm
│   │       ├── port: 5000
│   │       ├── restart-policy: Always
│   │       └── volume mount: /data → osrm-data file share
│   │
│   └── app-subnet (10.0.2.0/24) ─── App Service VNet Integration
│       └── pacman-tracker-api (existing App Service, outbound via VNet)
│           └── OSRM_URL = http://<aci-private-ip>:5000
│
├── pacmantrackersa (Storage Account, Standard LRS)
│   └── osrm-data (File Share, ~10 GB quota)
│       ├── washington-latest.osm.pbf  (~800 MB, raw download)
│       ├── washington-latest.osrm     (extracted)
│       ├── washington-latest.osrm.*   (partition + customize output files)
│       └── (total ~2-4 GB prepared data)
│
├── pacman-alerts (Action Group → email notification)
│
└── osrm-crash-alert (Metric Alert on ACI RestartCount > 3 in 5 min)
```

## Resource Relationships

| Resource | Depends On | Relationship |
|----------|-----------|--------------|
| VNet | Resource Group | Contains both subnets |
| aci-subnet | VNet | Delegated to ACI; hosts OSRM container |
| app-subnet | VNet | Used by App Service VNet Integration |
| Storage Account | Resource Group | Hosts the file share |
| File Share | Storage Account | Mounted by both prep ACI and routing ACI |
| OSRM ACI (server) | aci-subnet, File Share | Reads prepared data, serves on :5000 |
| OSRM ACI (prep job) | aci-subnet, File Share | Writes prepared data, then exits |
| App Service VNet Integration | app-subnet | Allows backend to reach ACI private IP |
| Monitor Alert | ACI | Monitors restart count metric |

## Deployment Order

1. Storage Account + File Share (no dependencies)
2. VNet + subnets (no dependencies)
3. Data Prep ACI job (depends on 1 + 2)
4. Wait for prep to complete
5. Routing Server ACI (depends on 1 + 2 + prep complete)
6. App Service VNet Integration (depends on 2)
7. Update backend `OSRM_URL` to ACI private IP (depends on 5 + 6)
8. Monitor Alert (depends on 5)

## Configuration Values

| Setting | Value | Where |
|---------|-------|-------|
| `OSRM_URL` (production) | `http://<aci-private-ip>:5000` | Backend App Service app settings |
| `OSRM_URL` (local dev) | `http://localhost:5000` | backend/.env (unchanged) |
| ACI vCPU | 1 (can scale to 0.5 if cost exceeds budget) | ACI create command |
| ACI Memory | 2 GB | ACI create command |
| ACI Prep vCPU | 2 | Prep ACI create command |
| ACI Prep Memory | 4 GB | Prep ACI create command |
| File Share quota | 10 GB (2.8 GB used) | Storage share create command |
| VNet CIDR | 10.0.0.0/16 | VNet create command |
| ACI Subnet | 10.0.1.0/24 | Subnet create command |
| App Subnet | 10.0.2.0/24 | Subnet create command |
