<#
.SYNOPSIS
    Fast data-only reset of the verification baseline between warm runs (feature 008).

.DESCRIPTION
    Restores the demo dataset to its known baseline WITHOUT re-restoring the frozen
    street snapshot, and clears process-local caches that would otherwise leak
    between runs. Use this between back-to-back verification runs while the stack
    stays warm (started by infra\verify-up.ps1).
#>
[CmdletBinding()]
param()

. (Join-Path $PSScriptRoot "_verify-common.ps1")

$RepoRoot = Get-RepoRoot
$DbUrl = Get-VerificationDbUrl

Assert-Command python "Activate the project virtualenv first."

if (-not (Test-VerificationDbExists -Url $DbUrl)) {
    throw "Verification database does not exist. Run infra\verify-up.ps1 first."
}
if (-not (Test-VerificationDbSeeded -Url $DbUrl)) {
    throw "Verification baseline missing (no demo user). Run infra\verify-up.ps1 first."
}

Invoke-Reset -RepoRoot $RepoRoot -Url $DbUrl

Write-Host "`nBaseline restored. Ready for the next verification run." -ForegroundColor Green
