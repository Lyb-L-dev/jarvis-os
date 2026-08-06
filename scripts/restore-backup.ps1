param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,
    [Parameter(Mandatory = $true)]
    [string]$Confirmation,
    [string]$BackupDirectory = ""
)

$ErrorActionPreference = "Stop"

if ($Confirmation -cne "RESTORE JARVIS") {
    throw "Restore cancelled. The exact confirmation text is: RESTORE JARVIS"
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($BackupDirectory)) {
    $BackupDirectory = Join-Path $ProjectRoot "backups"
}
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "Jarvis Core is running. Use 停止 Jarvis.cmd before restoring a backup."
}

& (Join-Path $PSScriptRoot "verify-backup.ps1") `
    -BackupPath $BackupPath `
    -BackupDirectory $BackupDirectory
if ($LASTEXITCODE -ne 0) {
    throw "Restore verification failed."
}

& (Join-Path $PSScriptRoot "backup.ps1") `
    -BackupDirectory $BackupDirectory `
    -RetentionCount 30 `
    -Quiet
if ($LASTEXITCODE -ne 0) {
    throw "Safety backup before restore failed."
}

$containerName = "jarvis-postgres"
$resolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path
$stamp = [DateTime]::UtcNow.ToString("yyyyMMdd_HHmmss")
$stageDatabase = "jarvis_restore_$([Guid]::NewGuid().ToString('N').Substring(0, 10))"
$previousDatabase = "jarvis_before_$stamp"
$containerBackup = "/tmp/jarvis-restore-$stamp.dump"

function Assert-DockerCommand {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

try {
    docker cp $resolvedBackup "${containerName}:${containerBackup}" *> $null
    Assert-DockerCommand "Copying selected backup"
    docker exec $containerName createdb --username jarvis $stageDatabase
    Assert-DockerCommand "Creating staged restore database"
    docker exec $containerName pg_restore `
        --exit-on-error `
        --no-owner `
        --no-privileges `
        --username jarvis `
        --dbname $stageDatabase `
        $containerBackup *> $null
    Assert-DockerCommand "Restoring staged database"

    $swapSql = @"
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'jarvis' AND pid <> pg_backend_pid();
ALTER DATABASE jarvis RENAME TO $previousDatabase;
ALTER DATABASE $stageDatabase RENAME TO jarvis;
"@
    docker exec $containerName psql `
        --username jarvis `
        --dbname postgres `
        --set ON_ERROR_STOP=1 `
        --command $swapSql
    Assert-DockerCommand "Activating restored database"

    Write-Output "Restore completed. Previous database kept as: $previousDatabase"
}
finally {
    docker exec $containerName rm -f $containerBackup *> $null
}
