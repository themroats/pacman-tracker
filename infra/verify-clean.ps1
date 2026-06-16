<#
.SYNOPSIS
    Clean full bring-up of the verification stack (feature 008) for a final pre-push check.

.DESCRIPTION
    Rebuilds the isolated verification database from scratch — drop, recreate,
    restore the frozen snapshot, and reseed — then starts the backend (exercising
    the normal startup/migration/validation path) and the frontend fresh. Use this
    before pushing to catch startup/schema regressions that the warm loop misses.

    LOCAL-ONLY. The backend runs with DEV_AUTH_BYPASS=1 (emits a CRITICAL log).
#>
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [int]$FrontendPort = 5173,
    [switch]$NoFrontend
)

. (Join-Path $PSScriptRoot "_verify-common.ps1")

$RepoRoot = Get-RepoRoot
$DbUrl = Get-VerificationDbUrl

Assert-Command python "Activate the project virtualenv first."
if (-not ((Test-HostCommand psql) -or (Test-DbContainerRunning (Get-DbContainer)))) {
    throw "Need either host 'psql' on PATH or the running DB container " +
          "'$(Get-DbContainer)'. Start it with: docker compose up -d db"
}
if (-not $NoFrontend) { Assert-Command npm "Install Node.js 20+." }

# 1. Rebuild the verification database from scratch.
if (Test-VerificationDbExists -Url $DbUrl) {
    Remove-VerificationDb -Url $DbUrl
}
New-VerificationDb -Url $DbUrl

# 2. Apply migrations, then restore snapshot + seed fresh.
Invoke-Migrations -RepoRoot $RepoRoot -Url $DbUrl
Restore-Snapshot -RepoRoot $RepoRoot -Url $DbUrl
Invoke-Seed -RepoRoot $RepoRoot -Url $DbUrl

# 3. Start the backend fresh (normal startup path: migrations + PostGIS validation).
Write-Step "Starting backend fresh (DEV_AUTH_BYPASS=1) on port $Port"
$backendDir = Join-Path $RepoRoot "backend"
$backend = Start-Process -PassThru -WorkingDirectory $backendDir -FilePath (Get-BackendPython) `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--port", "$Port") `
    -Environment @{ DATABASE_URL = $DbUrl; DEV_AUTH_BYPASS = "1" }
Write-Host "  backend PID $($backend.Id)" -ForegroundColor DarkGray

# 4. Start the frontend fresh.
if (-not $NoFrontend) {
    $frontend = Start-Frontend -RepoRoot $RepoRoot -FrontendPort $FrontendPort
}

Write-Host "`nClean verification stack is up (rebuilt from snapshot):" -ForegroundColor Green
Write-Host "  backend : http://localhost:$Port  (DEV_AUTH_BYPASS on)"
if (-not $NoFrontend) { Write-Host "  frontend: http://localhost:$FrontendPort" }
Write-Host "  Run the full suite: cd frontend; npm run test:e2e"
