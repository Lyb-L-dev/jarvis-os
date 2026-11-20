$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VoiceRoot = Join-Path $ProjectRoot ".data\voice"

function Assert-LastCommand {
    param([string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

function Install-VoiceModel {
    param(
        [string]$DisplayName,
        [string]$ModelName,
        [string]$Release = "tts-models",
        [string[]]$ExpectedPaths,
        [string]$RuntimeLink
    )

    $ModelPath = Join-Path $VoiceRoot $ModelName
    $ArchivePath = Join-Path $VoiceRoot "$ModelName.tar.bz2"
    $ModelUrl = "https://github.com/k2-fsa/sherpa-onnx/releases/download/$Release/$ModelName.tar.bz2"
    $ModelReady = $true
    foreach ($RelativePath in $ExpectedPaths) {
        if (-not (Test-Path -LiteralPath (Join-Path $ModelPath $RelativePath))) {
            $ModelReady = $false
            break
        }
    }

    if (-not $ModelReady) {
        Write-Host "Downloading the offline $DisplayName voice model..."
        Invoke-WebRequest -UseBasicParsing -Uri $ModelUrl -OutFile $ArchivePath

        Write-Host "Extracting the $DisplayName voice model..."
        tar -xjf $ArchivePath -C $VoiceRoot
        Assert-LastCommand "Extracting the offline $DisplayName voice model"

        $ResolvedVoiceRoot = (Resolve-Path -LiteralPath $VoiceRoot).Path
        $ResolvedModelPath = (Resolve-Path -LiteralPath $ModelPath).Path
        if (
            -not $ResolvedModelPath.StartsWith(
                $ResolvedVoiceRoot,
                [StringComparison]::OrdinalIgnoreCase
            )
        ) {
            throw "Extracted voice model path is outside the expected Jarvis data directory."
        }

        foreach ($RelativePath in $ExpectedPaths) {
            $ExpectedPath = Join-Path $ResolvedModelPath $RelativePath
            if (-not (Test-Path -LiteralPath $ExpectedPath)) {
                throw "$DisplayName voice model is incomplete: $RelativePath is missing."
            }
        }

        Remove-Item -LiteralPath $ArchivePath -Force
    }

    New-Item -ItemType Directory -Path (Split-Path -Parent $RuntimeLink) -Force |
        Out-Null
    if (Test-Path -LiteralPath $RuntimeLink) {
        $ExistingLink = Get-Item -LiteralPath $RuntimeLink -Force
        $LinkTarget = @($ExistingLink.Target)[0]
        if (
            $ExistingLink.LinkType -ne "Junction" -or
            -not [String]::Equals(
                [String]$LinkTarget,
                [String](Resolve-Path -LiteralPath $ModelPath).Path,
                [StringComparison]::OrdinalIgnoreCase
            )
        ) {
            throw "$RuntimeLink exists but is not the expected Jarvis model link."
        }
    }
    else {
        New-Item -ItemType Junction -Path $RuntimeLink -Target $ModelPath |
            Out-Null
    }
}

if (-not (Test-Path -LiteralPath $PythonPath)) {
    throw "Jarvis Python environment is missing. Run scripts\setup.ps1 first."
}

New-Item -ItemType Directory -Path $VoiceRoot -Force | Out-Null

Write-Host "Checking the local speech runtime..."
& $PythonPath -c "import sherpa_onnx"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing the local speech runtime..."
    & $PythonPath -m pip install "sherpa-onnx>=1.13.4,<2" "sherpa-onnx-bin>=1.13.4,<2"
    Assert-LastCommand "Installing local speech runtime"
}

Install-VoiceModel `
    -DisplayName "Chinese male" `
    -ModelName "vits-zh-hf-fanchen-wnj" `
    -ExpectedPaths @(
        "vits-zh-hf-fanchen-wnj.onnx",
        "lexicon.txt",
        "tokens.txt",
        "number.fst",
        "date.fst"
    ) `
    -RuntimeLink "C:\tmp\jarvis-voice-model"

Install-VoiceModel `
    -DisplayName "English male" `
    -ModelName "vits-piper-en_US-hfc_male-medium" `
    -ExpectedPaths @(
        "en_US-hfc_male-medium.onnx",
        "tokens.txt",
        "espeak-ng-data"
    ) `
    -RuntimeLink "C:\tmp\jarvis-voice-en-model"

Install-VoiceModel `
    -DisplayName "Chinese-English streaming speech recognition" `
    -ModelName "sherpa-onnx-streaming-zipformer-small-bilingual-zh-en-2023-02-16" `
    -Release "asr-models" `
    -ExpectedPaths @(
        "encoder-epoch-99-avg-1.int8.onnx",
        "decoder-epoch-99-avg-1.onnx",
        "joiner-epoch-99-avg-1.int8.onnx",
        "tokens.txt"
    ) `
    -RuntimeLink "C:\tmp\jarvis-stt-model"

Write-Host "Jarvis bilingual offline speech models are ready."
