<#
.SYNOPSIS
    Deploys the OSRM routing service to Azure as a Container Instance in a VNet.

.DESCRIPTION
    Creates the Azure infrastructure for the OSRM routing service:
    - Storage Account + File Share for OSRM data persistence
    - VNet with subnets for ACI and App Service integration
    - OSRM routing server ACI (always-on, private IP)
    - App Service VNet integration + OSRM_URL configuration
    - Azure Monitor alert for crash-loop detection

    Prereqs: Azure CLI logged in, resource group and backend App Service exist.
    Run infra/prep-osrm-data.ps1 first to prepare map data on the file share.

.PARAMETER ResourceGroup
    Azure resource group (must already exist). Default: pacman-tracker-rg

.PARAMETER Location
    Azure region. Default: eastus

.PARAMETER StorageAccountName
    Storage account for the OSRM file share. Default: pacmantrackersa

.PARAMETER VNetName
    Virtual network name. Default: pacman-vnet

.PARAMETER AciSubnet
    Subnet for ACI containers, delegated to Microsoft.ContainerInstance. Default: aci-subnet

.PARAMETER AppSubnet
    Subnet for App Service VNet integration. Default: app-subnet

.PARAMETER OsrmAciName
    Container group name for the OSRM routing server. Default: pacman-osrm

.PARAMETER OsrmFileShare
    Azure File Share name for OSRM data. Default: osrm-data

.PARAMETER BackendAppName
    Existing App Service name for the backend API. Default: pacman-tracker-api

.PARAMETER AlertEmail
    Email address for crash-loop alert notifications. Default: empty (skips alert creation)

.PARAMETER SkipMonitoring
    Skip Azure Monitor alert creation.

.PARAMETER Help
    Show this help message.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ResourceGroup = "pacman-tracker-rg",
    [string]$Location = "eastus",
    [string]$StorageAccountName = "pacmantrackersa",
    [string]$VNetName = "pacman-vnet",
    [string]$AciSubnet = "aci-subnet",
    [string]$AppSubnet = "app-subnet",
    [string]$OsrmAciName = "pacman-osrm",
    [string]$AcrName = "pacmantrackercr",
    [string]$OsrmFileShare = "osrm-data",
    [string]$BackendAppName = "pacman-tracker-api",
    [string]$AlertEmail = "",
    [switch]$SkipMonitoring,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Detailed
    exit 0
}

# ---------------------------------------------------------------------------
# Helper functions (match deploy-prod.ps1 patterns)
# ---------------------------------------------------------------------------

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH."
    }
}

function Invoke-AzJson {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $output = az @Arguments --output json 2>$null
    if ($LASTEXITCODE -ne 0) {
        $errOutput = az @Arguments --output json 2>&1
        throw "Azure CLI command failed: az $($Arguments -join ' ')`n$errOutput"
    }
    return $output | ConvertFrom-Json
}

function Invoke-AzText {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $output = az @Arguments --output tsv 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments -join ' ')`n$output"
    }
    return ($output | Out-String).Trim()
}

function Test-AzResourceExists {
    param([string[]]$Arguments)
    az @Arguments --output json 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function Wait-ForHttpOk {
    param(
        [string]$Url,
        [int]$MaxAttempts = 30,
        [int]$DelaySeconds = 10
    )
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            $response = Invoke-RestMethod -Uri $Url -TimeoutSec 30
            return $response
        } catch {
            if ($attempt -eq $MaxAttempts) {
                throw "Timed out waiting for $Url after $MaxAttempts attempts."
            }
            Write-Host "  Attempt $attempt/$MaxAttempts — waiting ${DelaySeconds}s..." -ForegroundColor Yellow
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

# ---------------------------------------------------------------------------
# Validate prerequisites
# ---------------------------------------------------------------------------

Write-Step "Validating prerequisites"
Assert-Command az

# Verify resource group exists
$null = Invoke-AzJson group show --name $ResourceGroup

# Verify backend App Service exists
$null = Invoke-AzJson webapp show --resource-group $ResourceGroup --name $BackendAppName

Write-Host "  Resource group '$ResourceGroup' and backend '$BackendAppName' exist." -ForegroundColor Green

# Get ACR credentials for ACI image pulls
$acrUser = Invoke-AzText acr credential show --name $AcrName --query username
$acrPass = Invoke-AzText acr credential show --name $AcrName --query "passwords[0].value"
Write-Host "  ACR '$AcrName' credentials retrieved." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Phase 2: Storage Account + File Share
# ---------------------------------------------------------------------------

Write-Step "Creating Storage Account and File Share"

if (Test-AzResourceExists storage account show --resource-group $ResourceGroup --name $StorageAccountName) {
    Write-Host "  Storage account '$StorageAccountName' already exists, skipping creation." -ForegroundColor Yellow
} else {
    if ($PSCmdlet.ShouldProcess($StorageAccountName, "Create storage account")) {
        Invoke-AzJson storage account create `
            --resource-group $ResourceGroup `
            --name $StorageAccountName `
            --location $Location `
            --sku Standard_LRS | Out-Null
        Write-Host "  Created storage account '$StorageAccountName'." -ForegroundColor Green
    }
}

# Create file share (idempotent — create-if-not-exists is default behavior)
$storageKey = Invoke-AzText storage account keys list `
    --resource-group $ResourceGroup `
    --account-name $StorageAccountName `
    --query "[0].value"

