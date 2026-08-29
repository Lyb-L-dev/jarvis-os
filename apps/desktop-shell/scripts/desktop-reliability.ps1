param(
    [ValidateSet("All", "Lifecycle", "Quick", "Measure")]
    [string]$Mode = "All",
    [ValidateRange(1, 200)]
    [int]$LifecycleIterations = 50,
    [ValidateRange(1, 100)]
    [int]$QuickIterations = 20,
    [string]$Executable = "",
    [string]$EvidencePath = "",
    [ValidateSet("bundled", "source")]
    [string]$RuntimeMode = "bundled",
    [string]$ProjectRoot = "",
    [ValidateRange(5, 120)]
    [int]$ReadyTimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"
$processName = "jarvis-os-desktop-shell"
$sidecarNames = @("jarvis-sidecar", "jarvis-companion")
$utf8 = [Text.UTF8Encoding]::new($false)

if ([string]::IsNullOrWhiteSpace($Executable)) {
    if (-not $env:LOCALAPPDATA) { throw "LOCALAPPDATA is unavailable." }
    $Executable = Join-Path $env:LOCALAPPDATA "Programs\Jarvis OS\jarvis-os-desktop-shell.exe"
}
$Executable = [IO.Path]::GetFullPath($Executable)
if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
    throw "Jarvis executable does not exist: $Executable"
}
if ($RuntimeMode -eq "source") {
    if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
        $ProjectRoot = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $PSScriptRoot) "..\.."))
    }
    $ProjectRoot = [IO.Path]::GetFullPath($ProjectRoot)
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "scripts\start.ps1") -PathType Leaf)) {
        throw "Source runtime project root is invalid: $ProjectRoot"
    }
    $env:JARVIS_PROJECT_ROOT = $ProjectRoot
}
if ([string]::IsNullOrWhiteSpace($EvidencePath)) {
    $evidenceRoot = Join-Path (Split-Path -Parent $PSScriptRoot) "..\..\.runtime\release-evidence"
    $evidenceRoot = [IO.Path]::GetFullPath($evidenceRoot)
    New-Item -ItemType Directory -Force -Path $evidenceRoot | Out-Null
    $EvidencePath = Join-Path $evidenceRoot "desktop-reliability.json"
}
$EvidencePath = [IO.Path]::GetFullPath($EvidencePath)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $EvidencePath) | Out-Null

if (-not ("JarvisWindowProbe" -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class JarvisWindowProbe {
  private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);
  [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] private static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll")] private static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
  public static string[] VisibleTitles(uint expectedProcessId) {
    var titles = new List<string>();
    EnumWindows((window, state) => {
      uint processId;
      GetWindowThreadProcessId(window, out processId);
      if (processId != expectedProcessId || !IsWindowVisible(window)) return true;
      var length = GetWindowTextLength(window);
      if (length <= 0) return true;
      var text = new StringBuilder(length + 1);
      GetWindowText(window, text, text.Capacity);
      titles.Add(text.ToString());
      return true;
    }, IntPtr.Zero);
    return titles.ToArray();
  }
  public static string WaitForUniqueTitle(uint expectedProcessId, string marker, int timeoutMilliseconds) {
    var watch = System.Diagnostics.Stopwatch.StartNew();
    while (watch.ElapsedMilliseconds < timeoutMilliseconds) {
      var matches = new List<string>();
      foreach (var title in VisibleTitles(expectedProcessId)) {
        if (title.IndexOf(marker, StringComparison.OrdinalIgnoreCase) >= 0) matches.Add(title);
      }
      if (matches.Count == 1) return matches[0];
      System.Threading.Thread.Sleep(10);
    }
    return null;
  }
}
'@
}

function Get-JarvisProcesses {
    @(Get-Process -Name $processName -ErrorAction SilentlyContinue)
}

