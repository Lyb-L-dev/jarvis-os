param(
    [ValidateSet("Start", "Sample", "Verify")]
    [string]$Mode = "Sample",
    [ValidateSet("normal", "sleep", "resume")]
    [string]$Event = "normal",
    [ValidateSet("none", "p0", "p1")]
    [string]$IssueSeverity = "none",
    [string]$IssueNote = "",
    [ValidateSet(24, 168)]
    [int]$RequiredHours = 168,
    [string]$InstallerPath = "",
    [string]$EvidenceDirectory = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($EvidenceDirectory)) {
    if (-not $env:LOCALAPPDATA) { throw "LOCALAPPDATA is unavailable." }
    $EvidenceDirectory = Join-Path $env:LOCALAPPDATA "Jarvis OS\observations\v4-beta.3-current"
}
$root = [IO.Path]::GetFullPath($EvidenceDirectory)
$statePath = Join-Path $root "observation.json"
$utf8 = [Text.UTF8Encoding]::new($false)
$desktopRoot = Split-Path -Parent $PSScriptRoot
$releaseManifestPath = Join-Path $desktopRoot "resources\release-manifest.json"

function Get-Sha256([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return (($sha.ComputeHash($stream) | ForEach-Object { $_.ToString("x2") }) -join "") }
    finally { $stream.Dispose(); $sha.Dispose() }
}

function Write-State([object]$State) {
    $temporary = "$statePath.partial"
    [IO.File]::WriteAllText($temporary, ($State | ConvertTo-Json -Depth 8), $utf8)
    Move-Item -LiteralPath $temporary -Destination $statePath -Force
}

$reliabilityKinds = @(
    "startup", "startup_stage", "quick_open", "quick_send", "quick_continue",
    "notification_open", "notification_snooze", "file_preview", "file_confirm",
    "file_reject", "file_analyze", "voice_permission", "voice_model",
    "voice_transcription", "supervisor_restart", "supervisor_state", "update_check",
    "update_download", "update_install", "update_rollback", "diagnostic_export"
)

