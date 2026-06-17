<#
.SYNOPSIS
    Fast data-only reset of the verification baseline between warm runs.

.DESCRIPTION
    Restores the demo dataset to its known baseline WITHOUT re-restoring the frozen
    street snapshot. Use this between back-to-back verification runs while the stack
    stays warm (started by infra\verify-up.ps1).

    NOTE: This resets database state only. The reset CLI runs in a separate process
    and cannot clear the already-running backend's in-memory caches (e.g. the OSRM
    availability flag); those clear via their own TTL/force-check or on a restart
    through infra\verify-clean.ps1.
#>
[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot "_verify-common.ps1")

$RepoRoot = Get-RepoRoot
$DbUrl = Get-VerificationDbUrl

Assert-BackendPython

if (-not (Test-VerificationDbExists -Url $DbUrl)) {
    throw "Verification database does not exist. Run infra\verify-up.ps1 first."
}
if (-not (Test-VerificationDbSeeded -Url $DbUrl)) {
    throw "Verification baseline missing (no demo user). Run infra\verify-up.ps1 first."
}

Invoke-Reset -RepoRoot $RepoRoot -Url $DbUrl

Write-Host "`nBaseline restored. Ready for the next verification run." -ForegroundColor Green
