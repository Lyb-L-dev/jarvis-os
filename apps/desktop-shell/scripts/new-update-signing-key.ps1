param(
    [string]$KeyId = "jarvis-v4-development-2026",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Security

$DesktopRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $DesktopRoot "..\..")).Path
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $ProjectRoot ".runtime\release-signing"
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

$rsa = [System.Security.Cryptography.RSA]::Create(3072)
try {
    $parameters = $rsa.ExportParameters($true)
    $privateBytes = [System.Text.Encoding]::UTF8.GetBytes($rsa.ToXmlString($true))
    try {
        $protected = [System.Security.Cryptography.ProtectedData]::Protect(
            $privateBytes,
            [System.Text.Encoding]::UTF8.GetBytes("Jarvis OS update signing key v1"),
            [System.Security.Cryptography.DataProtectionScope]::CurrentUser
        )
        $privateDocument = [ordered]@{
            schema_version = 1
            key_id = $KeyId
            protection = "windows-dpapi-current-user"
            protected_rsa_xml_base64 = [Convert]::ToBase64String($protected)
        }
        $publicDocument = [ordered]@{
            schema_version = 1
            key_id = $KeyId
            algorithm = "rsa-pkcs1-sha256"
            modulus_base64 = [Convert]::ToBase64String($parameters.Modulus)
            exponent_base64 = [Convert]::ToBase64String($parameters.Exponent)
            development_key = $KeyId.Contains("development")
        }
        $utf8 = [System.Text.UTF8Encoding]::new($false)
        [System.IO.File]::WriteAllText(
            (Join-Path $OutputRoot "private-key.dpapi.json"),
            ($privateDocument | ConvertTo-Json -Depth 4),
            $utf8
        )
        [System.IO.File]::WriteAllText(
            (Join-Path $OutputRoot "public-key.json"),
            ($publicDocument | ConvertTo-Json -Depth 4),
            $utf8
        )
    }
    finally {
        [Array]::Clear($privateBytes, 0, $privateBytes.Length)
    }
}
finally {
    $rsa.Dispose()
}

Write-Host "Generated a DPAPI-protected signing key under $OutputRoot"
Write-Host "Keep private-key.dpapi.json outside Git. Only public-key.json may be committed."
