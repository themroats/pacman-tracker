[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ImageName = "pacman-tracker-backend-local",
    [string]$ContainerName = "pacman-tracker-backend-local",
    [string]$BackendEnvPath = "backend/.env",
    [string]$BackendPath = "backend",
    [string]$DataPath = "backend/data",
    [int]$HostPort = 8000,
    [int]$ContainerPort = 8000,
    [switch]$RemoveImage,
    [switch]$PruneDangling,
    [switch]$Detach
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ResolvedBackendPath = Join-Path $RepoRoot $BackendPath
$ResolvedBackendEnvPath = Join-Path $RepoRoot $BackendEnvPath
$ResolvedDataPath = Join-Path $RepoRoot $DataPath

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

function Invoke-Docker {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed: docker $($Arguments -join ' ')"
    }
}

function Test-DockerObjectExists {
    param(
        [ValidateSet("container", "image")]
        [string]$Kind,
        [string]$Name
    )

    $output = if ($Kind -eq "container") {
        & docker ps -a --filter "name=^/${Name}$" --format "{{.Names}}"
    } else {
        & docker images --format "{{.Repository}}:{{.Tag}}" $Name
    }

    return ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace(($output | Out-String).Trim()))
}

Assert-Command docker

if (-not (Test-Path $ResolvedBackendPath)) {
    throw "Backend path not found: $ResolvedBackendPath"
}

if (-not (Test-Path $ResolvedBackendEnvPath)) {
    throw "Env file not found: $ResolvedBackendEnvPath"
}

if (-not (Test-Path $ResolvedDataPath)) {
    New-Item -ItemType Directory -Path $ResolvedDataPath | Out-Null
}

Write-Step "Removing existing container if present"
if (Test-DockerObjectExists -Kind container -Name $ContainerName) {
    if ($PSCmdlet.ShouldProcess($ContainerName, "Remove existing backend container")) {
        Invoke-Docker rm -f $ContainerName
    }
} else {
    Write-Host "No existing container named $ContainerName was found."
}

if ($RemoveImage -and (Test-DockerObjectExists -Kind image -Name $ImageName)) {
    Write-Step "Removing existing image $ImageName"
    if ($PSCmdlet.ShouldProcess($ImageName, "Remove existing backend image")) {
        Invoke-Docker rmi -f $ImageName
    }
}

if ($PruneDangling) {
    Write-Step "Pruning dangling Docker images and build cache"
    if ($PSCmdlet.ShouldProcess("Docker dangling artifacts", "Prune unused build cache and dangling images")) {
        Invoke-Docker image prune -f
        Invoke-Docker builder prune -f
    }
}

Write-Step "Building backend image $ImageName"
if ($PSCmdlet.ShouldProcess($ImageName, "Build local backend image")) {
    Invoke-Docker build -t $ImageName $ResolvedBackendPath
}

$runArgs = @(
    "run"
    "--rm"
    "--name", $ContainerName
    "-p", "${HostPort}:${ContainerPort}"
    "--env-file", $ResolvedBackendEnvPath
    "-v", "${ResolvedDataPath}:/home/data"
)

if ($Detach) {
    $runArgs += "-d"
}

$runArgs += $ImageName

Write-Step "Starting backend container on http://localhost:$HostPort"
if ($PSCmdlet.ShouldProcess($ContainerName, "Run local backend container")) {
    & docker @runArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed: docker $($runArgs -join ' ')"
    }
}

if ($Detach) {
    Write-Host "Backend container started in detached mode."
    Write-Host "Health check: http://localhost:$HostPort/health"
} else {
    Write-Host "Backend container exited. Review the logs above if that was unexpected."
}