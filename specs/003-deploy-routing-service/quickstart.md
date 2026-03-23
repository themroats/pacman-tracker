# Quickstart: Deploy OSRM Routing Service

**Feature**: 003-deploy-routing-service  
**Prerequisite**: Backend and frontend already deployed per AZURE_DEPLOY.md

## Prerequisites

- Azure CLI (`az`) installed and logged in
- Existing resource group (`pacman-tracker-rg`) with backend App Service deployed
- Docker is NOT needed — everything runs as Azure Container Instances

## Variables

```powershell
$resourceGroup = "pacman-tracker-rg"
$location = "eastus"
$storageAccountName = "pacmantrackersa"
$vnetName = "pacman-vnet"
$aciSubnet = "aci-subnet"
$appSubnet = "app-subnet"
$osrmAciName = "pacman-osrm"
$osrmFileShare = "osrm-data"
$apiAppName = "pacman-tracker-api"
```

## Step 1: Create Storage + File Share

```powershell
az storage account create --resource-group $resourceGroup --name $storageAccountName --location $location --sku Standard_LRS
az storage share create --account-name $storageAccountName --name $osrmFileShare --quota 10
$storageKey = az storage account keys list --resource-group $resourceGroup --account-name $storageAccountName --query "[0].value" -o tsv
```

## Step 2: Create VNet + Subnets

```powershell
az network vnet create --resource-group $resourceGroup --name $vnetName --address-prefix 10.0.0.0/16 --location $location
az network vnet subnet create --resource-group $resourceGroup --vnet-name $vnetName --name $aciSubnet --address-prefix 10.0.1.0/24 --delegations Microsoft.ContainerInstance/containerGroups
az network vnet subnet create --resource-group $resourceGroup --vnet-name $vnetName --name $appSubnet --address-prefix 10.0.2.0/24
```

## Step 3: Run Data Preparation (one-time, ~30-45 min)

```powershell
az container create --resource-group $resourceGroup --name pacman-osrm-prep `
  --image osrm/osrm-backend:latest `
  --cpu 2 --memory 4 `
  --vnet $vnetName --subnet $aciSubnet `
  --azure-file-volume-account-name $storageAccountName `
  --azure-file-volume-account-key $storageKey `
  --azure-file-volume-share-name $osrmFileShare `
  --azure-file-volume-mount-path /data `
  --restart-policy Never `
  --command-line "/bin/sh -c 'apt-get update && apt-get install -y wget && wget -O /data/washington-latest.osm.pbf https://download.geofabrik.de/north-america/us/washington-latest.osm.pbf && osrm-extract -p /opt/foot.lua /data/washington-latest.osm.pbf && osrm-partition /data/washington-latest.osrm && osrm-customize /data/washington-latest.osrm && echo Done'"

# Monitor progress
az container logs --resource-group $resourceGroup --name pacman-osrm-prep --follow

# Wait for completion (state = "Terminated", exit code 0)
az container show --resource-group $resourceGroup --name pacman-osrm-prep --query "instanceView.state" -o tsv
```

## Step 4: Deploy Routing Server

```powershell
az container create --resource-group $resourceGroup --name $osrmAciName `
  --image osrm/osrm-backend:latest `
  --cpu 1 --memory 2 `
  --vnet $vnetName --subnet $aciSubnet `
  --azure-file-volume-account-name $storageAccountName `
  --azure-file-volume-account-key $storageKey `
  --azure-file-volume-share-name $osrmFileShare `
  --azure-file-volume-mount-path /data `
  --restart-policy Always `
  --command-line "osrm-routed --algorithm mld /data/washington-latest.osrm" `
  --ports 5000
```

## Step 5: Connect Backend to Routing Service

```powershell
# Add VNet Integration to App Service
az webapp vnet-integration add --resource-group $resourceGroup --name $apiAppName --vnet $vnetName --subnet $appSubnet

# Get ACI private IP
$aciIp = az container show --resource-group $resourceGroup --name $osrmAciName --query "ipAddress.ip" -o tsv

# Update backend OSRM_URL
az webapp config appsettings set --resource-group $resourceGroup --name $apiAppName --settings OSRM_URL="http://${aciIp}:5000"

# Restart backend to pick up new settings
az webapp restart --resource-group $resourceGroup --name $apiAppName
```

## Step 6: Set Up Monitoring

```powershell
az monitor action-group create --resource-group $resourceGroup --name pacman-alerts --short-name pacman --action email admin your-email@example.com

$aciResourceId = az container show --resource-group $resourceGroup --name $osrmAciName --query id -o tsv

az monitor metrics alert create --resource-group $resourceGroup --name osrm-crash-alert `
  --scopes $aciResourceId `
  --condition "avg RestartCount > 3" `
  --window-size 5m `
  --evaluation-frequency 1m `
  --action pacman-alerts `
  --description "OSRM routing container is crash-looping"
```

## Step 7: Verify

```powershell
# Check backend health
$backendHost = az webapp show --resource-group $resourceGroup --name $apiAppName --query "defaultHostName" -o tsv
Invoke-RestMethod "https://$backendHost/health"
# Expected: { "status": "ok", "osrm_available": true }
```

## Cleanup (if needed)

```powershell
# Remove just the routing service (keeps backend + frontend)
az container delete --resource-group $resourceGroup --name $osrmAciName --yes
az container delete --resource-group $resourceGroup --name pacman-osrm-prep --yes
az storage share delete --account-name $storageAccountName --name $osrmFileShare
az webapp vnet-integration remove --resource-group $resourceGroup --name $apiAppName
az network vnet delete --resource-group $resourceGroup --name $vnetName
```
