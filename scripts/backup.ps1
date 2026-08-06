param(
    [string]$BackupDirectory = "",
    [switch]$IfDue,
    [int]$DueHours = 20,
    [int]$RetentionCount = 30,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($BackupDirectory)) {
    $BackupDirectory = Join-Path $ProjectRoot "backups"
}
$BackupRoot = [System.IO.Path]::GetFullPath($BackupDirectory)
$ContainerName = "jarvis-postgres"

function Assert-DockerCommand {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

function Assert-BackupChildPath {
    param([string]$Path)
    $resolved = [System.IO.Path]::GetFullPath($Path)
    $prefix = $BackupRoot.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ) + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Backup path escaped the configured backup directory: $resolved"
    }
    return $resolved
}

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null

if ($IfDue) {
    $latestManifest = Get-ChildItem -LiteralPath $BackupRoot -Filter "*.manifest.json" -File |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
    if ($latestManifest) {
        $age = [DateTime]::UtcNow - $latestManifest.LastWriteTimeUtc
        if ($age.TotalHours -lt $DueHours) {
            if (-not $Quiet) {
                Write-Output "Backup is current; latest backup is $([Math]::Round($age.TotalHours, 1)) hours old."
            }
            exit 0
        }
    }
}

docker inspect $ContainerName *> $null
Assert-DockerCommand "Checking PostgreSQL container"

$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 8)
$backupId = "$stamp-$suffix"
$baseName = "jarvis-$backupId"
$dumpPath = Assert-BackupChildPath (Join-Path $BackupRoot "$baseName.dump")
$partialDumpPath = Assert-BackupChildPath "$dumpPath.partial"
$manifestPath = Assert-BackupChildPath (Join-Path $BackupRoot "$baseName.manifest.json")
$partialManifestPath = Assert-BackupChildPath "$manifestPath.partial"
$checksumPath = Assert-BackupChildPath (Join-Path $BackupRoot "$baseName.sha256")
$containerDumpPath = "/tmp/$baseName.dump"

try {
    docker exec $ContainerName pg_dump `
        --username jarvis `
        --dbname jarvis `
        --format custom `
        --compress 9 `
        --file $containerDumpPath
    Assert-DockerCommand "Creating PostgreSQL backup"

    docker exec $ContainerName pg_restore --list $containerDumpPath *> $null
    Assert-DockerCommand "Validating PostgreSQL archive"

    docker cp "${ContainerName}:${containerDumpPath}" $partialDumpPath *> $null
    Assert-DockerCommand "Copying PostgreSQL backup"
    Move-Item -LiteralPath $partialDumpPath -Destination $dumpPath

    $hash = (Get-FileHash -LiteralPath $dumpPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $size = (Get-Item -LiteralPath $dumpPath).Length
    $alembicVersion = (
        docker exec $ContainerName psql `
            --username jarvis `
            --dbname jarvis `
            --tuples-only `
            --no-align `
            --command "SELECT version_num FROM alembic_version LIMIT 1;"
    ).Trim()
    Assert-DockerCommand "Reading database schema version"

    $manifest = [ordered]@{
        schema_version = 1
        id = $backupId
        created_at = [DateTime]::UtcNow.ToString("o")
        database = "jarvis"
        format = "postgresql-custom"
        file_name = [System.IO.Path]::GetFileName($dumpPath)
        size_bytes = $size
        sha256 = $hash
        archive_verified = $true
        restore_verified_at = $null
        verified_table_count = $null
        alembic_version = $alembicVersion
    }
    [System.IO.File]::WriteAllText(
        $partialManifestPath,
        ($manifest | ConvertTo-Json -Depth 4),
        [System.Text.UTF8Encoding]::new($false)
    )
    Move-Item -LiteralPath $partialManifestPath -Destination $manifestPath
    [System.IO.File]::WriteAllText(
        $checksumPath,
        "$hash  $([System.IO.Path]::GetFileName($dumpPath))`n",
        [System.Text.UTF8Encoding]::new($false)
    )

    $manifests = Get-ChildItem -LiteralPath $BackupRoot -Filter "*.manifest.json" -File |
        Sort-Object LastWriteTimeUtc -Descending
    if ($RetentionCount -gt 0 -and $manifests.Count -gt $RetentionCount) {
        foreach ($expired in $manifests | Select-Object -Skip $RetentionCount) {
            $expiredManifest = Assert-BackupChildPath $expired.FullName
            $expiredData = Get-Content -LiteralPath $expiredManifest -Raw -Encoding UTF8 |
                ConvertFrom-Json
            foreach ($candidate in @(
                (Join-Path $BackupRoot $expiredData.file_name),
                $expiredManifest,
                (Join-Path $BackupRoot (
                    [System.IO.Path]::GetFileNameWithoutExtension($expiredData.file_name) +
                    ".sha256"
                ))
            )) {
                $safeCandidate = Assert-BackupChildPath $candidate
                if (Test-Path -LiteralPath $safeCandidate) {
                    Remove-Item -LiteralPath $safeCandidate -Force
                }
            }
        }
    }

    if (-not $Quiet) {
        Write-Output "Backup created: $dumpPath"
    }
}
finally {
    if (Test-Path -LiteralPath $partialDumpPath) {
        Remove-Item -LiteralPath $partialDumpPath -Force
    }
    if (Test-Path -LiteralPath $partialManifestPath) {
        Remove-Item -LiteralPath $partialManifestPath -Force
    }
    docker exec $ContainerName rm -f $containerDumpPath *> $null
}
