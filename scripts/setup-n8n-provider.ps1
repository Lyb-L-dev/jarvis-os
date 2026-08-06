param(
    [switch]$Start
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SecretsDirectory = Join-Path $ProjectRoot ".data\n8n-secrets"
$EncryptionKeyPath = Join-Path $SecretsDirectory "n8n_encryption_key"
$WebhookSecretPath = Join-Path $SecretsDirectory "webhook_secret"
$OwnerPasswordPath = Join-Path $SecretsDirectory "n8n_owner_password"
$ComposeFile = Join-Path $ProjectRoot "infra\docker-compose.yml"
$Image = "docker.n8n.io/n8nio/n8n:1.123.5"

function New-SecretFile {
    param(
        [string]$Path,
        [int]$ByteCount
    )

    if (Test-Path -LiteralPath $Path) {
        return
    }
    $bytes = [byte[]]::new($ByteCount)
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    $value = [Convert]::ToBase64String($bytes)
    [System.IO.File]::WriteAllText(
        $Path,
        $value,
        [System.Text.UTF8Encoding]::new($false)
    )
}

New-Item -ItemType Directory -Path $SecretsDirectory -Force | Out-Null
New-SecretFile -Path $EncryptionKeyPath -ByteCount 48
New-SecretFile -Path $WebhookSecretPath -ByteCount 48
New-SecretFile -Path $OwnerPasswordPath -ByteCount 48

docker image inspect $Image *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Pinned n8n image is not installed: $Image"
}

docker compose -f $ComposeFile --profile automation config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Jarvis n8n compose configuration is invalid."
}

Write-Output "Jarvis n8n secrets and isolated deployment are configured."
Write-Output "Existing container named 'n8n' was not changed."

if ($Start) {
    docker compose -f $ComposeFile --profile automation up -d n8n n8n-ingress
    if ($LASTEXITCODE -ne 0) {
        throw "Starting Jarvis n8n Provider failed."
    }
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $response = Invoke-WebRequest `
                -UseBasicParsing `
                -Uri "http://127.0.0.1:5680/healthz" `
                -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                Write-Output "Jarvis n8n Provider is ready on signed ingress port 5680."
                exit 0
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "Jarvis n8n Provider did not become ready."
}
