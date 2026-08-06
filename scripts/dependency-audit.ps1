$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$WebDirectory = Join-Path $ProjectRoot "apps\web"

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Python environment is missing. Run scripts\setup.ps1 first."
}

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

& $PythonPath -m pip_audit --progress-spinner off
if ($LASTEXITCODE -ne 0) {
    throw "Python dependency audit failed."
}

Push-Location $WebDirectory
try {
    npm audit `
        --omit=dev `
        --audit-level=high `
        --registry=https://registry.npmjs.org
    if ($LASTEXITCODE -ne 0) {
        throw "Web production dependency audit failed."
    }
}
finally {
    Pop-Location
}

Write-Output "Dependency audits passed."
