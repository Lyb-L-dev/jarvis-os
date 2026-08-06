$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Failures = [System.Collections.Generic.List[string]]::new()
$Warnings = [System.Collections.Generic.List[string]]::new()
$Passes = [System.Collections.Generic.List[string]]::new()

function Test-Requirement {
    param(
        [bool]$Condition,
        [string]$Pass,
        [string]$Fail
    )
    if ($Condition) {
        $Passes.Add($Pass)
    }
    else {
        $Failures.Add($Fail)
    }
}

foreach ($CommandName in @("python", "node", "npm", "docker", "ollama")) {
    Test-Requirement `
        -Condition ($null -ne (Get-Command $CommandName -ErrorAction SilentlyContinue)) `
        -Pass "$CommandName is available" `
        -Fail "$CommandName is missing"
}

Test-Requirement `
    -Condition (Test-Path -LiteralPath (Join-Path $ProjectRoot ".env")) `
    -Pass "Local configuration exists" `
    -Fail "Local configuration is missing; run scripts\setup.ps1"
Test-Requirement `
    -Condition (Test-Path -LiteralPath (Join-Path $ProjectRoot ".venv\Scripts\python.exe")) `
    -Pass "Python environment exists" `
    -Fail "Python environment is missing; run scripts\setup.ps1"
Test-Requirement `
    -Condition (Test-Path -LiteralPath (Join-Path $ProjectRoot "apps\web\node_modules\next")) `
    -Pass "Web dependencies exist" `
    -Fail "Web dependencies are missing; run scripts\setup.ps1"

$PreviousErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
docker version *> $null
$DockerExitCode = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorPreference
Test-Requirement `
    -Condition ($DockerExitCode -eq 0) `
    -Pass "Docker engine is ready" `
    -Fail "Docker engine is not ready"

$ErrorActionPreference = "Continue"
$OllamaModels = ollama list 2>$null
$ErrorActionPreference = $PreviousErrorPreference
Test-Requirement `
    -Condition ([bool](($OllamaModels -join "`n") -match "qwen3:4b-instruct-2507-q4_K_M")) `
    -Pass "Local Qwen model is installed" `
    -Fail "Local Qwen model is missing"

foreach ($Endpoint in @(
    @{
        Name = "Jarvis Core"
        Url = "http://127.0.0.1:8000/api/v1/health/live"
    },
    @{
        Name = "Jarvis Web"
        Url = "http://127.0.0.1:3000"
    }
)) {
    try {
        $Response = Invoke-WebRequest `
            -Uri $Endpoint.Url `
            -UseBasicParsing `
            -TimeoutSec 8
        Test-Requirement `
            -Condition ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 400) `
            -Pass "$($Endpoint.Name) is ready" `
            -Fail "$($Endpoint.Name) returned an error"
    }
    catch {
        $Failures.Add("$($Endpoint.Name) is not reachable")
    }
}

try {
    $ModelStatus = Invoke-RestMethod `
        -Uri "http://127.0.0.1:8000/api/v1/models/status" `
        -TimeoutSec 8
    $ConfiguredCount = @($ModelStatus.providers | Where-Object { $_.configured }).Count
    $Passes.Add("$ConfiguredCount/$($ModelStatus.providers.Count) model providers are configured")
    if ($ConfiguredCount -lt $ModelStatus.providers.Count) {
        $Warnings.Add("Some cloud providers are not configured; local fallback remains available.")
    }
}
catch {
    $Warnings.Add("Model provider status could not be read.")
}

foreach ($Pass in $Passes) {
    Write-Output "[PASS] $Pass"
}
foreach ($Warning in $Warnings) {
    Write-Output "[WARN] $Warning"
}
foreach ($Failure in $Failures) {
    Write-Output "[FAIL] $Failure"
}

if ($Failures.Count -gt 0) {
    throw "Preflight failed with $($Failures.Count) blocking issue(s)."
}

Write-Output "Jarvis preflight passed with $($Warnings.Count) warning(s)."
