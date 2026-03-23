# Research: Deploy Routing Service

**Feature**: 003-deploy-routing-service  
**Date**: 2026-03-17

## R1: Azure Container Instance with VNet Integration

**Unknown**: How to deploy an ACI into a VNet with a private IP so only the backend App Service can reach it.

**Decision**: Deploy the ACI into a delegated subnet within a new VNet. ACI supports VNet deployment via `az container create --vnet ... --subnet ...`. The ACI gets a private IP (e.g., `10.0.1.4`) instead of a public IP.

**Rationale**:
- ACI natively supports VNet deployment with the `--subnet` flag, which assigns a private IP from the subnet's CIDR range.
- A dedicated subnet must be delegated to `Microsoft.ContainerInstance/containerGroups` — no other resource types can live in that subnet.
- The ACI uses the standard OSRM image (`osrm/osrm-backend`) with no custom networking config needed inside the container.

**Alternatives considered**:
- Public IP with firewall rules: Simpler but rejected per clarification (VNet-integrated was chosen).
- Azure Kubernetes Service: Overkill for a single container; much higher cost and complexity.

**Key commands**:
```powershell
# Create VNet + subnets
az network vnet create --resource-group $rg --name pacman-vnet --address-prefix 10.0.0.0/16 --location $location
az network vnet subnet create --resource-group $rg --vnet-name pacman-vnet --name aci-subnet --address-prefix 10.0.1.0/24 --delegations Microsoft.ContainerInstance/containerGroups
az network vnet subnet create --resource-group $rg --vnet-name pacman-vnet --name app-subnet --address-prefix 10.0.2.0/24

# Deploy ACI into VNet
az container create --resource-group $rg --name pacman-osrm \
  --image osrm/osrm-backend:latest \
  --cpu 1 --memory 2 \
  --vnet pacman-vnet --subnet aci-subnet \
  --azure-file-volume-account-name $storageAccount \
  --azure-file-volume-account-key $storageKey \
  --azure-file-volume-share-name osrm-data \
  --azure-file-volume-mount-path /data \
  --command-line "osrm-routed --algorithm mld /data/washington-latest.osrm" \
  --ports 5000 \
  --restart-policy Always
```

## R2: App Service VNet Integration to Reach ACI

**Unknown**: How the backend App Service (B1 plan) connects to the ACI's private IP via VNet.

**Decision**: Use App Service Regional VNet Integration to connect the backend into the same VNet, allowing it to resolve the ACI's private IP. This requires at minimum a **Basic (B1)** tier, which already supports Regional VNet Integration.

**Rationale**:
- App Service Regional VNet Integration (not the legacy "gateway-required" kind) is available on B1 and higher tiers. The existing B1 plan is sufficient.
- The App Service is integrated into a separate subnet (`app-subnet`) in the same VNet, and can then reach the ACI's private IP on port 5000.
- The `OSRM_URL` env var on the backend changes from `http://localhost:5000` to `http://10.0.1.4:5000` (or use the ACI private IP).

**Alternatives considered**:
- DNS private zone for name resolution: Adds complexity; a static IP is sufficient for a single ACI.
- Service Connector: Not yet supported for ACI-to-App-Service scenarios.

**Key commands**:
```powershell
# Integrate App Service into VNet
az webapp vnet-integration add --resource-group $rg --name $apiAppName --vnet pacman-vnet --subnet app-subnet

# Set OSRM_URL to ACI private IP
$aciIp = az container show --resource-group $rg --name pacman-osrm --query "ipAddress.ip" -o tsv
az webapp config appsettings set --resource-group $rg --name $apiAppName --settings OSRM_URL="http://${aciIp}:5000"
```

**Important**: B1 tier does support Regional VNet Integration. No tier upgrade is needed.

## R3: Azure File Share for OSRM Data Persistence

**Unknown**: How to set up an Azure File Share and mount it into both the prep ACI job and the routing ACI.

**Decision**: Create an Azure Storage Account with a File Share named `osrm-data`. Both the data preparation ACI and the routing server ACI mount the same share at `/data`.

**Rationale**:
- Azure File Share is the only ACI-supported persistent volume type (aside from emptyDir and gitRepo which are ephemeral).
- SMB mount is transparent to OSRM — it reads/writes files at `/data` the same as with a Docker volume.
- Multiple ACI containers can mount the same share (not simultaneously for write safety, but prep runs once then exits before the server starts).
- Cost is ~$0.06/GB/month for Hot tier; ~2.5 GB data = ~$0.15/month.

**Alternatives considered**:
- Blob storage with BlobFuse: Not natively supported by ACI; requires custom image.
- Baking data into Docker image: Makes the image 2-4 GB larger; rejected.

**Key commands**:
```powershell
$storageAccountName = "pacmantrackersa"

# Create storage account
az storage account create --resource-group $rg --name $storageAccountName --location $location --sku Standard_LRS

# Create file share
az storage share create --account-name $storageAccountName --name osrm-data --quota 10

# Get storage key for ACI volume mount
$storageKey = az storage account keys list --resource-group $rg --account-name $storageAccountName --query "[0].value" -o tsv
```

**Note**: The storage account needs to be accessible from the VNet. Since both ACIs and the storage account are in the same resource group/region, the default networking (allow all Azure services) works. For stricter security, a service endpoint for `Microsoft.Storage` can be added to the ACI subnet.

## R4: Data Preparation as a One-Time ACI Job

**Unknown**: How to run the OSRM data preparation pipeline as a one-time ACI job.

