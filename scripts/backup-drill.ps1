<#
Restore drill for Jarvis backups.

Purpose: automate the staging-database restore verification (the same
jarvis_*_<random> mechanism used by verify-backup.ps1) and extend it with
content-level checks: table count, Alembic schema version, key-table row
counts, and the Sprint 1 status-enum preflight (expect zero invalid rows).

Environment gating:
  - PostgreSQL not running and -Strict not set  -> prints SKIPPED, exit 0.
  - -Strict and PostgreSQL not running          -> throws (for manual runs).
  - -DryRun                                     -> prints the full plan and the
    exact commands it would run; requires no Docker/PostgreSQL and exits 0.

Usage examples:
  scripts\backup-restore-drill.ps1 -DryRun
  scripts\backup-restore-drill.ps1
  scripts\backup-restore-drill.ps1 -BackupPath <path to .dump> -Strict
#>

param(
    [string]$BackupPath = "",
    [string]$BackupDirectory = "",
    [switch]$DryRun,
    [switch]$Strict,
    [switch]$SkipVault,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($BackupDirectory)) {
    $BackupDirectory = Join-Path $ProjectRoot "backups"
}
$BackupRoot = [System.IO.Path]::GetFullPath($BackupDirectory)
$BackupPrefix = $BackupRoot.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
) + [System.IO.Path]::DirectorySeparatorChar
$ContainerName = "jarvis-postgres"

