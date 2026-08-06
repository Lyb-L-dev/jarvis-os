$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Failures = [System.Collections.Generic.List[string]]::new()
$Warnings = [System.Collections.Generic.List[string]]::new()
$Checks = [System.Collections.Generic.List[string]]::new()

function Add-Check {
    param(
        [bool]$Condition,
        [string]$Success,
        [string]$Failure
    )
    if ($Condition) {
        $Checks.Add($Success)
    }
    else {
        $Failures.Add($Failure)
    }
}

function Get-LocalEnvValue {
    param(
        [string]$Name,
        [string]$Default
    )

    $EnvPath = Join-Path $ProjectRoot ".env"
    if (-not (Test-Path -LiteralPath $EnvPath)) {
        return $Default
    }
    $Line = Get-Content -LiteralPath $EnvPath -Encoding UTF8 |
        Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s*=" } |
        Select-Object -Last 1
    if (-not $Line) {
        return $Default
    }
    $Value = ($Line -split "=", 2)[1].Trim()
    if (
        ($Value.StartsWith('"') -and $Value.EndsWith('"')) -or
        ($Value.StartsWith("'") -and $Value.EndsWith("'"))
    ) {
        return $Value.Substring(1, $Value.Length - 2)
    }
    return $Value
}

$GitIgnorePath = Join-Path $ProjectRoot ".gitignore"
$GitIgnore = if (Test-Path -LiteralPath $GitIgnorePath) {
    Get-Content -LiteralPath $GitIgnorePath -Raw -Encoding UTF8
}
else {
    ""
}
foreach ($RequiredRule in @(".env", "backups/", ".runtime/", "*.key", "*.pem")) {
    $RulePattern = "(?m)^" + [regex]::Escape($RequiredRule) + "\s*$"
    Add-Check `
        -Condition ($GitIgnore -match $RulePattern) `
        -Success ".gitignore protects $RequiredRule" `
        -Failure ".gitignore is missing required protection for $RequiredRule"
}

$Excluded = "\\(node_modules|\.next|\.venv|\.pytest_cache|__pycache__|\.runtime|backups|artifacts|tests)\\"
$Extensions = @(".py", ".ps1", ".ts", ".tsx", ".js", ".cjs", ".json", ".toml", ".md", ".yml", ".yaml", ".cmd")
$SecretPatterns = @(
    "(?i)\bsk-[A-Za-z0-9_-]{24,}\b",
    "(?i)\btp-[A-Za-z0-9_-]{24,}\b",
    "(?i)\bgithub_pat_[A-Za-z0-9_]{20,}\b",
    "(?i)\bghp_[A-Za-z0-9]{20,}\b",
    "(?i)\bxox[baprs]-[A-Za-z0-9-]{20,}\b",
    "(?i)\bAIza[0-9A-Za-z_-]{30,}\b",
    "-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
$SourceFiles = Get-ChildItem `
    -LiteralPath $ProjectRoot `
    -Recurse `
    -File `
    -ErrorAction SilentlyContinue |
    Where-Object {
        $_.FullName -notmatch $Excluded -and
        $_.Name -ne ".env" -and
        $Extensions -contains $_.Extension
    }
$SecretHits = [System.Collections.Generic.List[string]]::new()
foreach ($File in $SourceFiles) {
    $Content = Get-Content -LiteralPath $File.FullName -Raw -Encoding UTF8
    foreach ($Pattern in $SecretPatterns) {
        if ($Content -match $Pattern) {
            $RelativePath = [System.IO.Path]::GetRelativePath($ProjectRoot, $File.FullName)
            $SecretHits.Add($RelativePath)
            break
        }
    }
}
Add-Check `
    -Condition ($SecretHits.Count -eq 0) `
    -Success "No high-confidence API keys or private keys found in project source" `
    -Failure "Possible secret found in: $($SecretHits -join ', ')"

$ApiHost = Get-LocalEnvValue -Name "API_HOST" -Default "127.0.0.1"
Add-Check `
    -Condition ($ApiHost -in @("127.0.0.1", "localhost", "::1")) `
    -Success "API host is restricted to this computer" `
    -Failure "API_HOST must remain loopback-only"

$N8nIngress = Get-LocalEnvValue `
    -Name "N8N_INGRESS_URL" `
    -Default "http://127.0.0.1:5680"
$N8nIngressSafe = $false
try {
    $N8nUri = [Uri]$N8nIngress
    $N8nIngressSafe = (
        $N8nUri.Scheme -eq "http" -and
        $N8nUri.Host -in @("localhost", "127.0.0.1", "::1") -and
        [string]::IsNullOrEmpty($N8nUri.UserInfo) -and
        [string]::IsNullOrEmpty($N8nUri.Query) -and
        [string]::IsNullOrEmpty($N8nUri.Fragment)
    )
}
catch {
    $N8nIngressSafe = $false
}
Add-Check `
    -Condition $N8nIngressSafe `
    -Success "n8n ingress is credential-free and loopback-only" `
    -Failure "N8N_INGRESS_URL must remain a credential-free loopback HTTP URL"

$BrowserWorkerUrl = Get-LocalEnvValue `
    -Name "BROWSER_WORKER_URL" `
    -Default "http://127.0.0.1:5690"
$BrowserWorkerUrlSafe = $false
try {
    $BrowserUri = [Uri]$BrowserWorkerUrl
    $BrowserWorkerUrlSafe = (
        $BrowserUri.Scheme -eq "http" -and
        $BrowserUri.Host -in @("localhost", "127.0.0.1", "::1") -and
        [string]::IsNullOrEmpty($BrowserUri.UserInfo) -and
        [string]::IsNullOrEmpty($BrowserUri.Query) -and
        [string]::IsNullOrEmpty($BrowserUri.Fragment)
    )
}
catch {
    $BrowserWorkerUrlSafe = $false
}
Add-Check `
    -Condition $BrowserWorkerUrlSafe `
    -Success "Browser Worker is credential-free and loopback-only" `
    -Failure "BROWSER_WORKER_URL must remain a credential-free loopback HTTP URL"

$OpenClawEnabled = Get-LocalEnvValue -Name "OPENCLAW_ENABLED" -Default "false"
Add-Check `
    -Condition ($OpenClawEnabled -notmatch "^(?i:true|1|yes|on)$") `
    -Success "OpenClaw remains disabled" `
    -Failure "OPENCLAW_ENABLED must remain false until isolation review passes"

$Origins = Get-LocalEnvValue `
    -Name "WEB_ORIGINS" `
    -Default "http://localhost:3000,http://127.0.0.1:3000"
$UnsafeOrigins = @()
foreach ($Origin in ($Origins -split ",")) {
    try {
        $Uri = [Uri]$Origin.Trim()
        if ($Uri.Host -notin @("localhost", "127.0.0.1", "::1")) {
            $UnsafeOrigins += $Uri.Host
        }
    }
    catch {
        $UnsafeOrigins += "invalid-origin"
    }
}
Add-Check `
    -Condition ($UnsafeOrigins.Count -eq 0) `
    -Success "Browser access origins are loopback-only" `
    -Failure "WEB_ORIGINS contains a non-local or invalid origin"

foreach ($Port in @(3000, 5680, 5690, 8000)) {
    $Listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    $UnsafeListeners = @(
        $Listeners | Where-Object {
            $_.LocalAddress -notin @("127.0.0.1", "::1")
        }
    )
    Add-Check `
        -Condition ($UnsafeListeners.Count -eq 0) `
        -Success "Port $Port is not exposed beyond this computer" `
        -Failure "Port $Port is listening on a non-loopback address"
}

$BackupPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot "backups"))
$ExpectedBackupPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot "backups"))
Add-Check `
    -Condition ($BackupPath -eq $ExpectedBackupPath) `
    -Success "Backup path resolves to the expected project directory" `
    -Failure "Backup path resolution is unsafe"

$EnvPath = Join-Path $ProjectRoot ".env"
if (Test-Path -LiteralPath $EnvPath) {
    $Acl = Get-Acl -LiteralPath $EnvPath
    $BroadRead = @(
        $Acl.Access | Where-Object {
            $_.AccessControlType -eq "Allow" -and
            $_.IdentityReference.Value -match "(^|\\)(Everyone|Users|Authenticated Users)$" -and
            ($_.FileSystemRights.ToString() -match "Read|FullControl|Modify")
        }
    )
    if ($BroadRead.Count -gt 0) {
        $Warnings.Add(".env inherits broad local read permissions; do not use a shared Windows account.")
    }
    else {
        $Checks.Add(".env does not grant broad local read permissions")
    }
}

foreach ($Check in $Checks) {
    Write-Output "[PASS] $Check"
}
foreach ($Warning in $Warnings) {
    Write-Output "[WARN] $Warning"
}
foreach ($Failure in $Failures) {
    Write-Output "[FAIL] $Failure"
}

if ($Failures.Count -gt 0) {
    throw "Security check failed with $($Failures.Count) blocking issue(s)."
}

Write-Output "Security check passed with $($Warnings.Count) warning(s)."
