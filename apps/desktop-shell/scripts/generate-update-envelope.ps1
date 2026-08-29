param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,
    [Parameter(Mandatory = $true)]
    [ValidateSet("stable", "beta")]
    [string]$Channel,
    [Parameter(Mandatory = $true)]
    [string]$PackageUrl,
    [Parameter(Mandatory = $true)]
    [string]$SigningKeyPath,
    [string]$ReleaseNotes = "Jarvis OS desktop update.",
    [string]$OutputPath = "",
    [string]$MinimumAppVersion = "4.0.0-beta.1"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Security

$DesktopRoot = Split-Path -Parent $PSScriptRoot
$Package = Get-Content -LiteralPath (Join-Path $DesktopRoot "package.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$installer = (Resolve-Path -LiteralPath $InstallerPath).Path
$keyPath = (Resolve-Path -LiteralPath $SigningKeyPath).Path
if (-not $PackageUrl.StartsWith("https://", [StringComparison]::OrdinalIgnoreCase)) {
    throw "Update package URL must use HTTPS."
}
if ($ReleaseNotes.Length -lt 1 -or $ReleaseNotes.Length -gt 12000) {
    throw "Release notes must contain 1-12000 characters."
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path (Split-Path -Parent $installer) "$Channel-update.json"
}

$privateDocument = Get-Content -LiteralPath $keyPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($privateDocument.schema_version -ne 1 -or $privateDocument.protection -ne "windows-dpapi-current-user") {
    throw "Unsupported update signing key format."
}
$publicPath = Join-Path (Split-Path -Parent $keyPath) "public-key.json"
if (-not (Test-Path -LiteralPath $publicPath -PathType Leaf)) {
    throw "The matching public-key.json is required beside the private key."
}
$publicDocument = Get-Content -LiteralPath $publicPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($publicDocument.key_id -ne $privateDocument.key_id) {
    throw "Public and private update key IDs do not match."
}
if ($Channel -eq "stable" -and $publicDocument.development_key) {
    throw "A development update key cannot sign the Stable channel."
}

$signatureStatus = Get-AuthenticodeSignature -LiteralPath $installer
$authenticodeRequired = $signatureStatus.Status -eq [System.Management.Automation.SignatureStatus]::Valid
if ($Channel -eq "stable" -and -not $authenticodeRequired) {
    throw "The Stable installer must have a valid Windows Authenticode signature."
}

$payload = [ordered]@{
    manifest_version = 1
    channel = $Channel
    app_version = $Package.version
    target = "x86_64-pc-windows-msvc"
    published_at = [DateTimeOffset]::UtcNow.ToString("o")
    release_notes = $ReleaseNotes
    requires_restart = $true
    package = [ordered]@{
        url = $PackageUrl
        file_name = [System.IO.Path]::GetFileName($installer)
        size_bytes = (Get-Item -LiteralPath $installer).Length
        sha256 = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
        authenticode_required = $authenticodeRequired
    }
    compatibility = [ordered]@{
        minimum_app_version = $MinimumAppVersion
        database_migration_strategy = "expand-migrate-contract"
        binary_rollback_compatible = $true
    }
}
$payloadJson = $payload | ConvertTo-Json -Depth 8 -Compress
$payloadBytes = [System.Text.Encoding]::UTF8.GetBytes($payloadJson)
$protectedBytes = [Convert]::FromBase64String($privateDocument.protected_rsa_xml_base64)
$privateBytes = [System.Security.Cryptography.ProtectedData]::Unprotect(
    $protectedBytes,
    [System.Text.Encoding]::UTF8.GetBytes("Jarvis OS update signing key v1"),
    [System.Security.Cryptography.DataProtectionScope]::CurrentUser
)
$rsa = [System.Security.Cryptography.RSA]::Create()
try {
    $rsa.FromXmlString([System.Text.Encoding]::UTF8.GetString($privateBytes))
    $signature = $rsa.SignData(
        $payloadBytes,
        [System.Security.Cryptography.HashAlgorithmName]::SHA256,
        [System.Security.Cryptography.RSASignaturePadding]::Pkcs1
    )
}
finally {
    $rsa.Dispose()
    [Array]::Clear($privateBytes, 0, $privateBytes.Length)
}

$envelope = [ordered]@{
    schema_version = 1
    key_id = $privateDocument.key_id
    payload_base64 = [Convert]::ToBase64String($payloadBytes)
    signature_base64 = [Convert]::ToBase64String($signature)
}
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $resolvedOutput) | Out-Null
[System.IO.File]::WriteAllText(
    $resolvedOutput,
    ($envelope | ConvertTo-Json -Depth 4),
    [System.Text.UTF8Encoding]::new($false)
)
Write-Host "Generated signed $Channel update envelope at $resolvedOutput"
Write-Host "Installer Authenticode required: $authenticodeRequired"
