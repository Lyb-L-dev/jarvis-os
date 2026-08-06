$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BundledAdb = Join-Path $ProjectRoot ".tools\android\platform-tools\adb.exe"
$SystemAdb = Get-Command adb.exe -ErrorAction SilentlyContinue
$AdbPath = if ($SystemAdb) { $SystemAdb.Source } else { $BundledAdb }

if (-not (Test-Path -LiteralPath $AdbPath)) {
    Write-Host "Android Platform Tools are not installed; no Jarvis USB tunnel exists."
    exit 0
}

$DeviceRows = @(
    & $AdbPath devices |
        Select-Object -Skip 1 |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -match "\sdevice$" }
)
if ($DeviceRows.Count -eq 0) {
    Write-Host "No authorized Android tablet is connected."
    exit 0
}
if ($DeviceRows.Count -gt 1) {
    throw "More than one Android device is connected; disconnect unintended devices first."
}

$Serial = ($DeviceRows[0] -split "\s+")[0]
& $AdbPath -s $Serial reverse --remove tcp:3000 2> $null
& $AdbPath -s $Serial reverse --remove tcp:8000 2> $null

Write-Host "Jarvis USB tunnels were removed from tablet $Serial."
