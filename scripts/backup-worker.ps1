param(
    [string]$BackupDirectory = "",
    [int]$CheckIntervalMinutes = 60,
    [int]$DueHours = 20,
    [int]$RetentionCount = 30
)

$ErrorActionPreference = "Continue"
$BackupScript = Join-Path $PSScriptRoot "backup.ps1"

while ($true) {
    try {
        & $BackupScript `
            -BackupDirectory $BackupDirectory `
            -IfDue `
            -DueHours $DueHours `
            -RetentionCount $RetentionCount `
            -Quiet
        if ($LASTEXITCODE -ne 0) {
            throw "Backup command exited with code $LASTEXITCODE."
        }
    }
    catch {
        Write-Error "$(Get-Date -Format o) $($_.Exception.Message)"
    }
    Start-Sleep -Seconds ([Math]::Max(1, $CheckIntervalMinutes) * 60)
}
