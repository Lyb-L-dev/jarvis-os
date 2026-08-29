param()

$ErrorActionPreference = "Stop"

$DesktopRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $DesktopRoot "..\..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Spec = Join-Path $DesktopRoot "sidecar\jarvis-sidecar.spec"
$RuntimeRoot = Join-Path $ProjectRoot ".runtime"
$WorkPath = Join-Path $RuntimeRoot "sidecar-build"
$DistPath = Join-Path $RuntimeRoot "sidecar-dist"
$TempPath = Join-Path $RuntimeRoot "sidecar-temp"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Jarvis project Python environment is missing."
}

New-Item -ItemType Directory -Force -Path $WorkPath,$DistPath,$TempPath | Out-Null
$env:TEMP = $TempPath
$env:TMP = $TempPath

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --workpath $WorkPath `
    --distpath $DistPath `
    $Spec
if ($LASTEXITCODE -ne 0) {
    throw "Jarvis Sidecar build failed with exit code $LASTEXITCODE."
}

$Executable = Join-Path $DistPath "jarvis-sidecar\jarvis-sidecar.exe"
if (-not (Test-Path -LiteralPath $Executable)) {
    throw "Jarvis Sidecar executable was not produced."
}
$ResourceRoot = Join-Path $DesktopRoot "resources\sidecar"
if (Test-Path -LiteralPath $ResourceRoot) {
    Remove-Item -LiteralPath $ResourceRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $ResourceRoot | Out-Null
Copy-Item -Path (Join-Path $DistPath "jarvis-sidecar\*") `
    -Destination $ResourceRoot -Recurse -Force
Write-Host "Built Jarvis Sidecar at $Executable"
Write-Host "Prepared bundle resources at $ResourceRoot"
