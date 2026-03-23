<#
.SYNOPSIS
    Runs the one-time OSRM data preparation pipeline as an Azure Container Instance job.

.DESCRIPTION
    Downloads Washington state OSM data, extracts, partitions, and customizes it for
    OSRM foot routing. Output is written to an Azure File Share that the OSRM routing
    server ACI reads from.

    This is a one-time operation. Re-run only when OSM data needs to be refreshed.

    Prereqs: Storage Account and File Share must exist (created by deploy-osrm.ps1).
    The VNet and ACI subnet must also exist.

.PARAMETER ResourceGroup
    Azure resource group. Default: pacman-tracker-rg

.PARAMETER Location
    Azure region. Default: eastus

.PARAMETER StorageAccountName
    Storage account containing the OSRM file share. Default: pacmantrackersa

.PARAMETER VNetName
    Virtual network name. Default: pacman-vnet

.PARAMETER AciSubnet
    Subnet for ACI containers. Default: aci-subnet

.PARAMETER OsrmFileShare
    Azure File Share name for OSRM data. Default: osrm-data

.PARAMETER PrepAciName
    Container group name for the prep job. Default: pacman-osrm-prep

.PARAMETER Force
    Re-run preparation even if data already exists on the file share.

.PARAMETER Help
    Show this help message.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ResourceGroup = "pacman-tracker-rg",
    [string]$Location = "eastus",
    [string]$StorageAccountName = "pacmantrackersa",
    [string]$AcrName = "pacmantrackercr",
    [string]$VNetName = "pacman-vnet",
    [string]$AciSubnet = "aci-subnet",
    [string]$OsrmFileShare = "osrm-data",
    [string]$PrepAciName = "pacman-osrm-prep",
    [switch]$Force,
    [switch]$Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Detailed
    exit 0
}

# ---------------------------------------------------------------------------
# Helper functions
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

function Invoke-AzText {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $output = az @Arguments --output tsv 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments -join ' ')`n$output"
    }
    return ($output | Out-String).Trim()
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

function Test-AzResourceExists {
    param([string[]]$Arguments)
    az @Arguments --output json 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

# ---------------------------------------------------------------------------
# Validate prerequisites
# ---------------------------------------------------------------------------

Write-Step "Validating prerequisites"
Assert-Command az

$null = Invoke-AzJson group show --name $ResourceGroup

# Get ACR credentials for ACI image pulls
$acrUser = Invoke-AzText acr credential show --name $AcrName --query username
$acrPass = Invoke-AzText acr credential show --name $AcrName --query "passwords[0].value"
Write-Host "  ACR '$AcrName' credentials retrieved." -ForegroundColor Green

# Ensure storage account and file share exist (create if missing)
if (-not (Test-AzResourceExists storage account show --resource-group $ResourceGroup --name $StorageAccountName)) {
    Write-Host "  Storage account '$StorageAccountName' not found — creating..." -ForegroundColor Yellow
    Invoke-AzJson storage account create `
        --resource-group $ResourceGroup `
        --name $StorageAccountName `
        --location $Location `
        --sku Standard_LRS | Out-Null
    Write-Host "  Created storage account '$StorageAccountName'." -ForegroundColor Green
}

$storageKey = Invoke-AzText storage account keys list `
    --resource-group $ResourceGroup `
    --account-name $StorageAccountName `
    --query "[0].value"

# Ensure file share exists
az storage share create `
    --account-name $StorageAccountName `
    --account-key $storageKey `
    --name $OsrmFileShare `
    --quota 10 `
    --output none 2>$null

Write-Host "  Storage account '$StorageAccountName' and share '$OsrmFileShare' ready." -ForegroundColor Green

# Ensure VNet and ACI subnet exist (needed for VNet-deployed ACI)
if (-not (Test-AzResourceExists network vnet show --resource-group $ResourceGroup --name $VNetName)) {
    Write-Host "  VNet '$VNetName' not found — creating..." -ForegroundColor Yellow
    Invoke-AzJson network vnet create `
        --resource-group $ResourceGroup `
        --name $VNetName `
        --address-prefix "10.0.0.0/16" `
        --location $Location | Out-Null
    Write-Host "  Created VNet '$VNetName'." -ForegroundColor Green
}

if (-not (Test-AzResourceExists network vnet subnet show --resource-group $ResourceGroup --vnet-name $VNetName --name $AciSubnet)) {
    Write-Host "  Subnet '$AciSubnet' not found — creating..." -ForegroundColor Yellow
    Invoke-AzJson network vnet subnet create `
        --resource-group $ResourceGroup `
        --vnet-name $VNetName `
        --name $AciSubnet `
        --address-prefix "10.0.1.0/24" `
        --delegations "Microsoft.ContainerInstance/containerGroups" | Out-Null
    Write-Host "  Created subnet '$AciSubnet'." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Idempotency check: is data already prepared?
