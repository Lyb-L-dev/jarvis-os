$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ModelFile = Join-Path $ProjectRoot "infra\ollama\JarvisMemory.Modelfile"
$SourceModel = "qwen3:4b-instruct-2507-q4_K_M"
$EmbeddingModel = "bge-m3:latest"
$ShadowModel = "jarvis-memory-qwen:latest"

if (-not (Test-Path -LiteralPath $ModelFile)) {
    throw "Jarvis Mem0 Modelfile is missing: $ModelFile"
}

& ollama show $SourceModel *> $null
if ($LASTEXITCODE -ne 0) {
    throw "The existing Qwen source model is missing. This script will not download it automatically."
}

& ollama show $EmbeddingModel *> $null
if ($LASTEXITCODE -ne 0) {
    throw "The local BGE-M3 embedding model is missing. This script will not download it automatically."
}

& ollama show $ShadowModel *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Output "Jarvis Mem0 shadow model is already ready: $ShadowModel"
    exit 0
}

& ollama create $ShadowModel -f $ModelFile
if ($LASTEXITCODE -ne 0) {
    throw "Creating the local Mem0 shadow model failed."
}

Write-Output "Jarvis Mem0 shadow model is ready: $ShadowModel"
