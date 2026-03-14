[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$SubscriptionId,
    [string]$ResourceGroup = "pacman-tracker-rg",
    [string]$AcrName = "pacmantrackercr",
    [string]$BackendAppName = "pacman-tracker-api",
    [string]$FrontendAppName = "pacman-tracker-web",
    [string]$BackendImageName = "pacman-backend",
    [string]$BackendEnvPath = "backend/.env",
    [switch]$SkipBackend,
    [switch]$SkipFrontend
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendPath = Join-Path $RepoRoot "backend"
$FrontendPath = Join-Path $RepoRoot "frontend"
$ResolvedBackendEnvPath = Join-Path $RepoRoot $BackendEnvPath

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
    $output = az @Arguments --output json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments -join ' ')`n$output"
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

function Read-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        throw "Env file not found: $Path"
    }

    $values = @{}
    foreach ($line in Get-Content $Path) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        if ($line.TrimStart().StartsWith("#")) { continue }
        if ($line -notmatch "^[A-Z0-9_]+=.*$") { continue }

        $parts = $line.Split("=", 2)
        $values[$parts[0]] = $parts[1]
    }

    return $values
}

function Assert-EnvKeys {
    param(
        [hashtable]$EnvValues,
        [string[]]$RequiredKeys
    )

    $missing = @()
    foreach ($key in $RequiredKeys) {
        if (-not $EnvValues.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($EnvValues[$key])) {
            $missing += $key
        }
    }

    if ($missing.Count -gt 0) {
        throw "Missing required env values in ${ResolvedBackendEnvPath}: $($missing -join ', ')"
    }
}

function Wait-ForHttpJson {
    param(
        [string]$Url,
        [int]$MaxAttempts = 24,
        [int]$DelaySeconds = 10
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            return Invoke-RestMethod -Uri $Url -TimeoutSec 30
        } catch {
            if ($attempt -eq $MaxAttempts) {
                throw "Timed out waiting for URL: $Url"
            }
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

function Get-WebContent {
    param([string]$Url)
    return (Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 30).Content
}

function Assert-Contains {
    param(
        [string]$Text,
        [string]$Needle,
        [string]$Label
    )

    if ($Text -notmatch [regex]::Escape($Needle)) {
        throw "$Label did not contain expected value: $Needle"
    }
}

Write-Step "Validating local tooling"
Assert-Command az
Assert-Command npm
Assert-Command npx

$envValues = Read-EnvFile -Path $ResolvedBackendEnvPath
Assert-EnvKeys -EnvValues $envValues -RequiredKeys @(
    "STRAVA_CLIENT_ID",
    "STRAVA_CLIENT_SECRET"
)

if ([string]::IsNullOrWhiteSpace($SubscriptionId)) {
    $SubscriptionId = $envValues["AZURE_SUBSCRIPTION_ID"]
}

if ([string]::IsNullOrWhiteSpace($SubscriptionId)) {
    throw "Azure subscription id must be supplied via -SubscriptionId or AZURE_SUBSCRIPTION_ID in ${ResolvedBackendEnvPath}."
}

Write-Step "Selecting Azure subscription"
$currentAccount = Invoke-AzJson account show
if ($currentAccount.id -ne $SubscriptionId) {
    az account set --subscription $SubscriptionId
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to switch Azure CLI subscription to $SubscriptionId"
    }
}

Write-Step "Validating target Azure resources"
$backendApp = Invoke-AzJson webapp show --resource-group $ResourceGroup --name $BackendAppName
$frontendApp = Invoke-AzJson staticwebapp show --resource-group $ResourceGroup --name $FrontendAppName
$null = Invoke-AzJson acr show --resource-group $ResourceGroup --name $AcrName

$frontendHost = $frontendApp.defaultHostname
$backendHost = $backendApp.defaultHostName
$backendApiBase = "https://$backendHost/api/v1"
$backendHealthUrl = "https://$backendHost/health"

if (-not $SkipBackend) {
    $imageTag = "prod-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    $fullImageName = "${AcrName}.azurecr.io/${BackendImageName}:$imageTag"
    $acrUsername = Invoke-AzText acr credential show --name $AcrName --query username
    $acrPassword = Invoke-AzText acr credential show --name $AcrName --query "passwords[0].value"
    $backendDeployed = $false

    Write-Step "Deploying backend image $fullImageName"
    if ($PSCmdlet.ShouldProcess($BackendAppName, "Build backend image and update App Service container")) {
        az acr build --registry $AcrName --image "${BackendImageName}:$imageTag" $BackendPath
        if ($LASTEXITCODE -ne 0) {
            throw "Backend image build failed."
        }

        az webapp config container set `
            --resource-group $ResourceGroup `
            --name $BackendAppName `
            --container-image-name $fullImageName `
            --container-registry-url "https://$AcrName.azurecr.io" `
            --container-registry-user $acrUsername `
            --container-registry-password $acrPassword `
            --enable-app-service-storage true | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to update App Service container settings."
        }

        az webapp config appsettings set `
            --resource-group $ResourceGroup `
            --name $BackendAppName `
            --settings `
                STRAVA_CLIENT_ID="$($envValues['STRAVA_CLIENT_ID'])" `
                STRAVA_CLIENT_SECRET="$($envValues['STRAVA_CLIENT_SECRET'])" `
                STRAVA_REDIRECT_URI="https://$frontendHost/auth/callback" `
                CORS_ORIGINS="https://$frontendHost" `
                AUTO_LOAD_CITIES_ON_EMPTY_DB=false `
                WEBSITES_ENABLE_APP_SERVICE_STORAGE=true `
                WEBSITES_PORT=8000 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to update backend app settings."
        }

        az webapp restart --resource-group $ResourceGroup --name $BackendAppName | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to restart backend App Service."
        }

        $backendDeployed = $true
    }

    if ($backendDeployed) {
        Write-Step "Verifying backend deployment"
        $health = Wait-ForHttpJson -Url $backendHealthUrl
        if ($health.status -ne "ok") {
            throw "Backend health check returned unexpected payload: $($health | ConvertTo-Json -Compress)"
        }

        $liveImage = Invoke-AzText webapp show --resource-group $ResourceGroup --name $BackendAppName --query "siteConfig.linuxFxVersion"
        Assert-Contains -Text $liveImage -Needle $fullImageName -Label "App Service linuxFxVersion"

        $citiesResponse = Wait-ForHttpJson -Url "$backendApiBase/cities"
        if (-not $citiesResponse.bootstrap_status) {
            throw "Backend cities endpoint returned an unexpected payload."
        }
    }
}