function Get-VisibleTitles([Diagnostics.Process]$Process) {
    $titles = @([JarvisWindowProbe]::VisibleTitles([uint32]$Process.Id))
    $Process.Refresh()
    if (-not [string]::IsNullOrWhiteSpace($Process.MainWindowTitle)) {
        $titles += $Process.MainWindowTitle
    }
    @($titles | Select-Object -Unique)
}

function Wait-Until([scriptblock]$Condition, [int]$TimeoutMilliseconds) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while ($watch.ElapsedMilliseconds -lt $TimeoutMilliseconds) {
        $value = & $Condition
        if ($value) { return $value }
        Start-Sleep -Milliseconds 50
    }
    return $null
}

function Test-TcpPort([int]$Port) {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        return $task.Wait(250) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Test-RuntimeRecord([string]$ServicePath) {
    if (-not (Test-Path -LiteralPath $ServicePath -PathType Leaf)) { return $false }
    try {
        $record = Get-Content -LiteralPath $ServicePath -Raw -Encoding UTF8 | ConvertFrom-Json
        $apiPid = [int]$record.api_pid
        $api = Get-Process -Id $apiPid -ErrorAction Stop
        if ($api.ProcessName -notin @("python", "jarvis-sidecar")) { return $false }
        $port = if ($record.PSObject.Properties["api_port"]) { [int]$record.api_port } else { 8000 }
        return Test-TcpPort $port
    }
    catch {
        return $false
    }
}

function Get-Percentile([double[]]$Values, [double]$Percentile) {
    if ($Values.Count -eq 0) { return $null }
    $sorted = @($Values | Sort-Object)
    $index = [Math]::Ceiling(($Percentile / 100.0) * $sorted.Count) - 1
    $index = [Math]::Max(0, [Math]::Min($sorted.Count - 1, $index))
    [Math]::Round([double]$sorted[$index], 1)
}

function Stop-JarvisAndVerify([int]$Iteration) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $quit = Start-Process -FilePath $Executable -ArgumentList "--quit" -PassThru
    $quitTimeout = 30000
    if (-not $quit.WaitForExit($quitTimeout)) {
        throw "Iteration ${Iteration}: maintenance --quit process did not exit."
    }
    $stopped = Wait-Until { (Get-JarvisProcesses).Count -eq 0 } 20000
    if (-not $stopped) {
        throw "Iteration ${Iteration}: Jarvis app process remained after full exit."
    }
    foreach ($name in $sidecarNames) {
        if (@(Get-Process -Name $name -ErrorAction SilentlyContinue).Count -gt 0) {
            throw "Iteration ${Iteration}: orphan sidecar remained: $name"
        }
    }
    [Math]::Round($watch.Elapsed.TotalMilliseconds, 1)
}

function Start-JarvisAndMeasure([int]$Iteration) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $started = Start-Process -FilePath $Executable -PassThru
    $process = Wait-Until {
        @(Get-JarvisProcesses | Where-Object Id -EQ $started.Id | Select-Object -First 1)
    } 1000
    if (-not $process) {
        throw "Iteration ${Iteration}: no measurable native process feedback within one second."
    }
    $processFeedbackMs = [Math]::Round($watch.Elapsed.TotalMilliseconds, 1)
    if ($processFeedbackMs -gt 1000) {
        Stop-JarvisAndVerify $Iteration | Out-Null
        throw "Iteration ${Iteration}: end-to-end native process feedback exceeded one second ($processFeedbackMs ms)."
    }
    $window = Wait-Until {
        $titles = Get-VisibleTitles $started
        if ($titles.Count -gt 0) { $titles } else { $null }
    } 5000
    if (-not $window) {
        throw "Iteration ${Iteration}: native startup window was not visible within five seconds."
    }
    [ordered]@{
        process_id = $started.Id
        process_feedback_ms = $processFeedbackMs
        visible_window_ms = [Math]::Round($watch.Elapsed.TotalMilliseconds, 1)
        visible_titles = @($window)
    }
}

