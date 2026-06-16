# Shared helpers for the local browser verification harness launchers (feature 008).
# Dot-sourced by verify-up.ps1, verify-reset.ps1, verify-clean.ps1.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Get-RepoRoot {
    return (Split-Path -Parent $PSScriptRoot)
}

# Resolve the Python interpreter to use for backend commands. Prefer the repo
# virtualenv so the launchers work whether or not the venv is activated in the
# calling shell; fall back to whatever `python` is on PATH.
function Get-BackendPython {
    $venvPython = Join-Path (Get-RepoRoot) ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) { return $venvPython }
    return "python"
}

function Assert-Command {
    param([string]$Name, [string]$Hint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH. $Hint"
    }
}

function Test-HostCommand {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

# Dockerized Postgres container name (overridable via VERIFY_DB_CONTAINER).
function Get-DbContainer {
    if ($env:VERIFY_DB_CONTAINER) { return $env:VERIFY_DB_CONTAINER }
    return "pacman-tracker-db-1"
}

function Test-DbContainerRunning {
    param([string]$Container)
    if (-not (Test-HostCommand docker)) { return $false }
    $name = (& docker ps --filter "name=^/$Container$" --format "{{.Names}}" 2>$null)
    return ($name -eq $Container)
}

# Split a postgres URL into its user / password / database parts.
function Get-DbParts {
    param([string]$Url)
    $u = [System.Uri]$Url
    $userPass = $u.UserInfo -split ':', 2
    return [pscustomobject]@{
        Host     = $u.Host
        Port     = $u.Port
        User     = $userPass[0]
        Password = if ($userPass.Count -gt 1) { $userPass[1] } else { "" }
        Database = $u.AbsolutePath.TrimStart('/')
    }
}

# Default isolated verification database (overridable via VERIFICATION_DATABASE_URL).
function Get-VerificationDbUrl {
    if ($env:VERIFICATION_DATABASE_URL) { return $env:VERIFICATION_DATABASE_URL }
    return "postgresql://pacman:pacman_dev@localhost:5432/pacman_verify"
}

function Get-DbName {
    param([string]$Url)
    return ([System.Uri]$Url).AbsolutePath.TrimStart('/')
}

function Get-AdminDbUrl {
    # Same server/credentials but the maintenance 'postgres' database.
    param([string]$Url)
    $u = [System.Uri]$Url
    $userInfo = $u.UserInfo
    return "postgresql://$userInfo@$($u.Host):$($u.Port)/postgres"
}

function Invoke-Psql {
    param([string]$Url, [string]$Sql)
    $p = Get-DbParts $Url
    if (Test-HostCommand psql) {
        # Host-first: connect to the (possibly Dockerized) server over TCP.
        $env:PGPASSWORD = $p.Password
        $out = & psql -h $p.Host -p $p.Port -U $p.User -d $p.Database -v ON_ERROR_STOP=1 -tAc $Sql 2>&1
    }
    elseif (Test-DbContainerRunning (Get-DbContainer)) {
        # Fallback: run psql inside the container (connects to its local server).
        $container = Get-DbContainer
        $out = & docker exec -e "PGPASSWORD=$($p.Password)" $container `
            psql -U $p.User -d $p.Database -v ON_ERROR_STOP=1 -tAc $Sql 2>&1
    }
    else {
        throw "Neither host 'psql' nor a running DB container '$(Get-DbContainer)' is available. " +
              "Start the database (docker compose up -d db) or install PostgreSQL client tools."
    }
    if ($LASTEXITCODE -ne 0) { throw "psql failed: $out" }
    return ($out | Out-String).Trim()
}

function Test-VerificationDbExists {
    param([string]$Url)
    $dbName = Get-DbName $Url
    $admin = Get-AdminDbUrl $Url
    $exists = Invoke-Psql -Url $admin -Sql "SELECT 1 FROM pg_database WHERE datname='$dbName'"
    return ($exists -eq "1")
}

function New-VerificationDb {
    param([string]$Url)
    $dbName = Get-DbName $Url
    $admin = Get-AdminDbUrl $Url
    Write-Step "Creating verification database '$dbName'"
    Invoke-Psql -Url $admin -Sql "CREATE DATABASE `"$dbName`"" | Out-Null
    Invoke-Psql -Url $Url -Sql "CREATE EXTENSION IF NOT EXISTS postgis" | Out-Null
}

function Remove-VerificationDb {
    param([string]$Url)
    $dbName = Get-DbName $Url
    $admin = Get-AdminDbUrl $Url
    Write-Step "Dropping verification database '$dbName'"
    Invoke-Psql -Url $admin -Sql "DROP DATABASE IF EXISTS `"$dbName`" WITH (FORCE)" | Out-Null
}

function Test-VerificationDbSeeded {
    param([string]$Url)
    # Seeded when at least one user row exists.
    $count = Invoke-Psql -Url $Url -Sql "SELECT count(*) FROM users"
    return ([int]$count -gt 0)
}

function Get-SnapshotPath {
    param([string]$RepoRoot)
    return (Join-Path $RepoRoot "specs/008-browser-verification-harness/snapshot/seattle.dump")
}

# Defense-in-depth guard mirroring app.scripts._verify_guard: only ever operate
# on the configured verification database.
function Assert-VerificationDb {
    param([string]$Url)
    $expected = Get-DbName (Get-VerificationDbUrl)
    $actual = Get-DbName $Url
    if (-not $expected -or $actual -ne $expected) {
        throw "Refusing to operate on database '$actual'; only the verification " +
              "database '$expected' is allowed."
    }
}

function Restore-Snapshot {
    param([string]$RepoRoot, [string]$Url)
    $snapshot = Get-SnapshotPath $RepoRoot
    if (-not (Test-Path $snapshot)) {
        throw "Frozen snapshot not found at $snapshot. Build it with: " +
              "python -m app.scripts.snapshot_verification build --output `"$snapshot`""
    }
    Assert-VerificationDb $Url
    Write-Step "Restoring frozen Seattle snapshot"

    if (Test-HostCommand pg_restore) {
        # Host-first: the Python restore (guarded) drives host pg_restore.
        Push-Location (Join-Path $RepoRoot "backend")
        try {
            & (Get-BackendPython) -m app.scripts.snapshot_verification restore --input $snapshot --database-url $Url
            if ($LASTEXITCODE -ne 0) { throw "Snapshot restore failed (exit $LASTEXITCODE)." }
        } finally { Pop-Location }
        return
    }

    # Fallback: copy the dump into the container and restore there.
    $container = Get-DbContainer
    if (-not (Test-DbContainerRunning $container)) {
        throw "Neither host 'pg_restore' nor a running DB container '$container' is available. " +
              "Start the database (docker compose up -d db) or install PostgreSQL client tools."
    }
    $p = Get-DbParts $Url
    $remote = "/tmp/verify-seattle.dump"
    & docker cp $snapshot "${container}:${remote}"
    if ($LASTEXITCODE -ne 0) { throw "docker cp of snapshot into '$container' failed." }
    & docker exec -e "PGPASSWORD=$($p.Password)" $container `
        pg_restore --data-only --no-owner --no-privileges -U $p.User -d $p.Database $remote
    if ($LASTEXITCODE -ne 0) { throw "Snapshot restore failed (exit $LASTEXITCODE)." }
}

function Invoke-Migrations {
    param([string]$RepoRoot, [string]$Url)
    Write-Step "Applying database migrations (alembic upgrade head)"
    Push-Location (Join-Path $RepoRoot "backend")
    try {
        $prev = $env:DATABASE_URL
        $env:DATABASE_URL = $Url
        try {
            & (Get-BackendPython) -m alembic upgrade head
            if ($LASTEXITCODE -ne 0) { throw "Migrations failed (exit $LASTEXITCODE)." }
        } finally {
            $env:DATABASE_URL = $prev
        }
    } finally { Pop-Location }
}

function Invoke-Seed {
    param([string]$RepoRoot, [string]$Url)
    Write-Step "Seeding demo user + sample data"
    Push-Location (Join-Path $RepoRoot "backend")
    try {
        & (Get-BackendPython) -m app.scripts.seed_verification --database-url $Url
        if ($LASTEXITCODE -ne 0) { throw "Seed failed (exit $LASTEXITCODE)." }
    } finally { Pop-Location }
}

function Invoke-Reset {
    param([string]$RepoRoot, [string]$Url)
    Write-Step "Fast data-only reset to baseline"
    Push-Location (Join-Path $RepoRoot "backend")
    try {
        & (Get-BackendPython) -m app.scripts.reset_verification --database-url $Url
        if ($LASTEXITCODE -ne 0) { throw "Reset failed (exit $LASTEXITCODE)." }
    } finally { Pop-Location }
}

function Start-Frontend {
    param([string]$RepoRoot, [int]$FrontendPort)
    Write-Step "Starting frontend dev server on port $FrontendPort"
    $frontendDir = Join-Path $RepoRoot "frontend"
    # On Windows `npm` is `npm.cmd`; Start-Process -FilePath "npm" fails, so
    # resolve the real launcher path (or fall back to cmd.exe /c).
    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
    if ($npmCmd -and $npmCmd.Path) {
        $frontend = Start-Process -PassThru -WorkingDirectory $frontendDir -FilePath $npmCmd.Path `
            -ArgumentList @("run", "dev", "--", "--port", "$FrontendPort")
    } else {
        $frontend = Start-Process -PassThru -WorkingDirectory $frontendDir -FilePath "cmd.exe" `
            -ArgumentList @("/c", "npm", "run", "dev", "--", "--port", "$FrontendPort")
    }
    Write-Host "  frontend PID $($frontend.Id)" -ForegroundColor DarkGray
    return $frontend
}
