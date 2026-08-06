param(
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BundledAdb = Join-Path $ProjectRoot ".tools\android\platform-tools\adb.exe"
$TabletUrl = "http://127.0.0.1:3000/tablet"

function Get-JarvisAdb {
    $SystemAdb = Get-Command adb.exe -ErrorAction SilentlyContinue
    if ($SystemAdb) {
        return $SystemAdb.Source
    }
    if (Test-Path -LiteralPath $BundledAdb) {
        return $BundledAdb
    }
    throw @"
Android Platform Tools are missing.
Run scripts\install-tablet-tools.ps1 after reviewing and accepting Google's SDK license.
"@
}

function Assert-LastAdbCommand {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

try {
    $ApiResponse = Invoke-WebRequest -UseBasicParsing `
        "http://127.0.0.1:8000/api/v1/health/live" `
        -TimeoutSec 4
    $WebResponse = Invoke-WebRequest -UseBasicParsing $TabletUrl -TimeoutSec 4
    if ($ApiResponse.StatusCode -ne 200 -or $WebResponse.StatusCode -ne 200) {
        throw "Jarvis did not return a ready response."
    }
}
catch {
    throw "Jarvis is not running. Start Jarvis before connecting the tablet."
}

$AdbPath = Get-JarvisAdb
& $AdbPath start-server | Out-Null
Assert-LastAdbCommand "Starting the Android device bridge"

$DeviceRows = @(
    & $AdbPath devices |
        Select-Object -Skip 1 |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ }
)
Assert-LastAdbCommand "Reading connected Android devices"

if ($DeviceRows.Count -eq 0) {
    throw "No Android tablet was found. Connect it by USB and enable USB debugging."
}
if ($DeviceRows.Count -gt 1) {
    throw "More than one Android device is connected. Keep only the intended tablet connected."
}

$Parts = $DeviceRows[0] -split "\s+"
$Serial = $Parts[0]
$State = $Parts[1]
if ($State -eq "unauthorized") {
    throw "The tablet has not trusted this computer. Confirm the USB debugging prompt on the tablet."
}
if ($State -ne "device") {
    throw "The tablet is not ready. adb state: $State"
}

& $AdbPath -s $Serial reverse tcp:3000 tcp:3000
Assert-LastAdbCommand "Creating the private web USB tunnel"
& $AdbPath -s $Serial reverse tcp:8000 tcp:8000
Assert-LastAdbCommand "Creating the private API USB tunnel"

$ReverseRules = @(& $AdbPath -s $Serial reverse --list)
if (
    -not ($ReverseRules -match "tcp:3000 tcp:3000") -or
    -not ($ReverseRules -match "tcp:8000 tcp:8000")
) {
    throw "The tablet USB tunnel could not be verified."
}

if (-not $NoOpen) {
    & $AdbPath -s $Serial shell am start `
        -a android.intent.action.VIEW `
        -d $TabletUrl | Out-Null
    Assert-LastAdbCommand "Opening the Jarvis tablet terminal"
}

Write-Host ""
Write-Host "Jarvis tablet terminal is connected."
Write-Host "Device: $Serial"
Write-Host "Tablet URL: $TabletUrl"
Write-Host "Only USB loopback forwarding is active; no LAN port was opened."