if (-not $SkipFrontend) {
    $frontendDeployed = $false
    Write-Step "Building frontend for production"
    if ($PSCmdlet.ShouldProcess($FrontendAppName, "Build and deploy Static Web App")) {
        Push-Location $FrontendPath
        try {
            $env:VITE_API_URL = $backendApiBase
            npm run build
            if ($LASTEXITCODE -ne 0) {
                throw "Frontend build failed."
            }
        } finally {
            Pop-Location
        }

        $distBundle = Get-ChildItem (Join-Path $FrontendPath "dist/assets") -Filter *.js | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not $distBundle) {
            throw "Frontend dist assets were not created."
        }

        $distBundleText = Get-Content $distBundle.FullName -Raw
        Assert-Contains -Text $distBundleText -Needle "/sync/coverage" -Label "Built frontend bundle"
        Assert-Contains -Text $distBundleText -Needle $backendApiBase -Label "Built frontend bundle"

        $deploymentToken = Invoke-AzText staticwebapp secrets list --resource-group $ResourceGroup --name $FrontendAppName --query "properties.apiKey"
        Push-Location $FrontendPath
        try {
            npx @azure/static-web-apps-cli deploy ./dist --deployment-token $deploymentToken --env production --swa-config-location .
            if ($LASTEXITCODE -ne 0) {
                throw "Static Web App deployment failed."
            }

            $frontendDeployed = $true
        } finally {
            Pop-Location
        }
    }

    if ($frontendDeployed) {
        Write-Step "Verifying frontend deployment"
        Start-Sleep -Seconds 20
        $frontendHtml = Get-WebContent -Url "https://$frontendHost/"
        $assetMatch = [regex]::Match($frontendHtml, '/assets/[^"'' ]+\.js')
        if (-not $assetMatch.Success) {
            throw "Could not find a JavaScript asset in the deployed frontend HTML."
        }

        $assetUrl = "https://$frontendHost$($assetMatch.Value)"
        $liveBundle = Get-WebContent -Url $assetUrl
        Assert-Contains -Text $liveBundle -Needle "/sync/coverage" -Label "Live frontend bundle"
        Assert-Contains -Text $liveBundle -Needle $backendApiBase -Label "Live frontend bundle"
    }
}

Write-Step "Deployment complete"
Write-Host "Backend:  https://$backendHost/health" -ForegroundColor Green
Write-Host "Frontend: https://$frontendHost/" -ForegroundColor Green