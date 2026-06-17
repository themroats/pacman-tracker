<#
.SYNOPSIS
    Thin warm launcher for the local browser verification harness (feature 008).

.DESCRIPTION
    Brings up the isolated verification database (pacman_verify), the backend with
    DEV_AUTH_BYPASS enabled, and the frontend dev server, then leaves them WARM for
    repeated verification runs. Restores the frozen Seattle snapshot and seeds the
    demo user automatically when the verification database is empty.

    LOCAL-ONLY. The auth bypass logs a CRITICAL warning whenever it authenticates a
    request. Never run this against a shared or deployed environment.

.NOTES
    Fast loop:   infra\verify-reset.ps1  (between runs)
    Clean check: infra\verify-clean.ps1  (final pre-push)
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
if (-not ((Test-HostCommand psql) -or (Test-DbContainerRunning (Get-DbContainer)))) {
    throw "Need either host 'psql' on PATH or the running DB container " +
          "'$(Get-DbContainer)'. Start it with: docker compose up -d db"
}
if (-not $NoFrontend) { Assert-Command npm "Install Node.js 20+." }

# 1. Ensure the isolated verification database exists + PostGIS.
if (-not (Test-VerificationDbExists -Url $DbUrl)) {
    New-VerificationDb -Url $DbUrl
}

# 2. Ensure the full schema exists (idempotent) before any seed/seeded check.
Invoke-Migrations -RepoRoot $RepoRoot -Url $DbUrl

# 3. Restore snapshot + seed when empty (first bring-up).
if (-not (Test-VerificationDbSeeded -Url $DbUrl)) {
    Restore-Snapshot -RepoRoot $RepoRoot -Url $DbUrl
    Invoke-Seed -RepoRoot $RepoRoot -Url $DbUrl
} else {
    Write-Host "Verification database already seeded; reusing warm data." -ForegroundColor DarkGray
}

# 3. Start the backend with the bypass enabled, pointed at the verification DB.
# Reuse an already-warm backend if the port is in use (keeps the loop idempotent).
if (Test-PortInUse $Port) {
    Write-Host "Backend port $Port already in use; reusing the warm backend." -ForegroundColor DarkGray
    $backend = $null
} else {
    Write-Step "Starting backend (DEV_AUTH_BYPASS=1) on port $Port"
    $backend = Start-BackendProcess -RepoRoot $RepoRoot -Url $DbUrl -Port $Port -Reload
}

# 4. Start the frontend dev server (reuse a warm one if the port is taken).
if (-not $NoFrontend) {
    if (Test-PortInUse $FrontendPort) {
        Write-Host "Frontend port $FrontendPort already in use; reusing the warm dev server." -ForegroundColor DarkGray
    } else {
        $frontend = Start-Frontend -RepoRoot $RepoRoot -FrontendPort $FrontendPort
    }
}

Write-Host "`nVerification stack is warm:" -ForegroundColor Green
Write-Host "  backend : http://localhost:$Port  (DEV_AUTH_BYPASS on)"
if (-not $NoFrontend) { Write-Host "  frontend: http://localhost:$FrontendPort" }
Write-Host "  reset between runs: infra\verify-reset.ps1"
Write-Host "  clean pre-push run: infra\verify-clean.ps1"