function Get-ReliabilitySummary([DateTimeOffset]$Since) {
    $ledgerRoot = Join-Path $env:LOCALAPPDATA "Jarvis OS\observations"
    $events = @(
        Get-ChildItem -LiteralPath $ledgerRoot -File -Filter "desktop-reliability.jsonl*" -ErrorAction SilentlyContinue |
            Sort-Object Name |
            ForEach-Object { Get-Content -LiteralPath $_.FullName -Encoding UTF8 -ErrorAction SilentlyContinue } |
            ForEach-Object {
                try { $_ | ConvertFrom-Json } catch { $null }
            } |
            Where-Object {
                $null -ne $_ -and
                $_.schema_version -eq 1 -and
                $_.app_version -eq $state.app_version -and
                [DateTimeOffset]::FromUnixTimeMilliseconds([int64]$_.observed_at_ms) -ge $Since
            }
    )
    $updateResults = @(
        Get-ChildItem -LiteralPath (Join-Path $env:LOCALAPPDATA "Jarvis OS\updates\transactions") `
            -Recurse -File -Filter "result.json" -ErrorAction SilentlyContinue |
            ForEach-Object {
                try { Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $null }
            } |
            Where-Object {
                $null -ne $_ -and
                $_.schema_version -eq 1 -and
                $_.target_version -eq $state.app_version -and
                [DateTimeOffset]::FromUnixTimeMilliseconds([int64]$_.finished_at_ms) -ge $Since
            }
    )
    foreach ($result in $updateResults) {
        $kind = if ($result.status -in @("rolled_back", "rollback_failed")) { "update_rollback" } else { "update_install" }
        $outcome = if ($result.status -in @("updated", "rolled_back")) { "succeeded" } else { "failed" }
        $events += [pscustomobject]@{
            schema_version = 1
            observed_at_ms = [long]$result.finished_at_ms
            app_version = $state.app_version
            kind = $kind
            outcome = $outcome
            duration_ms = $null
            stage = $null
        }
    }
    $byKind = foreach ($kind in $reliabilityKinds) {
        $matching = @($events | Where-Object kind -EQ $kind)
        $durations = @($matching | Where-Object { $null -ne $_.duration_ms } | ForEach-Object { [long]$_.duration_ms } | Sort-Object)
        $p95 = if ($durations.Count -gt 0) {
            $durations[[Math]::Min($durations.Count - 1, [Math]::Ceiling($durations.Count * 0.95) - 1)]
        } else { $null }
        [ordered]@{
            kind = $kind
            attempted = @($matching | Where-Object outcome -EQ "attempted").Count
            succeeded = @($matching | Where-Object outcome -EQ "succeeded").Count
            failed = @($matching | Where-Object outcome -EQ "failed").Count
            cancelled = @($matching | Where-Object outcome -EQ "cancelled").Count
            degraded = @($matching | Where-Object outcome -EQ "degraded").Count
            blocked = @($matching | Where-Object outcome -EQ "blocked").Count
            not_configured = @($matching | Where-Object outcome -EQ "not_configured").Count
            duration_p95_ms = $p95
        }
    }
    $stages = foreach ($stage in @("preflight", "database", "migration", "core", "companion", "interface")) {
        $durations = @(
            $events |
                Where-Object { $_.kind -eq "startup_stage" -and $_.stage -eq $stage -and $null -ne $_.duration_ms } |
                ForEach-Object { [long]$_.duration_ms } |
                Sort-Object
        )
        [ordered]@{
            stage = $stage
            samples = $durations.Count
            time_to_stage_p95_ms = if ($durations.Count -gt 0) {
                $durations[[Math]::Min($durations.Count - 1, [Math]::Ceiling($durations.Count * 0.95) - 1)]
            } else { $null }
        }
    }
    return [ordered]@{
        schema_version = 1
        since = $Since.ToString("o")
        events_total = $events.Count
        by_kind = @($byKind)
        startup_stages = @($stages)
        privacy = "Closed event kinds, outcomes and timings only; no message, file or voice content."
    }
}

if ($Mode -eq "Start") {
    if ((Test-Path -LiteralPath $statePath) -and -not $Force) {
        throw "Observation evidence already exists. Use -Force only to begin a new, explicit window."
    }
    if ([string]::IsNullOrWhiteSpace($InstallerPath) -or -not (Test-Path -LiteralPath $InstallerPath -PathType Leaf)) {
        throw "Start requires -InstallerPath for the exact release artifact under observation."
    }
    if (-not (Test-Path -LiteralPath $releaseManifestPath -PathType Leaf)) {
        throw "Release manifest is missing: $releaseManifestPath"
    }
    New-Item -ItemType Directory -Force -Path $root | Out-Null
    $state = [ordered]@{
        schema_version = 2
        app_version = "4.0.0-beta.3"
        installer_sha256 = Get-Sha256 $InstallerPath
        release_manifest_sha256 = Get-Sha256 $releaseManifestPath
        started_at = [DateTimeOffset]::UtcNow.ToString("o")
        required_hours = $RequiredHours
        privacy = "No prompts, file contents, tokens, cookies, or voice data are recorded."
        samples = @()
    }
    Write-State $state
    Write-Host "Started $RequiredHours-hour observation at $statePath"
    exit 0
}

if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
    throw "Observation has not started. Run this script with -Mode Start first."
}
$state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($state.schema_version -ne 2) { throw "Unsupported observation evidence version; start a new window for the exact release artifact." }

if ($Mode -eq "Sample") {
    $jarvis = @(Get-Process -Name "jarvis-os-desktop-shell" -ErrorAction SilentlyContinue)
    $sidecars = @(Get-Process -Name "jarvis-sidecar" -ErrorAction SilentlyContinue)
    if ($jarvis.Count -ne 1) { throw "A valid observation sample requires exactly one running Jarvis App process." }
    if ($sidecars.Count -lt 1 -or $sidecars.Count -gt 2) { throw "A valid observation sample requires one or two owned Sidecar processes." }
    $dataRoot = Join-Path $env:LOCALAPPDATA "Jarvis OS"
    $logBytes = if (Test-Path (Join-Path $dataRoot "logs")) {
        (Get-ChildItem (Join-Path $dataRoot "logs") -File -Recurse -ErrorAction SilentlyContinue |
            Measure-Object Length -Sum).Sum
    } else { 0 }
    $version = $null
    $uninstallRoot = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall"
    if (Test-Path -LiteralPath $uninstallRoot) {
        $entry = Get-ChildItem -LiteralPath $uninstallRoot -ErrorAction SilentlyContinue |
            ForEach-Object { Get-ItemProperty -LiteralPath $_.PSPath -ErrorAction SilentlyContinue } |
            Where-Object DisplayName -EQ "Jarvis OS" |
            Select-Object -First 1
        if ($entry) { $version = [string]$entry.DisplayVersion }
    }
    if ([string]::IsNullOrWhiteSpace($version)) {
        $installedExe = if ($jarvis.Count -gt 0) { [string]$jarvis[0].Path } else { $null }
        if ([string]::IsNullOrWhiteSpace($installedExe)) {
            $installedExe = Join-Path $env:LOCALAPPDATA "Programs\Jarvis OS\jarvis-os-desktop-shell.exe"
        }
        if (Test-Path -LiteralPath $installedExe) {
            $version = [string](Get-Item -LiteralPath $installedExe).VersionInfo.ProductVersion
        }
    }
    if ([string]::IsNullOrWhiteSpace($version)) { $version = $null }
    $installedExe = Join-Path $env:LOCALAPPDATA "Programs\Jarvis OS\jarvis-os-desktop-shell.exe"
    $installedManifest = Join-Path $env:LOCALAPPDATA "Programs\Jarvis OS\resources\release-manifest.json"
    $sample = [ordered]@{
        observed_at = [DateTimeOffset]::UtcNow.ToString("o")
        event = $Event
        installed_version = $version
        installed_exe_sha256 = if (Test-Path -LiteralPath $installedExe -PathType Leaf) { Get-Sha256 $installedExe } else { $null }
        installed_manifest_sha256 = if (Test-Path -LiteralPath $installedManifest -PathType Leaf) { Get-Sha256 $installedManifest } else { $null }
        app_process_count = $jarvis.Count
        sidecar_process_count = $sidecars.Count
        log_bytes = [long]$(if ($null -eq $logBytes) { 0 } else { $logBytes })
        issue_severity = $IssueSeverity
        issue_note = if ($IssueSeverity -eq "none") { $null } else { $IssueNote }
        reliability_metrics = Get-ReliabilitySummary ([DateTimeOffset]::Parse($state.started_at))
    }
    $state.samples = @($state.samples) + @($sample)
    Write-State $state
    $sample | ConvertTo-Json
    exit 0
}

$started = [DateTimeOffset]::Parse($state.started_at)
$elapsedHours = ([DateTimeOffset]::UtcNow - $started).TotalHours
$minimumSamples = [Math]::Max(2, [Math]::Floor([int]$state.required_hours * 0.8))
$samples = @($state.samples)
$hourBuckets = @(
    $samples |
        ForEach-Object {
            try {
                [int][Math]::Floor(([DateTimeOffset]::Parse([string]$_.observed_at) - $started).TotalHours)
            } catch {
                -1
            }
        } |
        Where-Object { $_ -ge 0 -and $_ -lt [int]$state.required_hours } |
        Sort-Object -Unique
)
$coveredHourBuckets = $hourBuckets.Count
$failures = [Collections.Generic.List[string]]::new()
if ($elapsedHours -lt [int]$state.required_hours) { $failures.Add("required time window has not elapsed") }
if ($coveredHourBuckets -lt $minimumSamples) { $failures.Add("distinct hourly sample coverage is below 80% of the observation window") }
if (@($samples | Where-Object { [string]::IsNullOrWhiteSpace([string]$_.installed_version) -or $_.installed_version -ne $state.app_version }).Count -gt 0) {
    $failures.Add("one or more samples do not prove the observed app version")
}
if (@($samples | Where-Object { [string]::IsNullOrWhiteSpace([string]$_.installed_exe_sha256) }).Count -gt 0 -or
    @($samples.installed_exe_sha256 | Sort-Object -Unique).Count -ne 1) {
    $failures.Add("samples do not prove one immutable installed executable")
}
if (@($samples | Where-Object { $_.installed_manifest_sha256 -ne $state.release_manifest_sha256 }).Count -gt 0) {
    $failures.Add("one or more samples do not match the observed release manifest")
}
if (@($samples | Where-Object { $_.app_process_count -ne 1 }).Count -gt 0) { $failures.Add("sample does not prove exactly one running app process") }
if (@($samples | Where-Object { $_.sidecar_process_count -lt 1 -or $_.sidecar_process_count -gt 2 }).Count -gt 0) { $failures.Add("sample does not prove the owned Sidecar process budget") }
if ($samples.Count -eq 0 -or $null -eq $samples[-1].reliability_metrics -or $samples[-1].reliability_metrics.events_total -lt 1) {
    $failures.Add("privacy-safe product reliability metrics were not captured")
}
if (@($samples | Where-Object { $_.issue_severity -in @("p0", "p1") }).Count -gt 0) { $failures.Add("P0/P1 issue recorded") }
if ([int]$state.required_hours -ge 24 -and @($samples | Where-Object { $_.event -eq "resume" }).Count -lt 2) {
    $failures.Add("fewer than two resume samples were recorded")
}
$result = [ordered]@{
    passed = $failures.Count -eq 0
    elapsed_hours = [Math]::Round($elapsedHours, 2)
    required_hours = [int]$state.required_hours
    samples = $samples.Count
    covered_hour_buckets = $coveredHourBuckets
    required_samples = $minimumSamples
    failures = @($failures)
    evidence = $statePath
}
$result | ConvertTo-Json -Depth 4
if ($failures.Count -gt 0) { exit 1 }
