param(
    [ValidateSet("dev", "bundle", "build", "release", "test", "check", "run")]
    [string]$Task = "test"
)

$ErrorActionPreference = "Stop"

$DesktopRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $DesktopRoot "..\..")).Path
$ManifestPath = Join-Path $DesktopRoot "src-tauri\Cargo.toml"
$VsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"

if (-not (Test-Path -LiteralPath $VsWhere)) {
    throw "Visual Studio Build Tools discovery is unavailable. Install VS 2022 C++ Build Tools."
}

$VsInstallPath = & $VsWhere -latest -products * `
    -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
    -property installationPath
if (-not $VsInstallPath) {
    throw "VS 2022 C++ Build Tools were not found."
}

$MsvcRoot = Get-ChildItem -LiteralPath (Join-Path $VsInstallPath "VC\Tools\MSVC") `
    -Directory |
    Sort-Object Name -Descending |
    Select-Object -First 1
if (-not $MsvcRoot) {
    throw "The MSVC x64 toolchain was not found."
}

$SdkRegistry = Get-ItemProperty `
    -LiteralPath "HKLM:\SOFTWARE\Microsoft\Windows Kits\Installed Roots" `
    -ErrorAction SilentlyContinue
$SdkRoot = $SdkRegistry.KitsRoot10
if (-not $SdkRoot) {
    $SdkRoot = "${env:ProgramFiles(x86)}\Windows Kits\10\"
}
$SdkVersion = Get-ChildItem -LiteralPath (Join-Path $SdkRoot "Lib") `
    -Directory |
    Where-Object Name -Match '^10\.' |
    Sort-Object Name -Descending |
    Select-Object -ExpandProperty Name -First 1
if (-not $SdkVersion) {
    throw "The Windows 10/11 SDK was not found."
}

$Cargo = Get-Command cargo.exe -ErrorAction SilentlyContinue
if (-not $Cargo) {
    $CargoFallback = Join-Path $env:USERPROFILE ".cargo\bin\cargo.exe"
    if (-not (Test-Path -LiteralPath $CargoFallback)) {
        throw "Rust Cargo was not found."
    }
    $CargoPath = $CargoFallback
}
else {
    $CargoPath = $Cargo.Source
}

$TempDirectory = Join-Path $ProjectRoot ".runtime\desktop-build-temp"
New-Item -ItemType Directory -Force -Path $TempDirectory | Out-Null
$env:TEMP = $TempDirectory
$env:TMP = $TempDirectory
$env:CARGO_TARGET_DIR = if ($env:JARVIS_CARGO_TARGET_DIR) {
    $env:JARVIS_CARGO_TARGET_DIR
}
else {
    Join-Path $ProjectRoot ".runtime\desktop-target-v4"
}
$env:CARGO_BUILD_JOBS = if ($env:JARVIS_CARGO_BUILD_JOBS) {
    $env:JARVIS_CARGO_BUILD_JOBS
}
else {
    "1"
}
$env:VCToolsInstallDir = $MsvcRoot.FullName + "\"
$env:VCINSTALLDIR = (Join-Path $VsInstallPath "VC") + "\"
$env:WindowsSdkDir = $SdkRoot
$env:WindowsSDKVersion = $SdkVersion + "\"
$env:UCRTVersion = $SdkVersion
$env:RC_x86_64_pc_windows_msvc = Join-Path $SdkRoot "bin\$SdkVersion\x64\rc.exe"
if ($Task -in @("test", "check")) {
    $env:JARVIS_SKIP_TAURI_BUILD = "1"
}
$env:INCLUDE = @(
    (Join-Path $MsvcRoot.FullName "include"),
    (Join-Path $SdkRoot "Include\$SdkVersion\ucrt"),
    (Join-Path $SdkRoot "Include\$SdkVersion\shared"),
    (Join-Path $SdkRoot "Include\$SdkVersion\um"),
    (Join-Path $SdkRoot "Include\$SdkVersion\winrt"),
    (Join-Path $SdkRoot "Include\$SdkVersion\cppwinrt")
) -join ";"
$env:LIB = @(
    (Join-Path $MsvcRoot.FullName "lib\x64"),
    (Join-Path $SdkRoot "Lib\$SdkVersion\ucrt\x64"),
    (Join-Path $SdkRoot "Lib\$SdkVersion\um\x64")
) -join ";"
$env:LIBPATH = $env:LIB

$PathEntries = @(
    (Join-Path $MsvcRoot.FullName "bin\Hostx64\x64"),
    (Join-Path $SdkRoot "bin\$SdkVersion\x64"),
    (Split-Path -Parent $CargoPath)
)
$CurrentPath = [Environment]::GetEnvironmentVariable("Path", "Process")
$env:Path = ($PathEntries + $CurrentPath) -join ";"

Push-Location $DesktopRoot
try {
    switch ($Task) {
        "dev" {
            & (Join-Path $DesktopRoot "node_modules\.bin\tauri.cmd") dev
        }
        "bundle" {
            $TauriArguments = @("build")
            if ($env:JARVIS_WINDOWS_CERTIFICATE_THUMBPRINT) {
                if (-not $env:JARVIS_WINDOWS_TIMESTAMP_URL) {
                    throw "JARVIS_WINDOWS_TIMESTAMP_URL is required when code signing is enabled."
                }
                $SigningConfigPath = Join-Path $TempDirectory "tauri-signing-config.json"
                @{
                    bundle = @{
                        windows = @{
                            certificateThumbprint = $env:JARVIS_WINDOWS_CERTIFICATE_THUMBPRINT
                            digestAlgorithm = "sha256"
                            timestampUrl = $env:JARVIS_WINDOWS_TIMESTAMP_URL
                        }
                    }
                } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $SigningConfigPath -Encoding UTF8
                $TauriArguments += @("--config", $SigningConfigPath)
            }
            & (Join-Path $DesktopRoot "node_modules\.bin\tauri.cmd") @TauriArguments
            if ($LASTEXITCODE -eq 0) {
                $Installers = Get-ChildItem -LiteralPath (Join-Path $env:CARGO_TARGET_DIR "release\bundle\nsis") `
                    -Filter "*-setup.exe" -ErrorAction SilentlyContinue
                foreach ($Installer in $Installers) {
                    $Signature = Get-AuthenticodeSignature -LiteralPath $Installer.FullName
                    if ($Signature.Status -ne "Valid") {
                        Write-Warning "Unsigned development installer created: $($Installer.FullName). Stable publication remains blocked."
                    }
                }
            }
        }
        "release" {
            & $CargoPath build --release --manifest-path $ManifestPath
        }
        default {
            & $CargoPath $Task --manifest-path $ManifestPath
        }
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Desktop native task '$Task' failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
