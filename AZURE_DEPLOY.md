# Azure Deployment Guide (PoC)

Two services:
- **Backend** → Azure App Service (Linux container) — handles API + SpatiaLite
- **Frontend** → Azure Static Web Apps — serves the Vite SPA
- **Routing** → Azure Container Instance — OSRM walking route engine (private VNet)

> All commands below use **PowerShell** syntax (backtick `` ` `` for line continuation).

## Set Variables

Choose a single region and start with the plain names you want:

```powershell
$location = "eastus"
$staticWebAppLocation = "eastus2"
$resourceGroup = "pacman-tracker-rg"
$acrName = "pacmantrackercr"
$planName = "pacman-plan"
$apiAppName = "pacman-tracker-api"
$webAppName = "pacman-tracker-web"

# Routing service (Section 6)
$storageAccountName = "pacmantrackersa"
$vnetName = "pacman-vnet"
$osrmAciName = "pacman-osrm"
$osrmFileShare = "osrm-data"
```

If Azure says one of those names is already taken, change only that value and rerun.
The suffix is not required unless Azure rejects the hostname.

Static Web Apps does not support every Azure region. It is fine for `$staticWebAppLocation`
to differ from `$location`.

## Prerequisites

```powershell
# Install Azure CLI
winget install Microsoft.AzureCLI
# Then restart your terminal so 'az' is on PATH

az login
```

Add your Azure subscription id to `backend/.env` so the deployment script can pick it up automatically:

```text
AZURE_SUBSCRIPTION_ID=your-subscription-guid
```

## 1. Create Resource Group

```powershell
az group create --name $resourceGroup --location $location
```

## 2. Deploy Backend (App Service + Container)

### Build & push to Azure Container Registry

```powershell
# Create container registry
az acr create --resource-group $resourceGroup --name $acrName --sku Basic

# App Service pull from ACR is simplest when the admin user is enabled
az acr update --name $acrName --admin-enabled true

# Log in to registry
az acr login --name $acrName

# Fetch registry credentials once and reuse them below
$acrUser = az acr credential show --name $acrName --query username -o tsv
$acrPass = az acr credential show --name $acrName --query "passwords[0].value" -o tsv

# Build and push from the backend directory
cd backend
docker build -t "${acrName}.azurecr.io/pacman-backend:latest" .
docker push "${acrName}.azurecr.io/pacman-backend:latest"
```

### Create App Service

```powershell
# Create App Service plan (B1 = cheapest non-free tier with containers)
az appservice plan create `
  --resource-group $resourceGroup `
  --name $planName `
  --is-linux `
  --sku B1

# Create the Linux web app and point it directly at the ACR image
az webapp create `
  --resource-group $resourceGroup `
  --plan $planName `
  --name $apiAppName `
  --container-image-name "${acrName}.azurecr.io/pacman-backend:latest" `
  --container-registry-url "https://${acrName}.azurecr.io" `
  --container-registry-user $acrUser `
  --container-registry-password $acrPass

# If create succeeds but the image is wrong, force the Linux container image explicitly.
# PowerShell 5.1 can mis-handle the | character, so pass linuxFxVersion via JSON.
$siteConfig = @{ linuxFxVersion = "DOCKER|${acrName}.azurecr.io/pacman-backend:latest" } | ConvertTo-Json -Compress
$siteConfig | Set-Content -Path appservice-siteconfig.json

az webapp config set `
  --resource-group $resourceGroup `
  --name $apiAppName `
  --generic-configurations "@appservice-siteconfig.json"
```

### Configure environment variables

```powershell
# Generate a secret key
$secretKey = python -c "import secrets; print(secrets.token_urlsafe(32))"

az webapp config appsettings set `
  --resource-group $resourceGroup `
  --name $apiAppName `
  --settings `
    DOCKER_REGISTRY_SERVER_URL="https://${acrName}.azurecr.io" `
    DOCKER_REGISTRY_SERVER_USERNAME="$acrUser" `
    DOCKER_REGISTRY_SERVER_PASSWORD="$acrPass" `
    STRAVA_CLIENT_ID="your-client-id" `
    STRAVA_CLIENT_SECRET="your-client-secret" `
    STRAVA_REDIRECT_URI="https://your-static-web-app.azurestaticapps.net/auth/callback" `
    SECRET_KEY="$secretKey" `
    DATABASE_URL="sqlite:////home/data/pacman.db" `
    CORS_ORIGINS="https://your-static-web-app.azurestaticapps.net" `
    WEBSITES_ENABLE_APP_SERVICE_STORAGE=true `
    WEBSITES_PORT=8000
```

### Verify container settings

```powershell
az webapp show `
  --resource-group $resourceGroup `
  --name $apiAppName `
  --query "siteConfig.linuxFxVersion" `
  -o tsv
```

Expected output:

```text
DOCKER|pacmantrackercr.azurecr.io/pacman-backend:latest
```

If that value is empty or does not start with `DOCKER|`, rerun the `az webapp create`
step or the `az webapp config set --generic-configurations ...` command.

If you see `DOCKER|/pacman-backend:latest`, `$acrName` was empty when the web app was
configured. Set `$acrName`, `$acrUser`, and `$acrPass` again, then rerun the
`az webapp config set --generic-configurations ...` and `az webapp config appsettings set` commands.

Backend will be live at: `https://${apiAppName}.azurewebsites.net`

## 3. Deploy Frontend (Static Web Apps)

### Build the frontend with the deployed API URL

The frontend already reads `VITE_API_URL` from Vite. Because Vite bakes env vars into
the build output, set the API URL before you run `npm run build`.

```powershell
cd frontend
$env:VITE_API_URL = "https://${apiAppName}.azurewebsites.net/api/v1"
npm install
npm run build
```

### Create the Static Web App resource

```powershell
az staticwebapp create `
  --resource-group $resourceGroup `
  --name $webAppName `
  --location $staticWebAppLocation `
  --sku Free
```

`az staticwebapp create` creates the Azure resource. It does not upload a local Vite
folder.

### Deploy the built files

Use the Static Web Apps CLI with the deployment token from Azure.

```powershell
cd frontend

# Get a deployment token for the existing Static Web App resource
$deploymentToken = az staticwebapp secrets list `
  --resource-group $resourceGroup `
  --name $webAppName `
  --query "properties.apiKey" `
  -o tsv

# Deploy the already-built dist folder
npx @azure/static-web-apps-cli deploy ./dist `
  --deployment-token $deploymentToken `
  --env production `
  --swa-config-location .
```

Notes:
- `--swa-config-location .` makes the deploy pick up `frontend/staticwebapp.config.json`.
- The deployment token is a secret. Do not commit it or paste it into source files.
- The first `npx` run may take a minute because it downloads the CLI package.

If you prefer GitHub-based deployment later, reconnect the Static Web App to a repo
with `az staticwebapp reconnect`, then move the `VITE_API_URL` value into the GitHub
Actions workflow env section.

### Configure SPA routing

Create a static web app config so all routes fall through to `index.html`:

This is already handled by the `staticwebapp.config.json` created below.

You can get the frontend hostname with:

```powershell
az staticwebapp show `
  --resource-group $resourceGroup `
  --name $webAppName `
  --query "defaultHostname" `
  -o tsv
```

## 4. Update CORS

After deploying the frontend, update the backend's CORS setting:

```powershell
$frontendHost = az staticwebapp show `
  --resource-group $resourceGroup `
  --name $webAppName `
  --query "defaultHostname" `
  -o tsv

az webapp config appsettings set `
  --resource-group $resourceGroup `
  --name $apiAppName `
  --settings CORS_ORIGINS="https://${frontendHost}"
```

## 5. Update Strava OAuth Callback

After the Static Web App is deployed, get its real hostname:

```powershell
$frontendHost = az staticwebapp show `
  --resource-group $resourceGroup `
  --name $webAppName `
  --query "defaultHostname" `
  -o tsv
```

Update the backend app setting to use that exact hostname:

```powershell
az webapp config appsettings set `
  --resource-group $resourceGroup `
  --name $apiAppName `
  --settings STRAVA_REDIRECT_URI="https://${frontendHost}/auth/callback"
```

In your Strava API app settings, update the callback URL to:
`https://${frontendHost}/auth/callback`

Why this matters:
- The backend starts the OAuth flow at `${VITE_API_URL}/auth/strava`.
- Strava must redirect back to the frontend route `/auth/callback`.
- The frontend callback page then calls the backend API `/auth/strava/callback` to finish login and store the session in the browser.

## 6. Deploy Routing Service (OSRM)

The routing service runs OSRM (Open Source Routing Machine) with a foot/walking profile
for route suggestions. It is deployed as an Azure Container Instance in a private VNet,
accessible only to the backend.

### Prerequisites

- Sections 1-2 complete (resource group + backend App Service exist)
- Azure CLI logged in

### Automated deployment

The simplest approach — a single script handles everything:

```powershell
# 1. Prepare map data (one-time, ~30-60 min)
.\infra\prep-osrm-data.ps1

# 2. Deploy routing server + connect backend
.\infra\deploy-osrm.ps1

# With crash-loop email alerts:
.\infra\deploy-osrm.ps1 -AlertEmail "your-email@example.com"
```

### Manual step-by-step

If you prefer to run each step individually:

#### 6a. Create Storage Account + File Share

```powershell
az storage account create --resource-group $resourceGroup --name $storageAccountName --location $location --sku Standard_LRS
az storage share create --account-name $storageAccountName --name $osrmFileShare --quota 10
$storageKey = az storage account keys list --resource-group $resourceGroup --account-name $storageAccountName --query "[0].value" -o tsv
```

#### 6b. Create VNet + Subnets

```powershell
az network vnet create --resource-group $resourceGroup --name $vnetName --address-prefix 10.0.0.0/16 --location $location
az network vnet subnet create --resource-group $resourceGroup --vnet-name $vnetName --name aci-subnet --address-prefix 10.0.1.0/24 --delegations Microsoft.ContainerInstance/containerGroups
az network vnet subnet create --resource-group $resourceGroup --vnet-name $vnetName --name app-subnet --address-prefix 10.0.2.0/24
```

#### 6c. Prepare map data (one-time)

```powershell
.\infra\prep-osrm-data.ps1
```

This creates a temporary ACI that downloads Washington state OSM data (~800 MB),
runs `osrm-extract`, `osrm-partition`, and `osrm-customize`, writes ~2-4 GB of
prepared data to the file share, then exits. Takes 30-60 minutes.

#### 6d. Deploy OSRM routing server

```powershell
az container create --resource-group $resourceGroup --name $osrmAciName `
  --image osrm/osrm-backend:latest `
  --cpu 1 --memory 2 `
  --vnet $vnetName --subnet aci-subnet `
  --azure-file-volume-account-name $storageAccountName `
  --azure-file-volume-account-key $storageKey `
  --azure-file-volume-share-name $osrmFileShare `
  --azure-file-volume-mount-path /data `
  --restart-policy Always `
  --command-line "osrm-routed --algorithm mld /data/washington-latest.osrm" `
  --ports 5000
```

#### 6e. Connect backend to routing service

```powershell
# Add VNet integration
az webapp vnet-integration add --resource-group $resourceGroup --name $apiAppName --vnet $vnetName --subnet app-subnet

# Get ACI private IP and configure backend
$aciIp = az container show --resource-group $resourceGroup --name $osrmAciName --query "ipAddress.ip" -o tsv
az webapp config appsettings set --resource-group $resourceGroup --name $apiAppName --settings OSRM_URL="http://${aciIp}:5000"
az webapp restart --resource-group $resourceGroup --name $apiAppName
```

#### 6f. Verify

```powershell
$backendHost = az webapp show --resource-group $resourceGroup --name $apiAppName --query "defaultHostName" -o tsv
Invoke-RestMethod "https://$backendHost/health"
# Expected: { "status": "ok", "osrm_available": true }
```

## Cost Estimate (PoC)

| Service               | SKU           | ~Monthly Cost |
|----------------------|---------------|---------------|
| App Service Plan     | B1 (Linux)    | ~$13          |
| Container Registry   | Basic         | ~$5           |
| Static Web Apps      | Free tier     | $0            |
| ACI (OSRM routing)   | 1 vCPU, 2 GB  | ~$40          |
| Storage Account      | Standard LRS  | ~$0.20        |
| VNet                 | Free          | $0            |
| **Total**            |               | **~$58/month**|

> The ACI cost can be reduced to ~$22/month by using 0.5 vCPU / 1.5 GB RAM if
> OSRM performance is acceptable for a single-user PoC.

## Redeploying

After code changes:

```powershell
# Backend
cd backend
docker build -t "${acrName}.azurecr.io/pacman-backend:latest" .
docker push "${acrName}.azurecr.io/pacman-backend:latest"
az webapp restart --resource-group $resourceGroup --name $apiAppName

# Frontend
cd frontend
npm run build
# re-deploy to Static Web Apps
$deploymentToken = az staticwebapp secrets list --resource-group $resourceGroup --name $webAppName --query "properties.apiKey" -o tsv
npx @azure/static-web-apps-cli deploy ./dist --deployment-token $deploymentToken --env production --swa-config-location .
```

### Redeploying the Routing Service

To restart OSRM (e.g., after it crashes or to pick up new data):

```powershell
az container restart --resource-group $resourceGroup --name $osrmAciName
```

To refresh OSM data (e.g., when map data is updated):

```powershell
# 1. Re-run data preparation (downloads fresh data, re-processes)
.\infra\prep-osrm-data.ps1 -Force

# 2. Restart the routing server to load new data
az container restart --resource-group $resourceGroup --name $osrmAciName

# 3. Verify
$backendHost = az webapp show --resource-group $resourceGroup --name $apiAppName --query "defaultHostName" -o tsv
Invoke-RestMethod "https://$backendHost/health"
# Expected: osrm_available = true
```

## Scripted deployment

`infra/deploy-prod.ps1` reads `AZURE_SUBSCRIPTION_ID` from `backend/.env` by default. You can still override it explicitly:

```powershell
.\infra\deploy-prod.ps1

# or
.\infra\deploy-prod.ps1 -SubscriptionId "your-subscription-guid"
```

## Teardown

```powershell
az group delete --name $resourceGroup --yes
```
