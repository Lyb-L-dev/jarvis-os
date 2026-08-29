param(
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$DesktopRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $DesktopRoot "..\..")).Path
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $ProjectRoot ".runtime\release\jarvis-os-v4.cdx.json"
}
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $resolvedOutput) | Out-Null

$components = [System.Collections.Generic.List[object]]::new()
function Add-Component {
    param([string]$Type, [string]$Name, [string]$Version, [string]$Scope, [string]$Purl)
    $components.Add([pscustomobject][ordered]@{
        type = $Type
        name = $Name
        version = $Version
        scope = $Scope
        purl = $Purl
    }) | Out-Null
}

$npmPackages = @(
    Join-Path $ProjectRoot "apps\web\package-lock.json"
    Join-Path $DesktopRoot "package-lock.json"
)
foreach ($lockPath in $npmPackages) {
    $rows = & node (Join-Path $PSScriptRoot "list-lock-packages.mjs") $lockPath
    if ($LASTEXITCODE -ne 0) { throw "Unable to parse npm lockfile: $lockPath" }
    foreach ($row in $rows) {
        $columns = $row -split "`t", 2
        if ($columns.Count -ne 2) { continue }
        $name = $columns[0]
        $version = $columns[1]
        $encoded = [Uri]::EscapeDataString($name).Replace("%2F", "/")
        Add-Component "library" $name $version "required" "pkg:npm/$encoded@$version"
    }
}

$cargoLock = Get-Content -LiteralPath (Join-Path $DesktopRoot "src-tauri\Cargo.lock") -Raw -Encoding UTF8
$cargoMatches = [regex]::Matches($cargoLock, '(?ms)^\[\[package\]\]\s+name = "([^"]+)"\s+version = "([^"]+)"')
foreach ($match in $cargoMatches) {
    Add-Component "library" $match.Groups[1].Value $match.Groups[2].Value "required" "pkg:cargo/$($match.Groups[1].Value)@$($match.Groups[2].Value)"
}

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $python) {
    $frozen = & $python -m pip list --format=json | ConvertFrom-Json
    foreach ($package in $frozen) {
        $normalized = ([string]$package.name).Replace("_", "-").ToLowerInvariant()
        Add-Component "library" ([string]$package.name) ([string]$package.version) "required" "pkg:pypi/$normalized@$($package.version)"
    }
}

$deduplicated = $components |
    Sort-Object purl -Unique
$document = [ordered]@{
    bomFormat = "CycloneDX"
    specVersion = "1.5"
    serialNumber = "urn:uuid:$([Guid]::NewGuid())"
    version = 1
    metadata = [ordered]@{
        timestamp = [DateTimeOffset]::UtcNow.ToString("o")
        component = [ordered]@{
            type = "application"
            name = "Jarvis OS"
            version = ((Get-Content -LiteralPath (Join-Path $DesktopRoot "package.json") -Raw -Encoding UTF8 | ConvertFrom-Json).version)
        }
        properties = @(
            [ordered]@{ name = "jarvis:git_sha"; value = (git -C $ProjectRoot rev-parse HEAD).Trim() }
            [ordered]@{ name = "jarvis:generators"; value = "npm package-lock + Cargo.lock + pip environment" }
        )
    }
    components = @($deduplicated)
}
[System.IO.File]::WriteAllText(
    $resolvedOutput,
    ($document | ConvertTo-Json -Depth 8),
    [System.Text.UTF8Encoding]::new($false)
)
Write-Host "Generated CycloneDX SBOM with $($deduplicated.Count) components at $resolvedOutput"