if ($PSCmdlet.ShouldProcess($OsrmFileShare, "Create file share")) {
    az storage share create `
        --account-name $StorageAccountName `
        --account-key $storageKey `
        --name $OsrmFileShare `
        --quota 10 `
        --output none 2>$null
    Write-Host "  File share '$OsrmFileShare' ready." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Phase 2: VNet + Subnets
# ---------------------------------------------------------------------------

Write-Step "Creating VNet and subnets"

if (Test-AzResourceExists network vnet show --resource-group $ResourceGroup --name $VNetName) {
    Write-Host "  VNet '$VNetName' already exists, skipping creation." -ForegroundColor Yellow
} else {
    if ($PSCmdlet.ShouldProcess($VNetName, "Create VNet")) {
        Invoke-AzJson network vnet create `
            --resource-group $ResourceGroup `
            --name $VNetName `
            --address-prefix "10.0.0.0/16" `
            --location $Location | Out-Null
        Write-Host "  Created VNet '$VNetName'." -ForegroundColor Green
    }
}

# ACI subnet (delegated to Microsoft.ContainerInstance)
if (Test-AzResourceExists network vnet subnet show --resource-group $ResourceGroup --vnet-name $VNetName --name $AciSubnet) {
    Write-Host "  Subnet '$AciSubnet' already exists, skipping creation." -ForegroundColor Yellow
} else {
    if ($PSCmdlet.ShouldProcess($AciSubnet, "Create ACI subnet")) {
        Invoke-AzJson network vnet subnet create `
            --resource-group $ResourceGroup `
            --vnet-name $VNetName `
            --name $AciSubnet `
            --address-prefix "10.0.1.0/24" `
            --delegations "Microsoft.ContainerInstance/containerGroups" | Out-Null
        Write-Host "  Created subnet '$AciSubnet' (delegated to ACI)." -ForegroundColor Green
    }
}

