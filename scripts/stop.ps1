param(
    [switch]$StopDatabase
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeFile = Join-Path $ProjectRoot ".runtime\services.json"
$ComposeFile = Join-Path $ProjectRoot "infra\docker-compose.yml"

if (Test-Path -LiteralPath $RuntimeFile) {
    $runtime = Get-Content -LiteralPath $RuntimeFile -Raw -Encoding UTF8 |
        ConvertFrom-Json
    foreach ($entry in @(
        @{ Name = "browser worker"; Id = $runtime.browser_worker_pid; Expected = "node" },
        @{ Name = "backup worker"; Id = $runtime.backup_pid; Expected = "powershell" },
        @{ Name = "companion"; Id = $runtime.companion_pid; Expected = "python" },
        @{ Name = "web"; Id = $runtime.web_pid; Expected = "node" },
        @{ Name = "api"; Id = $runtime.api_pid; Expected = "python" }
    )) {
        if (-not $entry.Id) {
            continue
        }
        $process = Get-Process -Id ([int]$entry.Id) -ErrorAction SilentlyContinue
        if ($process -and $process.ProcessName -eq $entry.Expected) {
            Stop-Process -Id $process.Id -Force
            Write-Host "Stopped Jarvis $($entry.Name)."
        }
    }
    Remove-Item -LiteralPath $RuntimeFile -Force
}
else {
    Write-Host "No Jarvis runtime record was found."
}

$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    docker compose -f $ComposeFile --profile automation stop n8n-ingress n8n `
        2>$null | Out-Null
    $automationStopExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorAction
}
if ($automationStopExitCode -eq 0) {
    Write-Host "Stopped Jarvis n8n Provider."
}
else {
    Write-Warning "Jarvis n8n Provider did not stop cleanly (exit $automationStopExitCode)."
}

if ($StopDatabase) {
    docker compose -f $ComposeFile --profile automation stop
    if ($LASTEXITCODE -ne 0) {
        throw "Stopping PostgreSQL failed with exit code $LASTEXITCODE."
    }
    Write-Host "Stopped Jarvis database."
}
