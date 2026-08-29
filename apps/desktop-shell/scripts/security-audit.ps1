param(
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$DesktopRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $DesktopRoot "..\..")).Path
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $ProjectRoot ".runtime\release\audit"
}
$root = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $root | Out-Null
$summary = [ordered]@{
    schema_version = 1
    generated_at = [DateTimeOffset]::UtcNow.ToString("o")
    git_sha = (git -C $ProjectRoot rev-parse HEAD).Trim()
    npm = @()
    pip = $null
    cargo = $null
}
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$releaseBlocked = $false
$npmCache = Join-Path $root "npm-cache"
$pipAuditCache = Join-Path $root "pip-audit-cache"
New-Item -ItemType Directory -Force -Path $npmCache, $pipAuditCache | Out-Null

foreach ($app in @("apps\web", "apps\desktop-shell")) {
    Push-Location (Join-Path $ProjectRoot $app)
    try {
        $previousPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $output = & (Get-Command npm.cmd).Source audit --json --audit-level=high `
            --registry=https://registry.npmjs.org --cache=$npmCache 2>&1
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousPreference
        [System.IO.File]::WriteAllText(
            (Join-Path $root (($app -replace '[\\/]', '-') + "-npm-audit.json")),
            ($output -join "`n"),
            [System.Text.UTF8Encoding]::new($false)
        )
        $networkBlocked = ($output -join "`n") -match "EACCES|ENETUNREACH|ECONNREFUSED|audit endpoint returned an error"
        $summary.npm += [ordered]@{
            app = $app
            status = if ($exitCode -eq 0) { "passed" } elseif ($networkBlocked) { "blocked" } else { "failed" }
            exit_code = $exitCode
            blocker = if ($networkBlocked) { "audit registry is unreachable from this build host" } else { $null }
        }
        if ($exitCode -ne 0) { $releaseBlocked = $true }
    }
    finally { Pop-Location }
}

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $python) {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $pipCheck = & $python -m pip check 2>&1
    $pipCheckExitCode = $LASTEXITCODE
    $pipAudit = & $python -m pip_audit --progress-spinner off --format json `
        --vulnerability-service osv --timeout 60 --cache-dir $pipAuditCache 2>&1
    $pipAuditExitCode = $LASTEXITCODE
    [System.IO.File]::WriteAllText(
        (Join-Path $root "pip-audit.json"),
        ($pipAudit -join "`n"),
        [System.Text.UTF8Encoding]::new($false)
    )
    $summary.pip = [ordered]@{
        check_exit_code = $pipCheckExitCode
        check_output = ($pipCheck -join "`n")
        audit_exit_code = $pipAuditExitCode
    }
    if ($pipCheckExitCode -ne 0 -or $pipAuditExitCode -ne 0) { $releaseBlocked = $true }
    $ErrorActionPreference = $previousPreference
}

$cargoAudit = Get-Command cargo-audit.exe -ErrorAction SilentlyContinue
if (-not $cargoAudit) {
    $workspaceCargoAudit = Join-Path $ProjectRoot ".runtime\cargo-audit\bin\cargo-audit.exe"
    if (Test-Path -LiteralPath $workspaceCargoAudit) {
        $cargoAudit = Get-Item -LiteralPath $workspaceCargoAudit
    }
}
if ($cargoAudit) {
    $cargoAuditPath = if ($cargoAudit.Source) { $cargoAudit.Source } else { $cargoAudit.FullName }
    $cargoArguments = @(
        "audit",
        "--file", (Join-Path $DesktopRoot "src-tauri\Cargo.lock"),
        "--target-os", "windows",
        "--target-arch", "x86_64",
        "--json"
    )
    if ($env:JARVIS_RUSTSEC_ADVISORY_DB) {
        $advisoryDatabase = [System.IO.Path]::GetFullPath($env:JARVIS_RUSTSEC_ADVISORY_DB)
        if (-not (Test-Path -LiteralPath (Join-Path $advisoryDatabase "crates"))) {
            throw "JARVIS_RUSTSEC_ADVISORY_DB does not contain a RustSec crates directory."
        }
        $cargoArguments += @("--db", $advisoryDatabase, "--no-fetch", "--stale")
    }
    $cargoOutput = & $cargoAuditPath @cargoArguments 2>&1
    $summary.cargo = [ordered]@{ available = $true; exit_code = $LASTEXITCODE }
    if ($LASTEXITCODE -ne 0) { $releaseBlocked = $true }
    [System.IO.File]::WriteAllText(
        (Join-Path $root "cargo-audit.json"),
        ($cargoOutput -join "`n"),
        [System.Text.UTF8Encoding]::new($false)
    )
}
else {
    $summary.cargo = [ordered]@{ available = $false; exit_code = $null; blocker = "cargo-audit is not installed on this build host" }
    $releaseBlocked = $true
}

[System.IO.File]::WriteAllText(
    (Join-Path $root "summary.json"),
    ($summary | ConvertTo-Json -Depth 6),
    [System.Text.UTF8Encoding]::new($false)
)
Write-Host "Security audit evidence written to $root"
if ($releaseBlocked) {
    throw "Security audit did not pass. Inspect $root before publication."
}
