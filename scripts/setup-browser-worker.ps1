$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SecretDirectory = Join-Path $ProjectRoot ".data\browser-secrets"
$SecretPath = Join-Path $SecretDirectory "webhook_secret"
$OutputDirectory = Join-Path $ProjectRoot ".data\browser-research"
$EdgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$WorkerPath = Join-Path $ProjectRoot "apps\browser-worker\server.cjs"

if (-not (Test-Path -LiteralPath $EdgePath)) {
    throw "Microsoft Edge was not found at the expected system path."
}
if (-not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
    throw "Node.js is required for the isolated Browser Worker."
}
if (-not (Test-Path -LiteralPath $WorkerPath)) {
    throw "Browser Worker source is missing."
}

New-Item -ItemType Directory -Path $SecretDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

if (-not (Test-Path -LiteralPath $SecretPath)) {
    $Generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $Bytes = New-Object byte[] 48
        $Generator.GetBytes($Bytes)
        $Secret = [Convert]::ToBase64String($Bytes)
        [System.IO.File]::WriteAllText(
            $SecretPath,
            $Secret,
            [System.Text.UTF8Encoding]::new($false)
        )
    }
    finally {
        $Generator.Dispose()
    }
    Write-Host "Created a new local Browser Worker signing secret."
}
else {
    Write-Host "Existing Browser Worker signing secret was kept unchanged."
}

Write-Host "Browser Worker prerequisites are ready."
Write-Host "No website account, browser profile, resume, or external credential was configured."