$existing = Get-JarvisProcesses
if ($existing.Count -gt 0) {
    throw "Reliability evidence requires an isolated run. Fully exit Jarvis before running this script."
}

$lifecycle = @()
if ($Mode -in @("All", "Lifecycle")) {
    for ($index = 1; $index -le $LifecycleIterations; $index += 1) {
        $startup = Start-JarvisAndMeasure $index
        Start-Sleep -Milliseconds 1000
        $processCount = (Get-JarvisProcesses).Count
        if ($processCount -ne 1) {
            throw "Iteration ${index}: expected one app process, observed $processCount."
        }
        $quitMs = Stop-JarvisAndVerify $index
        $lifecycle += [ordered]@{
            iteration = $index
            process_feedback_ms = $startup.process_feedback_ms
            visible_window_ms = $startup.visible_window_ms
            quit_ms = $quitMs
            visible_titles = $startup.visible_titles
            orphan_processes = 0
        }
    }
}

$quick = @()
$resourceSamples = @()
$hostProcess = $null
if ($Mode -in @("All", "Quick", "Measure")) {
    $hostStartup = Start-JarvisAndMeasure 0
    $hostProcess = Get-Process -Id $hostStartup.process_id -ErrorAction Stop
    $runtimeReady = Wait-Until {
        $servicePath = if ($RuntimeMode -eq "source") {
            Join-Path $ProjectRoot ".runtime\services.json"
        } else {
            Join-Path $env:LOCALAPPDATA "Jarvis OS\runtime\services.json"
        }
        Test-RuntimeRecord $servicePath
    } ($ReadyTimeoutSeconds * 1000)
    if ($runtimeReady) {
        $runtimeReady = Wait-Until {
            $hostProcess.Refresh()
            $hostProcess.MainWindowTitle -eq "Jarvis OS"
        } 10000
    }
    if ($Mode -in @("All", "Quick") -and -not $runtimeReady) {
        Stop-JarvisAndVerify 0 | Out-Null
        throw "Jarvis runtime and main workspace did not become ready within the allowed startup window; quick-window evidence was not fabricated."
    }
    if ($Mode -in @("All", "Quick")) {
        for ($index = 1; $index -le $QuickIterations; $index += 1) {
            $watch = [Diagnostics.Stopwatch]::StartNew()
            $activation = Start-Process -FilePath $Executable -ArgumentList "--quick" -PassThru
            if (-not $activation.WaitForExit(5000)) {
                Stop-JarvisAndVerify 0 | Out-Null
                throw "Quick iteration ${index}: secondary activation did not exit."
            }
            $remainingMs = [Math]::Max(1, 1500 - [int]$watch.ElapsedMilliseconds)
            $hostProcessId = [uint32]$hostProcess.Id
            $quickMarker = -join ([char[]]@(0x5FEB, 0x901F, 0x63D0, 0x95EE))
            $quickTitle = [JarvisWindowProbe]::WaitForUniqueTitle($hostProcessId, $quickMarker, [int]$remainingMs)
            $activationMs = [Math]::Round($watch.Elapsed.TotalMilliseconds, 1)
            if (-not $quickTitle) {
                $observedTitles = @(Get-VisibleTitles $hostProcess)
                $observedSummary = if ($observedTitles.Count -gt 0) {
                    $observedTitles -join " | "
                } else {
                    "<none>"
                }
                Stop-JarvisAndVerify 0 | Out-Null
                throw "Quick iteration ${index}: unique quick window was not visible within 1.5 seconds. Observed titles: $observedSummary"
            }
            if ((Get-JarvisProcesses).Count -ne 1) {
                Stop-JarvisAndVerify 0 | Out-Null
                throw "Quick iteration ${index}: activation created a second app process."
            }
            $quick += [ordered]@{
                iteration = $index
                activation_ms = $activationMs
                window_count = 1
            }
        }
    }
    if ($Mode -in @("All", "Measure")) {
        for ($index = 1; $index -le 20; $index += 1) {
            $appProcesses = @(Get-JarvisProcesses)
            $sidecarProcesses = @($sidecarNames | ForEach-Object {
                Get-Process -Name $_ -ErrorAction SilentlyContinue
            })
            $owned = @($appProcesses) + @($sidecarProcesses)
            $resourceSamples += [ordered]@{
                observed_at = [DateTimeOffset]::UtcNow.ToString("o")
                process_count = $owned.Count
                working_set_bytes = [long](($owned | Measure-Object WorkingSet64 -Sum).Sum)
                cpu_seconds = [Math]::Round([double](($owned | Measure-Object CPU -Sum).Sum), 3)
            }
            Start-Sleep -Milliseconds 250
        }
    }
    Stop-JarvisAndVerify 0 | Out-Null
}

