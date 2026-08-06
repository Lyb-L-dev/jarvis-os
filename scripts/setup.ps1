$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot ".venv"
$PythonPath = Join-Path $VenvPath "Scripts\python.exe"

function Assert-LastCommand {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".env"))) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot ".env.example") -Destination (Join-Path $ProjectRoot ".env")
    Write-Host "Created .env from .env.example. Add API keys locally when ready."
}

if (-not (Test-Path -LiteralPath $PythonPath)) {
    python -m venv $VenvPath
    Assert-LastCommand "Creating Python virtual environment"
}

& $PythonPath -m pip install --upgrade pip
Assert-LastCommand "Upgrading pip"

Push-Location (Join-Path $ProjectRoot "apps\api")
try {
    & $PythonPath -m pip install -e ".[dev]"
    Assert-LastCommand "Installing backend dependencies"
}
finally {
    Pop-Location
}

Push-Location (Join-Path $ProjectRoot "apps\web")
try {
    npm install
    Assert-LastCommand "Installing frontend dependencies"
}
finally {
    Pop-Location
}

Push-Location (Join-Path $ProjectRoot "apps\desktop")
try {
    & $PythonPath -m pip install -e "."
    Assert-LastCommand "Installing Windows Companion dependencies"
}
finally {
    Pop-Location
}

Write-Host "Jarvis OS development environment is ready."
