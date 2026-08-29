param(
    [Parameter(Mandatory = $true)][string]$InstallerPath,
    [Parameter(Mandatory = $true)][string]$SbomPath,
    [Parameter(Mandatory = $true)][string]$SecuritySummaryPath,
    [Parameter(Mandatory = $true)][string]$ObservationEvidencePath,
    [switch]$AllowBetaUnsigned
)

$ErrorActionPreference = "Stop"
$desktopRoot = Split-Path -Parent $PSScriptRoot
$projectRoot = (Resolve-Path (Join-Path $desktopRoot "..\..")).Path
$manifestPath = Join-Path $desktopRoot "resources\release-manifest.json"
$publicKeyPath = Join-Path $desktopRoot "src-tauri\update-public-key.json"
foreach ($path in @($InstallerPath, $SbomPath, $SecuritySummaryPath, $ObservationEvidencePath, $manifestPath, $publicKeyPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Release evidence is missing: $path" }
}
$manifest = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$security = Get-Content $SecuritySummaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$publicKey = Get-Content $publicKeyPath -Raw -Encoding UTF8 | ConvertFrom-Json
$observation = Get-Content $ObservationEvidencePath -Raw -Encoding UTF8 | ConvertFrom-Json
$failures = [Collections.Generic.List[string]]::new()

function Get-Sha256([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return (($sha.ComputeHash($stream) | ForEach-Object { $_.ToString("x2") }) -join "") }
    finally { $stream.Dispose(); $sha.Dispose() }
}

$signature = Get-AuthenticodeSignature -LiteralPath $InstallerPath
$installerSha256 = Get-Sha256 $InstallerPath
$manifestSha256 = Get-Sha256 $manifestPath
if (-not $AllowBetaUnsigned -and $signature.Status -ne "Valid") { $failures.Add("installer Authenticode signature is not valid") }
if (-not $AllowBetaUnsigned -and $publicKey.development_key) { $failures.Add("development update public key is still embedded") }
if ($manifest.working_tree_dirty) { $failures.Add("release manifest was generated from a dirty worktree") }
if ($observation.schema_version -ne 2 -or $observation.installer_sha256 -ne $installerSha256) {
    $failures.Add("observation evidence is not bound to this exact installer")
}
if ($observation.release_manifest_sha256 -ne $manifestSha256) {
    $failures.Add("observation evidence is not bound to this release manifest")
}
if ($manifest.artifacts.sbom_sha256 -ne (Get-Sha256 $SbomPath)) {
    $failures.Add("SBOM hash does not match release manifest")
}
if (@($security.npm | Where-Object { $_.status -ne "passed" }).Count -gt 0) { $failures.Add("npm audit evidence did not pass") }
if ($security.pip.check_exit_code -ne 0 -or $security.pip.audit_exit_code -ne 0) { $failures.Add("Python audit evidence did not pass") }
if (-not $security.cargo.available -or $security.cargo.exit_code -ne 0) { $failures.Add("Cargo audit evidence did not pass") }
if (([DateTimeOffset]::UtcNow - [DateTimeOffset]::Parse($observation.started_at)) -lt [TimeSpan]::FromHours(168)) {
    $failures.Add("seven-day observation window has not elapsed")
}
if (@($observation.samples).Count -lt 134) { $failures.Add("seven-day observation sample coverage is incomplete") }
if (@($observation.samples).Count -eq 0 -or
    $null -eq $observation.samples[-1].reliability_metrics -or
    $observation.samples[-1].reliability_metrics.events_total -lt 1) {
    $failures.Add("privacy-safe product reliability metrics are missing")
}
if ($observation.app_version -ne $manifest.app_version -or
    @($observation.samples | Where-Object { $_.installed_version -ne $manifest.app_version }).Count -gt 0) {
    $failures.Add("observation evidence does not prove the release version")
}
if (@($observation.samples | Where-Object { [string]::IsNullOrWhiteSpace([string]$_.installed_exe_sha256) }).Count -gt 0 -or
    @($observation.samples.installed_exe_sha256 | Sort-Object -Unique).Count -ne 1) {
    $failures.Add("observation samples do not prove one immutable installed executable")
}
if (@($observation.samples | Where-Object { $_.installed_manifest_sha256 -ne $manifestSha256 }).Count -gt 0) {
    $failures.Add("observation samples do not match the current release manifest")
}
if (@($observation.samples | Where-Object { $_.issue_severity -in @("p0", "p1") }).Count -gt 0) {
    $failures.Add("P0/P1 issue exists in observation evidence")
}
if ((git -C $projectRoot status --porcelain).Count -gt 0) { $failures.Add("current worktree is dirty") }

[ordered]@{
    passed = $failures.Count -eq 0
    version = $manifest.app_version
    installer_sha256 = $installerSha256
    signature = $signature.Status.ToString()
    failures = @($failures)
} | ConvertTo-Json -Depth 4
if ($failures.Count -gt 0) { exit 1 }