$installRoot = Split-Path -Parent $Executable
$installFiles = @(Get-ChildItem -LiteralPath $installRoot -File -Recurse -ErrorAction Stop)
$feedbackValues = @($lifecycle | ForEach-Object { [double]$_.process_feedback_ms })
$visibleWindowValues = @($lifecycle | ForEach-Object { [double]$_.visible_window_ms })
$quitValues = @($lifecycle | ForEach-Object { [double]$_.quit_ms })
$quickValues = @($quick | ForEach-Object { [double]$_.activation_ms })
$workingSetValues = @($resourceSamples | ForEach-Object { [double]$_.working_set_bytes })
$result = [ordered]@{
    schema_version = 1
    generated_at = [DateTimeOffset]::UtcNow.ToString("o")
    executable = $Executable
    executable_sha256 = (Get-FileHash -LiteralPath $Executable -Algorithm SHA256).Hash
    product_version = (Get-Item -LiteralPath $Executable).VersionInfo.ProductVersion
    os = [Environment]::OSVersion.VersionString
    mode = $Mode
    runtime_mode = $RuntimeMode
    project_root = if ($RuntimeMode -eq "source") { $ProjectRoot } else { $null }
    thresholds = [ordered]@{
        native_feedback_ms = 1000
        quick_window_ms = 1500
        lifecycle_iterations = $LifecycleIterations
        quick_iterations = $QuickIterations
    }
    lifecycle = [ordered]@{
        passed = ($Mode -notin @("All", "Lifecycle")) -or $lifecycle.Count -eq $LifecycleIterations
        iterations = $lifecycle
        process_feedback_p50_ms = Get-Percentile $feedbackValues 50
        process_feedback_p95_ms = Get-Percentile $feedbackValues 95
        visible_window_p50_ms = Get-Percentile $visibleWindowValues 50
        visible_window_p95_ms = Get-Percentile $visibleWindowValues 95
        quit_p95_ms = Get-Percentile $quitValues 95
    }
    quick_window = [ordered]@{
        passed = ($Mode -notin @("All", "Quick")) -or $quick.Count -eq $QuickIterations
        iterations = $quick
        activation_p50_ms = Get-Percentile $quickValues 50
        activation_p95_ms = Get-Percentile $quickValues 95
    }
    resources = [ordered]@{
        install_bytes = [long](($installFiles | Measure-Object Length -Sum).Sum)
        install_files = $installFiles.Count
        idle_working_set_p50_bytes = Get-Percentile $workingSetValues 50
        idle_working_set_p95_bytes = Get-Percentile $workingSetValues 95
        samples = $resourceSamples
    }
    privacy = "Contains timings, process counts, paths, hashes, and resource totals only; no prompts, tokens, file contents, or voice data."
}
[IO.File]::WriteAllText($EvidencePath, ($result | ConvertTo-Json -Depth 10), $utf8)
$result | ConvertTo-Json -Depth 6
Write-Host "Desktop reliability evidence: $EvidencePath"
