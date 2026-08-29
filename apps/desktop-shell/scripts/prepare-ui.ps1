param(
    [switch]$SkipWebBuild
)

$ErrorActionPreference = "Stop"

$DesktopRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $DesktopRoot "..\..")).Path
$WebRoot = Join-Path $ProjectRoot "apps\web"
$SplashSource = Join-Path $DesktopRoot "src-ui"
$DesktopAssets = Join-Path $ProjectRoot ".runtime\desktop-dist-ui-v4"
$WebExport = $null

if (-not $SkipWebBuild) {
    # Next opens <project>/.next/trace before it resolves distDir. A stale or
    # antivirus-owned cache can therefore block release builds even when the
    # actual export directory is different. Build from a fresh, workspace-local
    # root and reuse only the reviewed dependency tree.
    $BuildRoot = Join-Path $ProjectRoot (".runtime\web-build-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $BuildRoot | Out-Null
    foreach ($File in @("package.json", "package-lock.json", "next.config.ts", "tsconfig.json", "postcss.config.mjs")) {
        Copy-Item -LiteralPath (Join-Path $WebRoot $File) -Destination $BuildRoot
    }
    Copy-Item -LiteralPath (Join-Path $WebRoot "src") -Destination $BuildRoot -Recurse
    if (Test-Path -LiteralPath (Join-Path $WebRoot "public")) {
        Copy-Item -LiteralPath (Join-Path $WebRoot "public") -Destination $BuildRoot -Recurse
    }
    New-Item -ItemType Junction `
        -Path (Join-Path $BuildRoot "node_modules") `
        -Target (Resolve-Path (Join-Path $WebRoot "node_modules")).Path | Out-Null
    $WebExport = Join-Path $BuildRoot ".next-v4-export"
    Push-Location $BuildRoot
    try {
        $previousStaticExport = $env:JARVIS_STATIC_EXPORT
        $previousDistDirectory = $env:JARVIS_NEXT_DIST_DIR
        $env:JARVIS_STATIC_EXPORT = "1"
        $env:JARVIS_NEXT_DIST_DIR = ".next-v4-export"
        & (Join-Path $BuildRoot "node_modules\.bin\next.cmd") build $BuildRoot --webpack
        if ($LASTEXITCODE -ne 0) {
            throw "Static Jarvis interface build failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        $env:JARVIS_STATIC_EXPORT = $previousStaticExport
        $env:JARVIS_NEXT_DIST_DIR = $previousDistDirectory
        Pop-Location
    }
}
else {
    $PreparedExport = Get-ChildItem -LiteralPath (Join-Path $ProjectRoot ".runtime") `
        -Directory -Filter "web-build-*" |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName ".next-v4-export\chat\index.html") } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($PreparedExport) {
        $WebExport = Join-Path $PreparedExport.FullName ".next-v4-export"
    }
}

if (-not $WebExport -or -not (Test-Path -LiteralPath (Join-Path $WebExport "chat\index.html"))) {
    throw "The static Jarvis interface is missing. Run this script without -SkipWebBuild first."
}
if (-not (Test-Path -LiteralPath (Join-Path $SplashSource "index.html"))) {
    throw "The desktop startup interface is missing."
}

$StagedAssets = Join-Path $ProjectRoot (".runtime\desktop-dist-ui-stage-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $StagedAssets | Out-Null
Copy-Item -Path (Join-Path $WebExport "*") -Destination $StagedAssets -Recurse -Force

$SplashDestination = Join-Path $StagedAssets "splash"
New-Item -ItemType Directory -Path $SplashDestination | Out-Null
Copy-Item -Path (Join-Path $SplashSource "*") -Destination $SplashDestination -Recurse -Force

if (-not (Test-Path -LiteralPath $DesktopAssets)) {
    New-Item -ItemType Directory -Path $DesktopAssets | Out-Null
}
& robocopy.exe $StagedAssets $DesktopAssets /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) {
    throw "Mirroring desktop assets failed with robocopy exit code $LASTEXITCODE."
}
$global:LASTEXITCODE = 0

Write-Host "Prepared Jarvis desktop assets at $DesktopAssets"