**Decision**: Deploy a temporary ACI container group with `--restart-policy Never` that runs the download + extract + partition + customize pipeline. It mounts the same Azure File Share and writes output there. The container exits when done and can be deleted afterward.

**Rationale**:
- ACI with `--restart-policy Never` is effectively a one-shot job — it runs, completes, and is billed only for the seconds it was active.
- The pipeline mirrors the existing Docker Compose `prepare` profile exactly: download PBF, `osrm-extract -p /opt/foot.lua`, `osrm-partition`, `osrm-customize`.
- The prep container needs more RAM than the routing server (extraction is memory-intensive) — use 2 vCPU / 4 GB RAM for the prep job.
- Total cost for a single prep run (estimating ~30-45 min): ~$0.05-0.10.

**Alternatives considered**:
- Running prep locally and uploading: Works but couples the deployment to a developer's machine.
- Running prep on first boot of routing ACI: Delays startup by 30+ minutes; bad UX if the server restarts.

**Pipeline script** (entrypoint for prep ACI):
```sh
#!/bin/sh
set -e

# Step 1: Download
if [ ! -f /data/washington-latest.osm.pbf ]; then
  echo 'Downloading Washington state OSM data...'
  apk add --no-cache wget
  wget -O /data/washington-latest.osm.pbf https://download.geofabrik.de/north-america/us/washington-latest.osm.pbf
fi

# Step 2: Extract + Partition + Customize
if [ ! -f /data/washington-latest.osrm ]; then
  echo 'Extracting with foot profile...'
  osrm-extract -p /opt/foot.lua /data/washington-latest.osm.pbf
  osrm-partition /data/washington-latest.osrm
  osrm-customize /data/washington-latest.osrm
fi

echo 'OSRM data preparation complete.'
```

**Note**: The prep ACI uses the same `osrm/osrm-backend:latest` image as the server, but with a custom command that includes the download step (the OSRM image is based on Debian, so `wget` or `curl` is available or can be installed). Alternatively, a two-step approach can be used: first an Alpine container for download, then the OSRM container for extract/partition/customize — but a single container is simpler for ACI.

Actually, the OSRM image is based on Debian and has `curl` available. The download step can use `curl` instead of `wget` to avoid needing Alpine + apk. Or we use two separate ACI containers run sequentially. Simplest approach: single OSRM-based container that does both download and prep.

## R5: Azure Monitor Alert for ACI Restart Count

**Unknown**: How to set up a basic alert on ACI restart count to detect crash loops.

**Decision**: Create an Azure Monitor metric alert on the ACI container group's `RestartCount` metric. Alert fires when restart count exceeds a threshold (e.g., 3 restarts in 5 minutes).

**Rationale**:
- ACI exposes `RestartCount` as a platform metric in Azure Monitor — no custom instrumentation needed.
- An action group can send email notifications when the alert fires.
- This is the simplest observability addition and catches the main failure mode (OSRM crashing on startup due to corrupted data or OOM).

**Key commands**:
```powershell
# Create action group for email notification
az monitor action-group create --resource-group $rg --name pacman-alerts --short-name pacman --action email admin your-email@example.com

# Create metric alert on restart count
$aciResourceId = az container show --resource-group $rg --name pacman-osrm --query id -o tsv

az monitor metrics alert create --resource-group $rg --name osrm-crash-alert \
  --scopes $aciResourceId \
  --condition "avg RestartCount > 3" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action pacman-alerts \
  --description "OSRM routing container is crash-looping"
```

## R6: Cost Estimate for Routing Service Deployment

**Unknown**: Total monthly cost for the routing service infrastructure.

**Decision**: The total additional monthly cost fits within the $45/month budget from SC-005.

| Resource | SKU / Config | ~Monthly Cost |
|----------|-------------|---------------|
| ACI (routing server) | 1 vCPU, 2 GB RAM, always-on | ~$40 |
| Storage Account + File Share | Standard LRS, ~2.8 GB used | ~$0.18 |
| VNet | Free | $0 |
| Azure Monitor alert | Free tier (first 10 alerts) | $0 |
| ACI (data prep job) | 2 vCPU, 4 GB RAM, ~45 min one-time | ~$0.10 one-time |
| **Total recurring** | | **~$40/month** |

**Rationale**: ACI pricing is ~$0.0000125/second per vCPU + ~$0.0000014/second per GB RAM. For 1 vCPU + 2 GB RAM running 24/7:
- vCPU: 1 × 0.0000125 × 2,592,000 = $32.40
- Memory: 2 × 0.0000014 × 2,592,000 = $7.26
- Total: ~$39.66/month

Verified post-deployment: actual resource configuration matches this calculation.

## R7: VNet Subnet Planning

**Unknown**: What CIDR ranges to use and how many subnets are needed.

**Decision**: Create a single VNet with two subnets:
- `aci-subnet` (10.0.1.0/24) — delegated to `Microsoft.ContainerInstance/containerGroups` — hosts the OSRM ACI.
- `app-subnet` (10.0.2.0/24) — used by App Service VNet Integration — hosts the backend's outbound traffic.

**Rationale**:
- ACI requires a dedicated, delegated subnet. App Service VNet Integration also requires its own subnet (cannot share with ACI's delegated subnet).
- /24 gives 251 usable IPs per subnet, far more than needed but standard practice for simplicity.
- VNet address space 10.0.0.0/16 leaves plenty of room for future subnets if needed.