function Assert-DrillChildPath {
    param([string]$Path)
    $resolved = [System.IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith(
        $BackupPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Backup path escaped the configured backup directory: $resolved"
    }
    return $resolved
}

function Assert-DockerCommand {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

# ---- Resolve the backup (explicit path or latest manifest) ----------------
if ([string]::IsNullOrWhiteSpace($BackupPath)) {
    $latestManifest = Get-ChildItem -LiteralPath $BackupRoot `
        -Filter "*.manifest.json" -File |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
    if (-not $latestManifest) {
        if ($DryRun) {
            Write-Output "[dry-run] No backup manifests found in $BackupRoot."
            Write-Output "[dry-run] Plan: staged pg_restore -> jarvis_drill_<random>; validation (table count, alembic_version, row counts, status-enum preflight); drop staging database."
            Write-Output "[dry-run] Complete. Nothing was executed."
            exit 0
        }
        throw "No backup manifests found in $BackupRoot."
    }
    $manifestPath = $latestManifest.FullName
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 |
        ConvertFrom-Json
    $dumpPath = Assert-DrillChildPath (Join-Path $BackupRoot $manifest.file_name)
}
else {
    $resolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path
    $dumpPath = Assert-DrillChildPath $resolvedBackup
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($resolvedBackup)
    $manifestPath = Join-Path $BackupRoot "$stem.manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "Backup manifest not found: $manifestPath"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 |
        ConvertFrom-Json
}

if (-not (Test-Path -LiteralPath $dumpPath)) {
    throw "Backup archive not found: $dumpPath"
}
$actualHash = (
    Get-FileHash -LiteralPath $dumpPath -Algorithm SHA256
).Hash.ToLowerInvariant()
if ($actualHash -ne $manifest.sha256) {
    throw "Backup checksum does not match its manifest."
}

$vaultArchive = $null
if ($manifest.vault -and $manifest.vault.file_name -and -not $SkipVault) {
    $vaultArchive = Assert-DrillChildPath (
        Join-Path $BackupRoot $manifest.vault.file_name
    )
    if (-not (Test-Path -LiteralPath $vaultArchive)) {
        throw "Vault archive listed in manifest was not found."
    }
    $vaultHash = (
        Get-FileHash -LiteralPath $vaultArchive -Algorithm SHA256
    ).Hash.ToLowerInvariant()
    if ($vaultHash -ne $manifest.vault.sha256) {
        throw "Vault archive checksum does not match its manifest."
    }
}

$stageDatabase = "jarvis_drill_$([Guid]::NewGuid().ToString('N').Substring(0, 12))"
$containerDump = "/tmp/jarvis-drill-$([Guid]::NewGuid().ToString('N').Substring(0, 8)).dump"

function Get-ValidationSql {
    return @"
SELECT 'memories' AS table_name, count(*) AS row_count FROM memories
UNION ALL SELECT 'knowledge_documents', count(*) FROM knowledge_documents
UNION ALL SELECT 'knowledge_vault_configs', count(*) FROM knowledge_vault_configs
UNION ALL SELECT 'agent_runs', count(*) FROM agent_runs
UNION ALL SELECT 'chat_messages', count(*) FROM chat_messages
UNION ALL SELECT 'tool_executions', count(*) FROM tool_executions;
"@
}

function Get-StatusPreflightSql {
    return @"
SELECT 'agent_approvals' AS table_name, count(*) AS invalid_rows
FROM agent_approvals
WHERE status NOT IN ('pending','approved','rejected','consumed','expired')
UNION ALL
SELECT 'agent_runs', count(*)
FROM agent_runs
WHERE status NOT IN ('created','running','waiting_for_input','waiting_for_sources',
  'waiting_for_model_approval','waiting_for_draft_review',
  'waiting_for_report_review','completed','rejected','cancelled','failed')
UNION ALL
SELECT 'memories', count(*)
FROM memories
WHERE status NOT IN ('pending','active','inactive','rejected','superseded','deleted')
UNION ALL
SELECT 'tool_executions', count(*)
FROM tool_executions
WHERE status NOT IN ('created','pending_approval','executing','succeeded',
  'failed','expired','approved','rejected')
UNION ALL
SELECT 'tool_approvals', count(*)
FROM tool_approvals
WHERE status NOT IN ('pending','approved','rejected','expired','consumed');
"@
}

if ($DryRun) {
    Write-Output "[dry-run] Backup archive: $dumpPath"
    Write-Output "[dry-run] Manifest: $manifestPath (sha256 OK)"
    if ($vaultArchive) {
        Write-Output "[dry-run] Vault archive: $vaultArchive (sha256 OK)"
    }
    else {
        Write-Output "[dry-run] Vault archive: none (not in manifest or skipped)"
    }
    Write-Output "[dry-run] Staging database: $stageDatabase"
    Write-Output "[dry-run] docker cp $dumpPath ${ContainerName}:$containerDump"
    Write-Output "[dry-run] docker exec ${ContainerName} createdb --username jarvis $stageDatabase"
    Write-Output "[dry-run] docker exec ${ContainerName} pg_restore --exit-on-error --no-owner --no-privileges --username jarvis --dbname $stageDatabase $containerDump"
    Write-Output "[dry-run] Validation queries: table count, alembic_version, key-table row counts, status-enum preflight (expect 0 invalid rows)"
    Write-Output "[dry-run] docker exec ${ContainerName} dropdb --username jarvis --if-exists --force $stageDatabase"
    Write-Output "[dry-run] Complete. Nothing was executed."
    exit 0
}

$dockerAvailable = $false
try {
    docker inspect $ContainerName *> $null
    $dockerAvailable = ($LASTEXITCODE -eq 0)
}
catch {
    $dockerAvailable = $false
}
if (-not $dockerAvailable) {
    if ($Strict) {
        throw "PostgreSQL container is not running; cannot run the restore drill."
    }
    Write-Output "SKIPPED: PostgreSQL container not running (restore drill requires it)."
    Write-Output "Use -DryRun for planning or -Strict to fail instead of skipping."
    exit 0
}

try {
    docker cp $dumpPath "${ContainerName}:${containerDump}" *> $null
    Assert-DockerCommand "Copying backup into the container"

    docker exec $ContainerName createdb --username jarvis $stageDatabase
    Assert-DockerCommand "Creating drill staging database"

    docker exec $ContainerName pg_restore `
        --exit-on-error `
        --no-owner `
        --no-privileges `
        --username jarvis `
        --dbname $stageDatabase `
        $containerDump *> $null
    Assert-DockerCommand "Restoring backup into the drill staging database"

    $tableCount = (
        docker exec $ContainerName psql `
            --username jarvis `
            --dbname $stageDatabase `
            --tuples-only `
            --no-align `
            --command (
                "SELECT COUNT(*) FROM information_schema.tables " +
                "WHERE table_schema = 'public';"
            )
    ).Trim()
    Assert-DockerCommand "Counting restored tables"
    if ([int]$tableCount -lt 1) {
        throw "Drill restore produced no public tables."
    }

    $alembicVersion = (
        docker exec $ContainerName psql `
            --username jarvis `
            --dbname $stageDatabase `
            --tuples-only `
            --no-align `
            --command "SELECT version_num FROM alembic_version LIMIT 1;"
    ).Trim()
    Assert-DockerCommand "Reading restored schema version"

    $rowCounts = (
        docker exec $ContainerName psql `
            --username jarvis `
            --dbname $stageDatabase `
            --tuples-only `
            --no-align `
            --command (Get-ValidationSql)
    )
    Assert-DockerCommand "Reading key table row counts"

    $invalidStatus = (
        docker exec $ContainerName psql `
            --username jarvis `
            --dbname $stageDatabase `
            --tuples-only `
            --no-align `
            --command (Get-StatusPreflightSql)
    )
    Assert-DockerCommand "Running status-enum preflight"
    $invalidTotal = 0
    foreach ($line in @($invalidStatus)) {
        $parts = ($line -split "\|")
        if ($parts.Count -eq 2) {
            $invalidTotal += [int]$parts[1].Trim()
        }
    }
    if ($invalidTotal -ne 0) {
        throw "Status-enum preflight found $invalidTotal invalid rows in the restored backup."
    }

    Write-Output "Drill passed: $tableCount tables, schema $alembicVersion."
    foreach ($line in @($rowCounts)) {
        Write-Output "  $line"
    }
    Write-Output "Status-enum preflight: 0 invalid rows across 5 tables."
    if ($vaultArchive) {
        Write-Output "Vault archive checksum verified: $vaultArchive"
    }
}
finally {
    docker exec $ContainerName dropdb `
        --username jarvis `
        --if-exists `
        --force `
        $stageDatabase *> $null
    docker exec $ContainerName rm -f $containerDump *> $null
}
