param(
    [string]$BackupDirectory = "",
    [switch]$IfDue,
    [int]$DueHours = 20,
    [int]$RetentionCount = 30,
    [string]$VaultPath = "",
    [switch]$SkipVault,
    [long]$VaultSizeLimitBytes = 2147483648,
    [switch]$DryRun,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

# Supports -DryRun for a non-destructive plan-only run (used by the QA gate
# and by CI when PostgreSQL is not available).
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

function Get-ConfiguredVaultPath {
    param([string]$Container)
    $row = (
        docker exec $Container psql `
            --username jarvis `
            --dbname jarvis `
            --tuples-only `
            --no-align `
            --command (
                "SELECT vault_path FROM knowledge_vault_configs " +
                "ORDER BY updated_at DESC LIMIT 1;"
            )
    )
    if ($LASTEXITCODE -ne 0) {
        throw "Reading vault configuration from database failed."
    }
    return ($row -join "`n").Trim()
}

function Assert-SafeVaultPath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "Vault path is empty."
    }
    $candidate = [System.IO.Path]::GetFullPath($Path.Trim())
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
        throw "Vault path does not exist or is not a directory: $candidate"
    }
    if ([System.IO.Path]::GetDirectoryName($candidate) -eq $candidate) {
        throw "A drive root cannot be used as the Vault: $candidate"
    }
    $obsidianMarker = Join-Path $candidate ".obsidian"
    if (-not (Test-Path -LiteralPath $obsidianMarker -PathType Container)) {
        throw "The selected directory is not an Obsidian Vault: $candidate"
    }
    return $candidate
}

New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null

if ($DryRun) {
    Write-Output "[dry-run] Backup directory: $BackupRoot"
    Write-Output "[dry-run] Plan: pg_dump --format custom --compress 9 -> $BackupRoot\jarvis-<stamp>-<id>.dump"
    Write-Output "[dry-run] Plan: pg_restore --list archive validation + SHA256 manifest (schema_version 2) + retention $RetentionCount"
    if ($SkipVault) {
        Write-Output "[dry-run] Plan: vault archive skipped (-SkipVault)"
    }
    elseif (-not [string]::IsNullOrWhiteSpace($VaultPath)) {
        $safeVault = Assert-SafeVaultPath $VaultPath
        Write-Output "[dry-run] Plan: vault archive tar -czf -C $safeVault . (limit $VaultSizeLimitBytes bytes)"
    }
    else {
        Write-Output "[dry-run] Plan: vault path discovered from knowledge_vault_configs; archive limit $VaultSizeLimitBytes bytes; skipped when none configured"
    }
    Write-Output "[dry-run] Complete. Nothing was executed."
    exit 0
}

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

    # Obsidian vault archive (read-only; never writes into the vault).
    # The vault path is discovered from knowledge_vault_configs so the backup
    # always covers the configured vault; explicit -VaultPath overrides it and
    # -SkipVault opts out. The archive and its SHA256 ride the same manifest
    # lifecycle as the PostgreSQL dump (schema_version = 2).
    $vault = $null
    $partialVaultArchivePath = $null
    if (-not $SkipVault) {
        $resolvedVault = ""
        if (-not [string]::IsNullOrWhiteSpace($VaultPath)) {
            $resolvedVault = Assert-SafeVaultPath $VaultPath
        }
        else {
            $configuredVault = Get-ConfiguredVaultPath $ContainerName
            if (-not [string]::IsNullOrWhiteSpace($configuredVault)) {
                $resolvedVault = Assert-SafeVaultPath $configuredVault
            }
        }
        if (-not [string]::IsNullOrWhiteSpace($resolvedVault)) {
            $vaultArchiveName = "$baseName.vault.tar.gz"
            $vaultArchivePath = Assert-BackupChildPath (
                Join-Path $BackupRoot $vaultArchiveName
            )
            $partialVaultArchivePath = Assert-BackupChildPath "$vaultArchivePath.partial"
            tar -czf $partialVaultArchivePath -C $resolvedVault .
            if ($LASTEXITCODE -ne 0) {
                throw "Archiving Obsidian vault failed."
            }
            $vaultSize = (Get-Item -LiteralPath $partialVaultArchivePath).Length
            if ($vaultSize -gt $VaultSizeLimitBytes) {
                throw (
                    "Vault archive exceeds the configured size limit " +
                    "($VaultSizeLimitBytes bytes, actual $vaultSize bytes). " +
                    "Raise -VaultSizeLimitBytes or use -SkipVault."
                )
            }
            Move-Item -LiteralPath $partialVaultArchivePath -Destination $vaultArchivePath
            $vaultHash = (
                Get-FileHash -LiteralPath $vaultArchivePath -Algorithm SHA256
            ).Hash.ToLowerInvariant()
            $vaultFileCount = @(
                tar -tzf $vaultArchivePath |
                    Where-Object { $_ -ne "./" -and $_ -ne "." }
            ).Count
            $vault = [ordered]@{
                file_name = $vaultArchiveName
                sha256 = $vaultHash
                size_bytes = $vaultSize
                file_count = $vaultFileCount
                root_path = $resolvedVault
            }
        }
    }

    # The dump is finalized only after the vault archive succeeds, so a vault
    # failure never leaves an orphan dump without a manifest (finally cleans
    # the partial dump).
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
        schema_version = 2
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
        vault = $vault
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
            if ($expiredData.vault -and $expiredData.vault.file_name) {
                $vaultCandidate = Assert-BackupChildPath (
                    Join-Path $BackupRoot $expiredData.vault.file_name
                )
                if (Test-Path -LiteralPath $vaultCandidate) {
                    Remove-Item -LiteralPath $vaultCandidate -Force
                }
            }
        }
    }

    if (-not $Quiet) {
        Write-Output "Backup created: $dumpPath"
        if ($vault) {
            Write-Output "Vault archive created: $vaultArchivePath ($vaultFileCount files)"
        }
        elseif (-not $SkipVault) {
            Write-Output "No Obsidian vault configured; vault backup skipped."
        }
    }
}
finally {
    if (Test-Path -LiteralPath $partialDumpPath) {
        Remove-Item -LiteralPath $partialDumpPath -Force
    }
    if (Test-Path -LiteralPath $partialManifestPath) {
        Remove-Item -LiteralPath $partialManifestPath -Force
    }
    if ($partialVaultArchivePath -and (Test-Path -LiteralPath $partialVaultArchivePath)) {
        Remove-Item -LiteralPath $partialVaultArchivePath -Force
    }
    docker exec $ContainerName rm -f $containerDumpPath *> $null
}