# ---------------------------------------------------------------------------

Write-Step "Checking for existing prepared data"

$existingFiles = az storage file list `
    --account-name $StorageAccountName `
    --account-key $storageKey `
    --share-name $OsrmFileShare `
    --query "[?name=='washington-latest.osrm'].{name:name, size:properties.contentLength}" `
    --output json 2>$null | ConvertFrom-Json

if ($existingFiles -and $existingFiles.Count -gt 0 -and -not $Force) {
    $fileSize = $existingFiles[0].size
    # Prepared .osrm file should be at least 1 MB (a partial/empty file would be smaller)
    $minSizeBytes = 1048576
    if ($fileSize -gt $minSizeBytes) {
        Write-Host "  washington-latest.osrm already exists ($([math]::Round($fileSize / 1MB, 1)) MB). Skipping preparation." -ForegroundColor Yellow
        Write-Host "  Use -Force to re-run data preparation." -ForegroundColor Yellow
        exit 0
    } else {
        Write-Host "  WARNING: washington-latest.osrm exists but is only $fileSize bytes (possibly corrupt/partial)." -ForegroundColor Red
        Write-Host "  Proceeding with data preparation..." -ForegroundColor Yellow
    }
} elseif ($Force) {
    Write-Host "  -Force specified, running data preparation regardless of existing data." -ForegroundColor Yellow
} else {
    Write-Host "  No existing prepared data found. Proceeding with preparation." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Clean up any existing prep container
# ---------------------------------------------------------------------------

if (Test-AzResourceExists container show --resource-group $ResourceGroup --name $PrepAciName) {
    Write-Step "Removing existing prep container '$PrepAciName'"
    az container delete --resource-group $ResourceGroup --name $PrepAciName --yes --output none
    Write-Host "  Removed." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Create data prep ACI job
# ---------------------------------------------------------------------------

Write-Step "Starting OSRM data preparation"
Write-Host "  Step 1: Download OSM data (~800 MB) via Alpine container" -ForegroundColor Yellow
Write-Host "  Step 2: Extract/partition/customize via OSRM container" -ForegroundColor Yellow
Write-Host "  Expected total duration: 30-60 minutes." -ForegroundColor Yellow

# Upload both shell scripts to the file share
foreach ($scriptName in @("osrm-download.sh", "osrm-prep.sh")) {
    $localPath = Join-Path $PSScriptRoot $scriptName
    if (-not (Test-Path $localPath)) {
        throw "Shell script not found: $localPath"
    }
    az storage file upload `
        --account-name $StorageAccountName `
        --account-key $storageKey `
        --share-name $OsrmFileShare `
        --source $localPath `
        --path $scriptName `
        --output none 2>$null
}
Write-Host "  Uploaded shell scripts to file share." -ForegroundColor Green

# --- Step 1: Download OSM data (Alpine container with wget) ---

$downloadAciName = "${PrepAciName}-dl"

# Clean up any previous download container
if (Test-AzResourceExists container show --resource-group $ResourceGroup --name $downloadAciName) {
    az container delete --resource-group $ResourceGroup --name $downloadAciName --yes --output none
}

if ($PSCmdlet.ShouldProcess($downloadAciName, "Create download ACI job")) {
    Write-Step "Step 1: Downloading OSM data"
    Invoke-AzJson container create `
        --resource-group $ResourceGroup `
        --name $downloadAciName `
        --image "${AcrName}.azurecr.io/alpine:3.20" `
        --os-type Linux `
        --registry-login-server "${AcrName}.azurecr.io" `
        --registry-username $acrUser `
        --registry-password $acrPass `
        --cpu 1 --memory 1 `
        --vnet $VNetName `
        --subnet $AciSubnet `
        --azure-file-volume-account-name $StorageAccountName `
        --azure-file-volume-account-key $storageKey `
        --azure-file-volume-share-name $OsrmFileShare `
        --azure-file-volume-mount-path "/data" `
        --restart-policy Never `
        --command-line "/bin/sh /data/osrm-download.sh" | Out-Null

    Write-Host "  Download ACI '$downloadAciName' created." -ForegroundColor Green

    # Wait for download to complete
    for ($i = 1; $i -le 120; $i++) {
        $dlInfo = Invoke-AzJson container show --resource-group $ResourceGroup --name $downloadAciName
        $dlState = $dlInfo.instanceView.state
        if ($dlState -eq "Terminated" -or $dlState -eq "Succeeded") { break }
        if ($i % 6 -eq 0) {
            Write-Host "  Download state: $dlState ($([math]::Round($i * 10 / 60, 0)) min elapsed)" -ForegroundColor Yellow
        }
        Start-Sleep -Seconds 10
    }

    # Check exit code
    $dlExit = $dlInfo.containers[0].instanceView.currentState.exitCode
    if ($dlExit -ne 0) {
        Write-Host "  Download logs:" -ForegroundColor Red
        az container logs --resource-group $ResourceGroup --name $downloadAciName 2>$null
        throw "OSM data download failed (exit code $dlExit)."
    }
    Write-Host "  Download complete." -ForegroundColor Green

    # Clean up download container
    az container delete --resource-group $ResourceGroup --name $downloadAciName --yes --output none 2>$null
}

# --- Step 2: Extract/partition/customize (OSRM container) ---

if (Test-AzResourceExists container show --resource-group $ResourceGroup --name $PrepAciName) {
    az container delete --resource-group $ResourceGroup --name $PrepAciName --yes --output none
}

if ($PSCmdlet.ShouldProcess($PrepAciName, "Create OSRM extract/partition/customize ACI job")) {
    Write-Step "Step 2: Extracting, partitioning, and customizing"
    Invoke-AzJson container create `
        --resource-group $ResourceGroup `
        --name $PrepAciName `
        --image "${AcrName}.azurecr.io/osrm-backend:latest" `
        --os-type Linux `
        --registry-login-server "${AcrName}.azurecr.io" `
        --registry-username $acrUser `
        --registry-password $acrPass `
        --cpu 2 --memory 4 `
        --vnet $VNetName `
        --subnet $AciSubnet `
        --azure-file-volume-account-name $StorageAccountName `
        --azure-file-volume-account-key $storageKey `
        --azure-file-volume-share-name $OsrmFileShare `
        --azure-file-volume-mount-path "/data" `
        --restart-policy Never `
        --command-line "/bin/sh /data/osrm-prep.sh" | Out-Null

    Write-Host "  Prep ACI '$PrepAciName' created and running." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Monitor progress and wait for completion
# ---------------------------------------------------------------------------

Write-Step "Monitoring data preparation progress"
Write-Host "  Streaming logs (Ctrl+C to detach — job continues in background)..." -ForegroundColor Yellow

# Give the container a moment to start
Start-Sleep -Seconds 10

# Stream logs (non-blocking — will end when container exits)
try {
    az container logs --resource-group $ResourceGroup --name $PrepAciName --follow 2>$null
} catch {
    Write-Host "  Log streaming ended." -ForegroundColor Yellow
}

# Poll for completion
Write-Step "Waiting for prep job to finish"
for ($i = 1; $i -le 180; $i++) {
    $containerInfo = Invoke-AzJson container show --resource-group $ResourceGroup --name $PrepAciName
    $containerState = $containerInfo.instanceView.state

    if ($containerState -eq "Terminated" -or $containerState -eq "Succeeded") {
        break
    }

    if ($i % 6 -eq 0) {
        Write-Host "  State: $containerState — waiting... ($([math]::Round($i * 10 / 60, 0)) min elapsed)" -ForegroundColor Yellow
    }
    Start-Sleep -Seconds 10
}

# Check exit code
$containers = $containerInfo.containers
if ($containers -and $containers.Count -gt 0) {
    $exitCode = $containers[0].instanceView.currentState.exitCode
} else {
    $exitCode = -1
}

if ($exitCode -ne 0) {
    Write-Host "  Data preparation FAILED with exit code $exitCode." -ForegroundColor Red
    Write-Host "  View logs: az container logs --resource-group $ResourceGroup --name $PrepAciName" -ForegroundColor Yellow
    throw "OSRM data preparation failed."
}

Write-Host "  Data preparation completed successfully." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Verify output
# ---------------------------------------------------------------------------

Write-Step "Verifying prepared data on file share"

$verifyFiles = az storage file list `
    --account-name $StorageAccountName `
    --account-key $storageKey `
    --share-name $OsrmFileShare `
    --query "[?name=='washington-latest.osrm'].{name:name, size:properties.contentLength}" `
    --output json 2>$null | ConvertFrom-Json

if (-not $verifyFiles -or $verifyFiles.Count -eq 0) {
    throw "washington-latest.osrm not found on file share after preparation. Check container logs."
}

$outputSize = $verifyFiles[0].size
Write-Host "  washington-latest.osrm: $([math]::Round($outputSize / 1MB, 1)) MB" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Cleanup prep container
# ---------------------------------------------------------------------------

Write-Step "Cleaning up prep container"

if ($PSCmdlet.ShouldProcess($PrepAciName, "Delete prep ACI container")) {
    az container delete --resource-group $ResourceGroup --name $PrepAciName --yes --output none
    Write-Host "  Deleted prep container '$PrepAciName'." -ForegroundColor Green
}

Write-Step "OSRM data preparation complete"
Write-Host "  File share '$OsrmFileShare' now contains prepared routing data." -ForegroundColor Cyan
Write-Host "  Next: run 'infra/deploy-osrm.ps1' to deploy the routing server." -ForegroundColor Cyan
Write-Host ""
