param(
    [Parameter(Mandatory = $true)]
    [string]$BackupPath,
    [string]$BackupDirectory = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($BackupDirectory)) {
    $BackupDirectory = Join-Path $ProjectRoot "backups"
}
$BackupRoot = [System.IO.Path]::GetFullPath($BackupDirectory)
$ResolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path
$BackupPrefix = $BackupRoot.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
) + [System.IO.Path]::DirectorySeparatorChar
if (-not $ResolvedBackup.StartsWith(
    $BackupPrefix,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "Backup path escaped the configured backup directory."
}

$stem = [System.IO.Path]::GetFileNameWithoutExtension($ResolvedBackup)
$manifestPath = Join-Path $BackupRoot "$stem.manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Backup manifest not found."
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
$actualHash = (Get-FileHash -LiteralPath $ResolvedBackup -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $manifest.sha256) {
    throw "Backup checksum does not match its manifest."
}

$containerName = "jarvis-postgres"
$containerBackup = "/tmp/$stem-verify.dump"
$verifyDatabase = "jarvis_verify_$([Guid]::NewGuid().ToString('N').Substring(0, 12))"

function Assert-DockerCommand {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

try {
    docker cp $ResolvedBackup "${containerName}:${containerBackup}" *> $null
    Assert-DockerCommand "Copying backup for restore verification"

    docker exec $containerName createdb --username jarvis $verifyDatabase
    Assert-DockerCommand "Creating temporary restore database"

    docker exec $containerName pg_restore `
        --exit-on-error `
        --no-owner `
        --no-privileges `
        --username jarvis `
        --dbname $verifyDatabase `
        $containerBackup *> $null
    Assert-DockerCommand "Restoring backup into temporary database"

    $tableCount = (
        docker exec $containerName psql `
            --username jarvis `
            --dbname $verifyDatabase `
            --tuples-only `
            --no-align `
            --command (
                "SELECT COUNT(*) FROM information_schema.tables " +
                "WHERE table_schema = 'public';"
            )
    ).Trim()
    Assert-DockerCommand "Counting restored tables"
    if ([int]$tableCount -lt 1) {
        throw "Restore verification produced no public tables."
    }

    $alembicVersion = (
        docker exec $containerName psql `
            --username jarvis `
            --dbname $verifyDatabase `
            --tuples-only `
            --no-align `
            --command "SELECT version_num FROM alembic_version LIMIT 1;"
    ).Trim()
    Assert-DockerCommand "Reading restored schema version"

    $manifest | Add-Member -NotePropertyName restore_verified_at `
        -NotePropertyValue ([DateTime]::UtcNow.ToString("o")) -Force
    $manifest | Add-Member -NotePropertyName verified_table_count `
        -NotePropertyValue ([int]$tableCount) -Force
    $manifest | Add-Member -NotePropertyName alembic_version `
        -NotePropertyValue $alembicVersion -Force
    [System.IO.File]::WriteAllText(
        $manifestPath,
        ($manifest | ConvertTo-Json -Depth 4),
        [System.Text.UTF8Encoding]::new($false)
    )

    Write-Output "Restore verification passed: $tableCount tables, schema $alembicVersion."
}
finally {
    docker exec $containerName dropdb `
        --username jarvis `
        --if-exists `
        --force `
        $verifyDatabase *> $null
    docker exec $containerName rm -f $containerBackup *> $null
}
