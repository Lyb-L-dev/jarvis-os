param(
    [switch]$NoBrowser,
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ApiDirectory = Join-Path $ProjectRoot "apps\api"
$WebDirectory = Join-Path $ProjectRoot "apps\web"
$DesktopDirectory = Join-Path $ProjectRoot "apps\desktop"
$RuntimeDirectory = Join-Path $ProjectRoot ".runtime"
$RuntimeFile = Join-Path $RuntimeDirectory "services.json"
$CompanionOutputLog = Join-Path $RuntimeDirectory "companion.log"
$CompanionErrorLog = Join-Path $RuntimeDirectory "companion-error.log"
$ApiOutputLog = Join-Path $RuntimeDirectory "api.log"
$ApiErrorLog = Join-Path $RuntimeDirectory "api-error.log"
$BackupOutputLog = Join-Path $RuntimeDirectory "backup.log"
$BackupErrorLog = Join-Path $RuntimeDirectory "backup-error.log"
$BrowserWorkerOutputLog = Join-Path $RuntimeDirectory "browser-worker.log"
$BrowserWorkerErrorLog = Join-Path $RuntimeDirectory "browser-worker-error.log"
$BrowserWorkerPath = Join-Path $ProjectRoot "apps\browser-worker\server.cjs"
$ComposeFile = Join-Path $ProjectRoot "infra\docker-compose.yml"

function Assert-LastCommand {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

function Get-ListeningProcessId {
    param([int]$Port)

    $line = netstat -ano |
        Select-String "LISTENING" |
        Select-String ":$Port\s" |
        Select-Object -First 1
    if (-not $line) {
        return $null
    }
    $parts = $line.ToString().Trim() -split "\s+"
    return [int]$parts[-1]
}

function Wait-ForUrl {
    param(
        [string]$Url,
        [string]$Name,
        [int]$Attempts = 20
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                return
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "$Name did not become ready."
}

function Test-EnvFlag {
    param([string]$Name)

    $environmentFile = Join-Path $ProjectRoot ".env"
    if (-not (Test-Path -LiteralPath $environmentFile)) {
        return $false
    }
    $match = Select-String `
        -LiteralPath $environmentFile `
        -Pattern "^$([Regex]::Escape($Name))\s*=\s*(true|1|yes)\s*$" `
        -CaseSensitive:$false
    return $null -ne $match
}

$pageConvergenceEnabled = Test-EnvFlag -Name "V3_PAGE_CONVERGENCE_ENABLED"
if ($pageConvergenceEnabled) {
    $env:V3_PAGE_CONVERGENCE_ENABLED = "true"
    $InterfaceUrl = "http://127.0.0.1:3000/chat"
}
else {
    $env:V3_PAGE_CONVERGENCE_ENABLED = "false"
    $InterfaceUrl = "http://127.0.0.1:3000"
}

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Jarvis dependencies are missing. Run scripts\setup.ps1 first."
}

New-Item -ItemType Directory -Path $RuntimeDirectory -Force | Out-Null

$existingRuntime = $null
if (Test-Path -LiteralPath $RuntimeFile) {
    $existingRuntime = Get-Content -LiteralPath $RuntimeFile -Raw -Encoding UTF8 |
        ConvertFrom-Json
}

docker version *> $null
if ($LASTEXITCODE -ne 0) {
    $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path -LiteralPath $dockerDesktop)) {
        throw "Docker Desktop is not installed."
    }
    Write-Host "Starting Docker Desktop..."
    Start-Process -WindowStyle Hidden -FilePath $dockerDesktop
    $dockerReady = $false
    for ($attempt = 1; $attempt -le 15; $attempt++) {
        Start-Sleep -Seconds 4
        docker version *> $null
        if ($LASTEXITCODE -eq 0) {
            $dockerReady = $true
            break
        }
    }
    if (-not $dockerReady) {
        throw "Docker Desktop did not become ready."
    }
}

Write-Host "Starting Jarvis database..."
$n8nProviderEnabled = Test-EnvFlag -Name "V2_N8N_PROVIDER_ENABLED"
if ($n8nProviderEnabled) {
    foreach ($secretName in @(
        "n8n_encryption_key",
        "webhook_secret",
        "n8n_owner_password"
    )) {
        $secretPath = Join-Path $ProjectRoot ".data\n8n-secrets\$secretName"
        if (-not (Test-Path -LiteralPath $secretPath)) {
            throw "Jarvis n8n secrets are missing. Run scripts\setup-n8n-provider.ps1 first."
        }
    }
    docker compose -f $ComposeFile --profile automation up -d
}
else {
    docker compose -f $ComposeFile up -d
}
Assert-LastCommand "Starting Jarvis infrastructure"

if ($n8nProviderEnabled) {
    Wait-ForUrl `
        -Url "http://127.0.0.1:5680/healthz" `
        -Name "Jarvis n8n Provider" `
        -Attempts 30
}

$browserWorkerProcess = $null
$browserResearchEnabled = Test-EnvFlag -Name "V2_BROWSER_RESEARCH_ENABLED"
if ($browserResearchEnabled) {
    $browserSecretPath = Join-Path $ProjectRoot ".data\browser-secrets\webhook_secret"
    $edgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if (-not (Test-Path -LiteralPath $browserSecretPath)) {
        throw "Browser Worker secret is missing. Run scripts\setup-browser-worker.ps1 manually first."
    }
    if (-not (Test-Path -LiteralPath $edgePath)) {
        throw "Microsoft Edge is required for the isolated Browser Worker."
    }
    $browserPid = Get-ListeningProcessId -Port 5690
    if ($browserPid) {
        $candidate = Get-Process -Id $browserPid -ErrorAction SilentlyContinue
        if (-not $candidate -or $candidate.ProcessName -ne "node") {
            throw "Port 5690 is already used by a non-Node process."
        }
        $browserWorkerProcess = $candidate
    }
    else {
        Write-Host "Starting Jarvis isolated Browser Worker..."
        $nodePath = (Get-Command node.exe).Source
        $browserWorkerProcess = Start-Process -WindowStyle Hidden -PassThru `
            -FilePath $nodePath `
            -ArgumentList @($BrowserWorkerPath) `
            -WorkingDirectory $ProjectRoot `
            -RedirectStandardOutput $BrowserWorkerOutputLog `
            -RedirectStandardError $BrowserWorkerErrorLog
    }
    Wait-ForUrl `
        -Url "http://127.0.0.1:5690/healthz" `
        -Name "Jarvis Browser Worker" `
        -Attempts 20
}

Push-Location $ApiDirectory
try {
    & $PythonPath -m alembic upgrade head
    Assert-LastCommand "Applying database migrations"
}
finally {
    Pop-Location
}

if (-not (Get-ListeningProcessId -Port 8000)) {
    Write-Host "Starting Jarvis Core..."
    Start-Process -WindowStyle Hidden -FilePath $PythonPath `
        -ArgumentList @(
            "-m",
            "app"
        ) `
        -WorkingDirectory $ApiDirectory `
        -RedirectStandardOutput $ApiOutputLog `
        -RedirectStandardError $ApiErrorLog
}
Wait-ForUrl -Url "http://127.0.0.1:8000/api/v1/health/live" -Name "Jarvis Core"

$companionProcess = $null
if ($existingRuntime -and $existingRuntime.companion_pid) {
    $candidate = Get-Process -Id ([int]$existingRuntime.companion_pid) `
        -ErrorAction SilentlyContinue
    if ($candidate -and $candidate.ProcessName -eq "python") {
        $companionProcess = $candidate
    }
}
if (-not $companionProcess) {
    Write-Host "Starting Jarvis Windows Companion..."
    $companionProcess = Start-Process -WindowStyle Hidden -PassThru `
        -FilePath $PythonPath `
        -ArgumentList @("-m", "jarvis_desktop") `
        -WorkingDirectory $DesktopDirectory `
        -RedirectStandardOutput $CompanionOutputLog `
        -RedirectStandardError $CompanionErrorLog
    Start-Sleep -Seconds 2
    if (-not (Get-Process -Id $companionProcess.Id -ErrorAction SilentlyContinue)) {
        throw "Jarvis Windows Companion exited during startup. Check .runtime logs."
    }
}

$backupProcess = $null
if ($existingRuntime -and $existingRuntime.backup_pid) {
    $candidate = Get-Process -Id ([int]$existingRuntime.backup_pid) `
        -ErrorAction SilentlyContinue
    if ($candidate -and $candidate.ProcessName -eq "powershell") {
        $backupProcess = $candidate
    }
}
if (-not $backupProcess) {
    Write-Host "Starting Jarvis automatic backup worker..."
    $powershellPath = (
        Get-Command "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    ).Source
    $backupProcess = Start-Process -WindowStyle Hidden -PassThru `
        -FilePath $powershellPath `
        -ArgumentList @(
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            (Join-Path $ProjectRoot "scripts\backup-worker.ps1")
        ) `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $BackupOutputLog `
        -RedirectStandardError $BackupErrorLog
    Start-Sleep -Seconds 1
    if (-not (Get-Process -Id $backupProcess.Id -ErrorAction SilentlyContinue)) {
        throw "Jarvis backup worker exited during startup. Check .runtime logs."
    }
}

$buildId = Join-Path $WebDirectory ".next\BUILD_ID"
$needsWebBuild = $Rebuild -or -not (Test-Path -LiteralPath $buildId)
if (-not $needsWebBuild) {
    $buildTime = (Get-Item -LiteralPath $buildId).LastWriteTimeUtc
    $webInputs = @()
    foreach ($relativeDirectory in @("src", "public")) {
        $inputDirectory = Join-Path $WebDirectory $relativeDirectory
        if (Test-Path -LiteralPath $inputDirectory) {
            $webInputs += Get-ChildItem -LiteralPath $inputDirectory -Recurse -File
        }
    }
    $webInputs += Get-ChildItem -LiteralPath $WebDirectory -File |
        Where-Object {
            $_.Name -match `
                "^(package(-lock)?\.json|next\.config\..+|postcss\.config\..+|tsconfig\.json)$"
        }
    $newerInput = $webInputs |
        Where-Object { $_.LastWriteTimeUtc -gt $buildTime } |
        Select-Object -First 1
    if ($newerInput) {
        Write-Host "Jarvis interface sources changed after the last build."
        $needsWebBuild = $true
    }
}

$previousPageConvergenceEnabled = $null
if ($existingRuntime) {
    $flagProperty = $existingRuntime.PSObject.Properties[
        "page_convergence_enabled"
    ]
    if ($flagProperty) {
        $previousPageConvergenceEnabled = [bool]$flagProperty.Value
    }
}
$webConfigurationChanged =
    $null -eq $previousPageConvergenceEnabled -or
    $previousPageConvergenceEnabled -ne $pageConvergenceEnabled

$webProcessId = Get-ListeningProcessId -Port 3000
if ($webProcessId -and ($needsWebBuild -or $webConfigurationChanged)) {
    if (
        -not $existingRuntime -or
        -not $existingRuntime.web_pid -or
        [int]$existingRuntime.web_pid -ne $webProcessId
    ) {
        throw "Port 3000 is used by an untracked process; refusing to restart it."
    }
    $webProcess = Get-Process -Id $webProcessId -ErrorAction SilentlyContinue
    if (-not $webProcess -or $webProcess.ProcessName -ne "node") {
        throw "Port 3000 is not owned by the tracked Jarvis interface."
    }
    Write-Host "Restarting Jarvis interface to apply source or configuration changes..."
    Stop-Process -Id $webProcessId -Force
    Start-Sleep -Seconds 1
}

if ($needsWebBuild) {
    Write-Host "Building Jarvis interface..."
    Push-Location $WebDirectory
    try {
        npm run build
        Assert-LastCommand "Building the interface"
    }
    finally {
        Pop-Location
    }
}

if (-not (Get-ListeningProcessId -Port 3000)) {
    Write-Host "Starting Jarvis interface..."
    $npmPath = (Get-Command npm.cmd).Source
    Start-Process -WindowStyle Hidden -FilePath $npmPath `
        -ArgumentList @("run", "start") `
        -WorkingDirectory $WebDirectory
}
Wait-ForUrl -Url $InterfaceUrl -Name "Jarvis interface"

$runtime = @{
    api_pid = Get-ListeningProcessId -Port 8000
    web_pid = Get-ListeningProcessId -Port 3000
    companion_pid = $companionProcess.Id
    backup_pid = $backupProcess.Id
    browser_worker_pid = if ($browserWorkerProcess) { $browserWorkerProcess.Id } else { $null }
    page_convergence_enabled = $pageConvergenceEnabled
    started_at = (Get-Date).ToString("o")
}
[System.IO.File]::WriteAllText(
    $RuntimeFile,
    ($runtime | ConvertTo-Json),
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host ""
Write-Host "Jarvis OS is ready: $InterfaceUrl"
if (-not $NoBrowser) {
    Start-Process $InterfaceUrl
}
