param(
    [switch]$AcceptAndroidSdkLicense
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ToolsRoot = Join-Path $ProjectRoot ".tools\android"
$AdbPath = Join-Path $ToolsRoot "platform-tools\adb.exe"
$RuntimeRoot = Join-Path $ProjectRoot ".runtime"
$ArchivePath = Join-Path $RuntimeRoot "platform-tools-latest-windows.zip"
$DownloadUrl = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"

function Assert-GoogleSignature {
    param([string]$ExecutablePath)

    $Signature = Get-AuthenticodeSignature -LiteralPath $ExecutablePath
    if (
        $Signature.Status -ne "Valid" -or
        -not $Signature.SignerCertificate -or
        $Signature.SignerCertificate.Subject -notmatch "Google"
    ) {
        throw "Android Platform Tools signature validation failed."
    }
}

$SystemAdb = Get-Command adb.exe -ErrorAction SilentlyContinue
if ($SystemAdb) {
    Write-Host "Using the existing Android Platform Tools:"
    Write-Host $SystemAdb.Source
    & $SystemAdb.Source version
    exit $LASTEXITCODE
}

if (Test-Path -LiteralPath $AdbPath) {
    Assert-GoogleSignature -ExecutablePath $AdbPath
    Write-Host "Jarvis tablet tools are already installed."
    & $AdbPath version
    exit $LASTEXITCODE
}

if (-not $AcceptAndroidSdkLicense) {
    throw @"
Android Platform Tools are not installed.
Review Google's Android SDK license, then explicitly run:

  powershell -ExecutionPolicy Bypass -File .\scripts\install-tablet-tools.ps1 -AcceptAndroidSdkLicense

Jarvis will download only Google's official Platform Tools package.
"@
}

$ResolvedProjectRoot = [System.IO.Path]::GetFullPath($ProjectRoot)
$ResolvedToolsRoot = [System.IO.Path]::GetFullPath($ToolsRoot)
if (
    -not $ResolvedToolsRoot.StartsWith(
        $ResolvedProjectRoot,
        [StringComparison]::OrdinalIgnoreCase
    )
) {
    throw "Tablet tools path is outside the Jarvis project."
}

New-Item -ItemType Directory -Path $ToolsRoot -Force | Out-Null
New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null

Write-Host "Downloading Google Android Platform Tools..."
Invoke-WebRequest -UseBasicParsing -Uri $DownloadUrl -OutFile $ArchivePath

Write-Host "Extracting Android Platform Tools inside Jarvis .tools..."
Expand-Archive -LiteralPath $ArchivePath -DestinationPath $ToolsRoot

if (-not (Test-Path -LiteralPath $AdbPath)) {
    throw "The downloaded Android Platform Tools package is incomplete."
}
Assert-GoogleSignature -ExecutablePath $AdbPath
Remove-Item -LiteralPath $ArchivePath -Force

Write-Host "Jarvis tablet tools are installed and signature-verified."
& $AdbPath version
if ($LASTEXITCODE -ne 0) {
    throw "adb self-check failed with exit code $LASTEXITCODE."
}
