param()

$ErrorActionPreference = "Stop"

$DesktopRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $DesktopRoot "..\..")).Path
$Package = Get-Content -LiteralPath (Join-Path $DesktopRoot "package.json") `
    -Raw -Encoding UTF8 | ConvertFrom-Json
$StaticUi = Join-Path $ProjectRoot ".runtime\desktop-dist-ui-v4"
$Sidecar = Join-Path $DesktopRoot "resources\sidecar"
$ManifestPath = Join-Path $DesktopRoot "resources\release-manifest.json"

function Get-Sha256 {
    param([string]$Path)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        return (($sha.ComputeHash($stream) | ForEach-Object { $_.ToString("x2") }) -join "")
    }
    finally {
        $stream.Dispose()
        $sha.Dispose()
    }
}

function Get-TreeHash {
    param([string]$Root)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $resolvedRoot = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\') + '\'
        $lines = Get-ChildItem -LiteralPath $Root -Recurse -File |
            Sort-Object FullName |
            ForEach-Object {
                if (-not $_.FullName.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
                    throw "Release artifact escaped its declared root: $($_.FullName)"
                }
                $relative = $_.FullName.Substring($resolvedRoot.Length) -replace '\\','/'
                $hash = Get-Sha256 -Path $_.FullName
                "$relative`t$($_.Length)`t$hash`n"
            }
        $bytes = [System.Text.Encoding]::UTF8.GetBytes(($lines -join ""))
        return (($sha.ComputeHash($bytes) | ForEach-Object { $_.ToString("x2") }) -join "")
    }
    finally {
        $sha.Dispose()
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $StaticUi "chat\index.html"))) {
    throw "Static desktop UI must be prepared before generating the release manifest."
}
if (-not (Test-Path -LiteralPath (Join-Path $Sidecar "jarvis-sidecar.exe"))) {
    throw "Bundled Sidecar must be prepared before generating the release manifest."
}

$gitSha = (git -C $ProjectRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or -not $gitSha) {
    throw "Unable to resolve the release Git SHA."
}
$schemaRevision = Get-ChildItem -LiteralPath (Join-Path $ProjectRoot "apps\api\migrations\versions") `
    -Filter "*.py" -File |
    Sort-Object Name |
    Select-Object -ExpandProperty BaseName -Last 1
$channel = if ($env:JARVIS_RELEASE_CHANNEL) {
    $env:JARVIS_RELEASE_CHANNEL
}
else {
    "beta"
}
if ($channel -notin @("stable", "beta")) {
    throw "Release channel must be stable or beta."
}
$workingTreeDirty = -not [string]::IsNullOrWhiteSpace((git -C $ProjectRoot status --porcelain))
if ($channel -eq "stable" -and $workingTreeDirty) {
    throw "Stable release manifest requires a clean Git worktree."
}
$sbom = Join-Path $ProjectRoot ".runtime\release\jarvis-os-v4.cdx.json"
if (-not (Test-Path -LiteralPath $sbom -PathType Leaf)) {
    throw "CycloneDX SBOM must be generated before the release manifest."
}

$manifest = [ordered]@{
    schema_version = 2
    app_version = $Package.version
    git_sha = $gitSha
    web_build_id = (Get-TreeHash -Root $StaticUi).Substring(0, 20)
    core_version = "0.1.0"
    companion_version = "0.1.0"
    schema_revision = $schemaRevision
    target = "x86_64-pc-windows-msvc"
    build_time_utc = [DateTimeOffset]::UtcNow.ToString("o")
    channel = $channel
    working_tree_dirty = $workingTreeDirty
    update_manifest_signature = "rsa-pkcs1-sha256"
    windows_code_signing = if ($channel -eq "stable") { "required" } else { "required-for-publication" }
    artifacts = [ordered]@{
        static_ui_sha256 = Get-TreeHash -Root $StaticUi
        sidecar_sha256 = Get-TreeHash -Root $Sidecar
        runtime_scripts_sha256 = Get-TreeHash -Root (Join-Path $DesktopRoot "resources\scripts")
        installer_hooks_sha256 = Get-Sha256 -Path (Join-Path $DesktopRoot "src-tauri\windows\installer-hooks.nsh")
        sbom_sha256 = Get-Sha256 -Path $sbom
    }
}

[System.IO.File]::WriteAllText(
    $ManifestPath,
    ($manifest | ConvertTo-Json -Depth 6),
    [System.Text.UTF8Encoding]::new($false)
)
Write-Host "Generated release manifest at $ManifestPath"
