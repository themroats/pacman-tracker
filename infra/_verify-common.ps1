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
# calling shell; fall back to whatever `python` is on PATH. Checks both the
# Windows (.venv\Scripts) and POSIX (.venv/bin) interpreter layouts.
function Get-BackendPython {
    $repoRoot = Get-RepoRoot
    foreach ($rel in @(".venv\Scripts\python.exe", ".venv/bin/python")) {
        $candidate = Join-Path $repoRoot $rel
        if (Test-Path $candidate) { return $candidate }
    }
    return "python"
}

function Assert-Command {
    param([string]$Name, [string]$Hint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found on PATH. $Hint"
    }
}

# Validate that a usable backend Python interpreter exists. Prefers the repo
# virtualenv (Windows or POSIX layout), so — unlike `Assert-Command python` — this
# does not require a system `python` on PATH when the venv interpreter is present.
function Assert-BackendPython {
    $repoRoot = Get-RepoRoot
    foreach ($rel in @(".venv\Scripts\python.exe", ".venv/bin/python")) {
        if (Test-Path (Join-Path $repoRoot $rel)) { return }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) { return }
    throw "No backend Python found. Create the project virtualenv " +
          "(python -m venv .venv) or ensure 'python' is on PATH."
}

# True if host 'psql' and 'pg_restore' are both on PATH — snapshot restore needs
# pg_restore, so a partial install (psql only) should not pass the preflight.
function Test-HostDbTools {
    return ((Test-HostCommand psql) -and (Test-HostCommand pg_restore))
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
    # Seeded only when the specific synthetic demo user exists. Checking for any
    # user would wrongly treat an unrelated non-empty DB as a valid baseline and
    # could let the DEV_AUTH_BYPASS "first user" resolve to the wrong identity.
    $count = Invoke-Psql -Url $Url -Sql "SELECT count(*) FROM users WHERE strava_athlete_id = 9000000001"
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
    # Idempotency (mirrors the Python restore path): clear existing snapshot rows
    # first so a re-run against a non-empty DB does not fail with duplicate keys.
    # CASCADE also clears dependent demo rows, which the seed step recreates.
    & docker exec -e "PGPASSWORD=$($p.Password)" $container `
        psql -U $p.User -d $p.Database `
        -c "TRUNCATE cities, neighborhoods, street_segments RESTART IDENTITY CASCADE"
    if ($LASTEXITCODE -ne 0) { throw "Failed to clear snapshot tables before restore." }
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

# True if a local TCP port is already being listened on. Used to keep the warm
# launcher idempotent (don't spawn a second backend that can't bind the port).
# Uses Get-NetTCPConnection where available (Windows), else a portable loopback
# TcpClient probe so the check still works on PowerShell Core on macOS/Linux.
function Test-PortInUse {
    param([int]$Port)
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        try {
            return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
        } catch { }
    }
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $client.Connect("127.0.0.1", $Port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

# Stop whatever process is listening on a local port. Used by verify-clean to
# actually stop warm services before a clean bring-up. Falls back to `lsof` when
# Get-NetTCPConnection is unavailable (macOS/Linux).
function Stop-ProcessOnPort {
    param([int]$Port)
    $procIds = @()
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        try {
            $procIds = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty OwningProcess -Unique
        } catch { }
    } elseif (Get-Command lsof -ErrorAction SilentlyContinue) {
        $procIds = lsof -ti "tcp:$Port" -sTCP:LISTEN 2>$null
    }
    foreach ($procId in $procIds) {
        if (-not $procId) { continue }
        try {
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Host "  stopped process $procId on port $Port" -ForegroundColor DarkGray
        } catch { }
    }
}

# Start the backend (uvicorn) against the verification DB with the bypass on.
# Start-Process -Environment is PowerShell 7+ only, so set the env vars on the
# current process (inherited by the child at spawn) and restore them afterwards
# to stay compatible with Windows PowerShell 5.1.
function Start-BackendProcess {
    param(
        [string]$RepoRoot,
        [string]$Url,
        [int]$Port,
        [switch]$Reload
    )
    $backendDir = Join-Path $RepoRoot "backend"
    $procArgs = @("-m", "uvicorn", "app.main:app")
    if ($Reload) { $procArgs += "--reload" }
    $procArgs += @("--port", "$Port")

    $prevDb = $env:DATABASE_URL
    $prevBypass = $env:DEV_AUTH_BYPASS
    $env:DATABASE_URL = $Url
    $env:DEV_AUTH_BYPASS = "1"
    try {
        $backend = Start-Process -PassThru -WorkingDirectory $backendDir `
            -FilePath (Get-BackendPython) -ArgumentList $procArgs
    } finally {
        $env:DATABASE_URL = $prevDb
        $env:DEV_AUTH_BYPASS = $prevBypass
    }
    Write-Host "  backend PID $($backend.Id)" -ForegroundColor DarkGray
    return $backend
}
