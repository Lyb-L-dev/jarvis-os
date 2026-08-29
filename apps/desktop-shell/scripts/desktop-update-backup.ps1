param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDirectory,
    [Parameter(Mandatory = $true)]
    [string]$BackupScript,
    [Parameter(Mandatory = $true)]
    [string]$VerifyScript
)

$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath($BackupDirectory)
$backup = [System.IO.Path]::GetFullPath($BackupScript)
$verify = [System.IO.Path]::GetFullPath($VerifyScript)
if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) {
    throw "Bundled backup script is missing."
}
if (-not (Test-Path -LiteralPath $verify -PathType Leaf)) {
    throw "Bundled backup verification script is missing."
}
New-Item -ItemType Directory -Force -Path $root | Out-Null

& $backup -BackupDirectory $root -SkipVault -Quiet
if ($LASTEXITCODE -ne 0) {
    throw "Database backup failed with exit code $LASTEXITCODE."
}
$dump = Get-ChildItem -LiteralPath $root -Filter "*.dump" -File |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
if (-not $dump) {
    throw "Database backup did not produce a dump."
}
& $verify -BackupPath $dump.FullName -BackupDirectory $root
if ($LASTEXITCODE -ne 0) {
    throw "Database restore verification failed with exit code $LASTEXITCODE."
}
$manifest = [System.IO.Path]::ChangeExtension($dump.FullName, "manifest.json")
$record = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $record.restore_verified_at -or [int]$record.verified_table_count -lt 1) {
    throw "Backup manifest does not contain successful restore evidence."
}
Write-Output $manifest
