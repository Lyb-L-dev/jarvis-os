param()

$ErrorActionPreference = "Stop"

$DesktopRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $DesktopRoot "..\..")).Path
$ScriptResources = Join-Path $DesktopRoot "resources\scripts"
New-Item -ItemType Directory -Force -Path $ScriptResources | Out-Null
Copy-Item -LiteralPath (Join-Path $ProjectRoot "scripts\backup.ps1") `
    -Destination (Join-Path $ScriptResources "backup.ps1") -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "scripts\verify-backup.ps1") `
    -Destination (Join-Path $ScriptResources "verify-backup.ps1") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "desktop-update-backup.ps1") `
    -Destination (Join-Path $ScriptResources "desktop-update-backup.ps1") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "desktop-observation.ps1") `
    -Destination (Join-Path $ScriptResources "desktop-observation.ps1") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "verify-v4-release-gate.ps1") `
    -Destination (Join-Path $ScriptResources "verify-v4-release-gate.ps1") -Force

& (Join-Path $PSScriptRoot "prepare-ui.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Preparing desktop UI failed with exit code $LASTEXITCODE."
}

& (Join-Path $PSScriptRoot "build-sidecar.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Preparing bundled Sidecar failed with exit code $LASTEXITCODE."
}

$Sidecar = Join-Path $DesktopRoot "resources\sidecar\jarvis-sidecar.exe"
if (-not (Test-Path -LiteralPath $Sidecar)) {
    throw "The bundled Jarvis Sidecar is missing after preparation."
}

& (Join-Path $PSScriptRoot "generate-sbom.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Generating the CycloneDX SBOM failed with exit code $LASTEXITCODE."
}
$Sbom = Join-Path $ProjectRoot ".runtime\release\jarvis-os-v4.cdx.json"
Copy-Item -LiteralPath $Sbom -Destination (Join-Path $DesktopRoot "resources\jarvis-os-v4.cdx.json") -Force

& (Join-Path $PSScriptRoot "generate-release-manifest.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Generating the release manifest failed with exit code $LASTEXITCODE."
}
