$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$CheckRunId = [Guid]::NewGuid().ToString("N")
$PytestTempDirectory = Join-Path $ProjectRoot ".runtime\pytest-temp-$CheckRunId"
$PytestCacheDirectory = Join-Path $ProjectRoot ".runtime\pytest-cache-$CheckRunId"

function Assert-LastCommand {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Python virtual environment not found. Run scripts/setup.ps1 first."
}

New-Item -ItemType Directory -Path $PytestTempDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $PytestCacheDirectory -Force | Out-Null

& $PythonPath -m ruff check `
    (Join-Path $ProjectRoot "apps\api") `
    (Join-Path $ProjectRoot "apps\desktop")
Assert-LastCommand "Backend lint"
& $PythonPath -m pytest `
    --basetemp $PytestTempDirectory `
    -o "cache_dir=$PytestCacheDirectory" `
    (Join-Path $ProjectRoot "apps\api\tests") `
    (Join-Path $ProjectRoot "apps\api\app\db\tests") `
    (Join-Path $ProjectRoot "apps\desktop\tests")
Assert-LastCommand "Backend tests"

& (Join-Path $ProjectRoot "scripts\security-check.ps1")
& $PythonPath (Join-Path $ProjectRoot "scripts\evaluate-prompts.py")
Assert-LastCommand "Prompt and policy evaluation"

Push-Location (Join-Path $ProjectRoot "apps\web")
try {
    npm run typecheck
    Assert-LastCommand "Frontend typecheck"
    npm run lint
    Assert-LastCommand "Frontend lint"
}
finally {
    Pop-Location
}