# App Service subnet
if (Test-AzResourceExists network vnet subnet show --resource-group $ResourceGroup --vnet-name $VNetName --name $AppSubnet) {
    Write-Host "  Subnet '$AppSubnet' already exists, skipping creation." -ForegroundColor Yellow
} else {
    if ($PSCmdlet.ShouldProcess($AppSubnet, "Create App Service subnet")) {
        Invoke-AzJson network vnet subnet create `
            --resource-group $ResourceGroup `
            --vnet-name $VNetName `
            --name $AppSubnet `
            --address-prefix "10.0.2.0/24" `
            --delegations "Microsoft.Web/serverFarms" | Out-Null
        Write-Host "  Created subnet '$AppSubnet'." -ForegroundColor Green
    }
}

# ---------------------------------------------------------------------------
# Phase 4: Deploy OSRM Routing Server ACI
# ---------------------------------------------------------------------------

Write-Step "Deploying OSRM routing server ACI"

# Pre-flight: check that prepared data exists on the file share
$fileList = az storage file list `
    --account-name $StorageAccountName `
    --account-key $storageKey `
    --share-name $OsrmFileShare `
    --query "[?name=='washington-latest.osrm'].{name:name, size:properties.contentLength}" `
    --output json 2>$null | ConvertFrom-Json

if (-not $fileList -or $fileList.Count -eq 0) {
    throw @"
OSRM prepared data not found on file share '$OsrmFileShare'.
Run 'infra/prep-osrm-data.ps1' first to download and prepare the map data.
"@
}

Write-Host "  Pre-flight OK: washington-latest.osrm found on file share." -ForegroundColor Green

if (Test-AzResourceExists container show --resource-group $ResourceGroup --name $OsrmAciName) {
    Write-Host "  ACI '$OsrmAciName' already exists, skipping creation." -ForegroundColor Yellow
} else {
    if ($PSCmdlet.ShouldProcess($OsrmAciName, "Create OSRM routing server ACI")) {
        Invoke-AzJson container create `
            --resource-group $ResourceGroup `
            --name $OsrmAciName `
            --image "${AcrName}.azurecr.io/osrm-backend:latest" `
            --os-type Linux `
            --registry-login-server "${AcrName}.azurecr.io" `
            --registry-username $acrUser `
            --registry-password $acrPass `
            --cpu 1 --memory 2 `
            --vnet $VNetName `
            --subnet $AciSubnet `
            --azure-file-volume-account-name $StorageAccountName `
            --azure-file-volume-account-key $storageKey `
            --azure-file-volume-share-name $OsrmFileShare `
            --azure-file-volume-mount-path "/data" `
            --restart-policy Always `
            --command-line "osrm-routed --algorithm mld /data/washington-latest.osrm" `
            --ports 5000 | Out-Null
        Write-Host "  Created ACI '$OsrmAciName'." -ForegroundColor Green
    }
}

# Wait for Running state and retrieve private IP
Write-Step "Waiting for OSRM ACI to start"
for ($i = 1; $i -le 30; $i++) {
    $state = Invoke-AzText container show `
        --resource-group $ResourceGroup `
        --name $OsrmAciName `
        --query "instanceView.state"
    if ($state -eq "Running") { break }
    Write-Host "  State: $state — waiting 10s ($i/30)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
}

if ($state -ne "Running") {
    throw "OSRM ACI did not reach Running state. Current state: $state. Check logs with: az container logs --resource-group $ResourceGroup --name $OsrmAciName"
}

$aciIp = Invoke-AzText container show `
    --resource-group $ResourceGroup `
    --name $OsrmAciName `
    --query "ipAddress.ip"

Write-Host "  OSRM ACI running at private IP: $aciIp" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Phase 4: App Service VNet Integration + OSRM_URL
# ---------------------------------------------------------------------------

Write-Step "Connecting backend to OSRM via VNet integration"

# Check if VNet integration already exists
$existingVnet = az webapp vnet-integration list `
    --resource-group $ResourceGroup `
    --name $BackendAppName `
    --output json 2>$null | ConvertFrom-Json

if ($existingVnet -and $existingVnet.Count -gt 0) {
    Write-Host "  Backend already has VNet integration, skipping." -ForegroundColor Yellow
} else {
    if ($PSCmdlet.ShouldProcess($BackendAppName, "Add VNet integration")) {
        az webapp vnet-integration add `
            --resource-group $ResourceGroup `
            --name $BackendAppName `
            --vnet $VNetName `
            --subnet $AppSubnet `
            --output none
        Write-Host "  Added VNet integration to '$BackendAppName'." -ForegroundColor Green
    }
}

# Update OSRM_URL to point at the ACI private IP
$osrmUrl = "http://${aciIp}:5000"
if ($PSCmdlet.ShouldProcess($BackendAppName, "Set OSRM_URL=$osrmUrl")) {
    az webapp config appsettings set `
        --resource-group $ResourceGroup `
        --name $BackendAppName `
        --settings OSRM_URL="$osrmUrl" `
        --output none
    Write-Host "  Set OSRM_URL=$osrmUrl on backend." -ForegroundColor Green

    az webapp restart --resource-group $ResourceGroup --name $BackendAppName --output none
    Write-Host "  Restarted backend to apply new settings." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Phase 4: Health check verification
# ---------------------------------------------------------------------------

Write-Step "Verifying OSRM connectivity via backend health check"

$backendHost = Invoke-AzText webapp show `
    --resource-group $ResourceGroup `
    --name $BackendAppName `
    --query "defaultHostName"

$healthUrl = "https://$backendHost/health"
Write-Host "  Checking $healthUrl ..."

$health = Wait-ForHttpOk -Url $healthUrl -MaxAttempts 30 -DelaySeconds 10

if ($health.osrm_available -ne $true) {
    Write-Host "  WARNING: /health returned osrm_available=$($health.osrm_available)" -ForegroundColor Red
    Write-Host "  The OSRM ACI may still be loading data. Try again in a few minutes." -ForegroundColor Yellow
    Write-Host "  Debug: az container logs --resource-group $ResourceGroup --name $OsrmAciName" -ForegroundColor Yellow
} else {
    Write-Host "  SUCCESS: /health reports osrm_available=true" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Phase 5: Restart verification
# ---------------------------------------------------------------------------

Write-Step "Verifying ACI restart resilience"

if ($PSCmdlet.ShouldProcess($OsrmAciName, "Restart ACI to verify persistence")) {
    az container restart --resource-group $ResourceGroup --name $OsrmAciName --output none
    Write-Host "  Restarted ACI '$OsrmAciName'. Waiting for recovery..." -ForegroundColor Yellow

    Start-Sleep -Seconds 15
    for ($i = 1; $i -le 20; $i++) {
        $state = Invoke-AzText container show `
            --resource-group $ResourceGroup `
            --name $OsrmAciName `
            --query "instanceView.state"
        if ($state -eq "Running") { break }
        Write-Host "  State: $state — waiting 10s ($i/20)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }

    if ($state -ne "Running") {
        throw "OSRM ACI did not recover after restart. Current state: $state"
    }

    # Re-check health after restart
    Start-Sleep -Seconds 30
    $health2 = Wait-ForHttpOk -Url $healthUrl -MaxAttempts 12 -DelaySeconds 10
    if ($health2.osrm_available -eq $true) {
        Write-Host "  SUCCESS: OSRM recovered after restart — osrm_available=true" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: osrm_available=$($health2.osrm_available) after restart." -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------------------
# Phase 5: Azure Monitor alert
# ---------------------------------------------------------------------------

if (-not $SkipMonitoring) {
    Write-Step "Setting up Azure Monitor crash-loop alert"

    if ([string]::IsNullOrWhiteSpace($AlertEmail)) {
        Write-Host "  No -AlertEmail provided, skipping alert creation." -ForegroundColor Yellow
        Write-Host "  Re-run with -AlertEmail your@email.com to enable crash-loop alerts." -ForegroundColor Yellow
    } else {
        # Create action group
        if (-not (Test-AzResourceExists monitor action-group show --resource-group $ResourceGroup --name "pacman-alerts")) {
            if ($PSCmdlet.ShouldProcess("pacman-alerts", "Create action group")) {
                az monitor action-group create `
                    --resource-group $ResourceGroup `
                    --name "pacman-alerts" `
                    --short-name "pacman" `
                    --action email admin $AlertEmail `
                    --output none
                Write-Host "  Created action group 'pacman-alerts' → $AlertEmail" -ForegroundColor Green
            }
        } else {
            Write-Host "  Action group 'pacman-alerts' already exists." -ForegroundColor Yellow
        }

        # Create metric alert on RestartCount
        $aciResourceId = Invoke-AzText container show `
            --resource-group $ResourceGroup `
            --name $OsrmAciName `
            --query "id"

        if (-not (Test-AzResourceExists monitor metrics alert show --resource-group $ResourceGroup --name "osrm-crash-alert")) {
            if ($PSCmdlet.ShouldProcess("osrm-crash-alert", "Create metric alert")) {
                az monitor metrics alert create `
                    --resource-group $ResourceGroup `
                    --name "osrm-crash-alert" `
                    --scopes $aciResourceId `
                    --condition "avg RestartCount > 3" `
                    --window-size 5m `
                    --evaluation-frequency 1m `
                    --action "pacman-alerts" `
                    --description "OSRM routing container is crash-looping" `
                    --output none
                Write-Host "  Created metric alert 'osrm-crash-alert'." -ForegroundColor Green
            }
        } else {
            Write-Host "  Metric alert 'osrm-crash-alert' already exists." -ForegroundColor Yellow
        }
    }
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

Write-Step "OSRM routing service deployment complete"
Write-Host "  ACI:   $OsrmAciName ($aciIp:5000)" -ForegroundColor Cyan
Write-Host "  VNet:  $VNetName ($AciSubnet + $AppSubnet)" -ForegroundColor Cyan
Write-Host "  Data:  $StorageAccountName / $OsrmFileShare" -ForegroundColor Cyan
Write-Host "  URL:   OSRM_URL=$osrmUrl (on $BackendAppName)" -ForegroundColor Cyan
Write-Host ""
