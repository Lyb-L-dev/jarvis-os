param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,
    [Parameter(Mandatory = $true)]
    [string]$Confirmation,
    [string]$BackupDirectory = "",
    [switch]$RestoreVault,
    [string]$VaultDestination = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if ($Confirmation -cne "RESTORE JARVIS") {
    throw "Restore cancelled. The exact confirmation text is: RESTORE JARVIS"
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($BackupDirectory)) {
    $BackupDirectory = Join-Path $ProjectRoot "backups"
}
$BackupRoot = [System.IO.Path]::GetFullPath($BackupDirectory)
$BackupPrefix = $BackupRoot.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
) + [System.IO.Path]::DirectorySeparatorChar

if ($DryRun) {
    Write-Output "[dry-run] Selected backup: $BackupPath"
    Write-Output "[dry-run] Plan: verify-backup.ps1 (checksum + staging restore)"
    Write-Output "[dry-run] Plan: safety backup.ps1 before restore (includes vault archive when configured)"
    Write-Output "[dry-run] Plan: staged pg_restore -> jarvis_restore_<random>; swap databases; previous kept as jarvis_before_<stamp>"
    if ($RestoreVault) {
        $target = "manifest vault root"
        if (-not [string]::IsNullOrWhiteSpace($VaultDestination)) {
            $target = $VaultDestination
        }
        Write-Output "[dry-run] Plan: vault archive extraction to $target (entry-level boundary validation)"
    }
    Write-Output "[dry-run] Complete. Nothing was executed."
    exit 0
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
if (-not $resolvedBackup.StartsWith(
    $BackupPrefix,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Backup path escaped the configured backup directory."
}
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

    if ($RestoreVault) {
        $stem = [System.IO.Path]::GetFileNameWithoutExtension($resolvedBackup)
        $restoreManifest = Get-Content `
            -LiteralPath (Join-Path $BackupRoot "$stem.manifest.json") `
            -Raw -Encoding UTF8 |
            ConvertFrom-Json
        if (-not $restoreManifest.vault -or -not $restoreManifest.vault.file_name) {
            throw "Selected backup has no vault archive to restore."
        }
        $vaultArchive = [System.IO.Path]::GetFullPath(
            (Join-Path $BackupRoot $restoreManifest.vault.file_name)
        )
        if (-not $vaultArchive.StartsWith(
            $BackupPrefix,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Vault archive path escaped the configured backup directory."
        }
        if (-not (Test-Path -LiteralPath $vaultArchive)) {
            throw "Vault archive listed in the manifest was not found."
        }

        $destination = ""
        if (-not [string]::IsNullOrWhiteSpace($VaultDestination)) {
            $destination = [System.IO.Path]::GetFullPath($VaultDestination.Trim())
        }
        elseif ($restoreManifest.vault.root_path) {
            $destination = [System.IO.Path]::GetFullPath(
                $restoreManifest.vault.root_path
            )
        }
        else {
            throw "Vault destination is unknown; pass -VaultDestination."
        }
        if ([System.IO.Path]::GetDirectoryName($destination) -eq $destination) {
            throw "Vault destination cannot be a drive root."
        }
        if ($destination.StartsWith(
            $BackupPrefix,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Vault destination cannot be inside the backup directory."
        }
        New-Item -ItemType Directory -Path $destination -Force | Out-Null

        # Entry-level boundary validation: every archive entry must stay
        # inside the destination. The restore never deletes or writes files
        # outside the vault; files inside the vault are overwritten by design
        # (the pre-restore safety backup already snapshotted them).
        $destinationPrefix = $destination.TrimEnd(
            [System.IO.Path]::DirectorySeparatorChar,
            [System.IO.Path]::AltDirectorySeparatorChar
        ) + [System.IO.Path]::DirectorySeparatorChar
        foreach ($entry in @(tar -tzf $vaultArchive)) {
            $clean = $entry.Trim().Replace("\", "/")
            if ($clean -eq "./" -or $clean -eq "." -or $clean -eq "") {
                continue
            }
            if ($clean.StartsWith("/") -or $clean -match "^[A-Za-z]:") {
                throw "Vault archive contains an absolute entry: $entry"
            }
            if ($clean.Split("/") -contains "..") {
                throw "Vault archive contains a parent traversal entry: $entry"
            }
            $combined = [System.IO.Path]::GetFullPath(
                (Join-Path $destination ($clean -replace "/", "\"))
            )
            if (-not $combined.StartsWith(
                $destinationPrefix,
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
                throw "Vault entry escapes the destination: $entry"
            }
        }

        tar -xzf $vaultArchive -C $destination
        if ($LASTEXITCODE -ne 0) {
            throw "Extracting vault archive failed."
        }
        Write-Output "Vault restored to: $destination"
    }
}
finally {
    docker exec $containerName rm -f $containerBackup *> $null
}
