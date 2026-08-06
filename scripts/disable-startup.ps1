$ErrorActionPreference = "Stop"

$StartupDirectory = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupDirectory "Jarvis OS.lnk"

if (Test-Path -LiteralPath $ShortcutPath) {
    Remove-Item -LiteralPath $ShortcutPath -Force
    Write-Host "Jarvis OS automatic startup was disabled."
}
else {
    Write-Host "Jarvis OS automatic startup was not enabled."
}
