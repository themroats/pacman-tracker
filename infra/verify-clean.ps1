<#
.SYNOPSIS
    Clean full bring-up of the verification stack for a final pre-push check.

.DESCRIPTION
    Stops any warm verification services, then rebuilds the isolated verification
    database from scratch — drop, recreate, restore the frozen snapshot, and reseed
    — then starts the backend (exercising the normal startup/migration/validation
    path) and the frontend fresh. Use this before pushing to catch startup/schema
    regressions that the warm loop misses.

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

Assert-BackendPython
if (-not ((Test-HostDbTools) -or (Test-DbContainerRunning (Get-DbContainer)))) {
    throw "Need host 'psql' + 'pg_restore' on PATH, or the running DB container " +
          "'$(Get-DbContainer)'. Start it with: docker compose up -d db"
}
if (-not $NoFrontend) { Assert-Command npm "Install Node.js 20+." }

# 0. Stop any warm services from a previous verify-up so this clean run owns the ports.
Write-Step "Stopping any warm verification services"
Stop-ProcessOnPort $Port
if (-not $NoFrontend) { Stop-ProcessOnPort $FrontendPort }

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
$backend = Start-BackendProcess -RepoRoot $RepoRoot -Url $DbUrl -Port $Port

# 4. Start the frontend fresh.
if (-not $NoFrontend) {
    $frontend = Start-Frontend -RepoRoot $RepoRoot -FrontendPort $FrontendPort
}

Write-Host "`nClean verification stack is up (rebuilt from snapshot):" -ForegroundColor Green
Write-Host "  backend : http://localhost:$Port  (DEV_AUTH_BYPASS on)"
if (-not $NoFrontend) { Write-Host "  frontend: http://localhost:$FrontendPort" }
Write-Host "  Run the full suite: cd frontend; npm run test:e2e"
