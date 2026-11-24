# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = "",
    [string]$startTime = (Get-Date).ToString("o"),
    [string]$modelTier = "portable",
    [string]$lane = "eager",
    [string]$quant = "none",
    [string]$shape = "short",
    [switch]$noGpu = $false
)

# 9F0F6E2E-8D06-4D2F-B8F5-6F1F2D5A1C01 is a custom provider we use to emit phase markers from the scenario script (optional, may not be present)
if (-not ('HoblRunPhaseProvider' -as [type])) {
    Add-Type -TypeDefinition @"
using System.Diagnostics.Tracing;

[EventSource(Name = "HOBL-Scenario-Phases", Guid = "9f0f6e2e-8d06-4d2f-b8f5-6f1f2d5a1c01")]
public sealed class HoblRunPhaseProvider : EventSource
{
    public static readonly HoblRunPhaseProvider Log = new HoblRunPhaseProvider();

    [Event(1, Level = EventLevel.Informational)]
    public void Phase(string marker, string scenario)
    {
        WriteEvent(1, marker, scenario);
    }
}
"@
}

function Write-RunPhaseMarker {
    param([string]$Marker)

    try {
        [HoblRunPhaseProvider]::Log.Phase($Marker, "pytorch_inf_v2")
    } catch {
    }
}

$scriptDrive = Split-Path -Qualifier $PSScriptRoot

if (-not (Test-Path "$scriptDrive\hobl_data")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_data" -ForegroundColor Red
    Exit 1
}
if (-not (Test-Path "$scriptDrive\hobl_bin")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_bin" -ForegroundColor Red
    Exit 1
}

if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\pytorch_inf_v2_run.log" }

$timeTraceFile = "$scriptDrive\hobl_data\run_time.trace"
$totalTokenTraceFile = "$scriptDrive\hobl_data\total_tokens.trace"
$tpsTraceFile = "$scriptDrive\hobl_data\tokens_per_second.trace"

function log {
    [CmdletBinding()] Param([Parameter(ValueFromPipeline)] $msg)
    process {
        if ($msg -Match " ERROR - ") {
            Write-Host $msg -ForegroundColor Red
        } else {
            Write-Host $msg
        }
        Add-Content -Path $logFile -encoding utf8 "$msg"
    }
}

function check {
    param($code)
    if ($code -ne 0) {
        " ERROR - Last command failed." | log
        Exit $code
    }
}

function checkCmd {
    param($code)
    if ($code -ne "True") {
        " ERROR - Last command failed." | log
        Exit 1
    }
}

Set-Content -Path $logFile -encoding utf8 "-- pytorch_inf_v2 run started"
"-- pytorch_inf_v2 run started (model_tier=$modelTier lane=$lane quant=$quant shape=$shape no_gpu=$noGpu)" | log
Write-RunPhaseMarker "phase.run_prep.start"

$osInfo = Get-CimInstance Win32_OperatingSystem
$arch = $osInfo.OSArchitecture
$processorArch = $env:PROCESSOR_ARCHITECTURE

if ($arch -eq "64-bit" -and $processorArch -eq "AMD64") {
    $pythonVersion = "3.14.8"
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    $pythonVersion = "3.14.8-arm"
} else {
    " ERROR - Unsupported architecture: $arch (Processor: $processorArch)" | log
    Exit 1
}

# --- Ensure CUDA paths are in session PATH if available ---
if ($env:CUDA_PATH -and (Test-Path $env:CUDA_PATH)) {
    $cudaBin = Join-Path $env:CUDA_PATH "bin"
    if ($env:PATH -notlike "*$cudaBin*") {
        $env:PATH = "$cudaBin;$env:PATH"
        "Added CUDA bin to session PATH: $cudaBin" | log
    }
}

foreach ($cmd in @('pyenv', 'python')) {
    $resolved = Get-Command $cmd -ErrorAction SilentlyContinue
    if (-not $resolved) {
        " ERROR - Required command '$cmd' not found on PATH." | log
        " ERROR - Prep may not have completed, or the RPC service has a stale PATH." | log
        Exit 1
    }
}

"Setting Python global version to $pythonVersion..." | log
pyenv global $pythonVersion
if ($LASTEXITCODE -ne 0) {
    " ERROR - Failed to set Python version $pythonVersion. Make sure it's installed via pyenv." | log
    "Run the pytorch_inf_v2 prep script first to install the correct Python version." | log
    Exit 1
}

"-- CD to resources" | log
Set-Location "$scriptDrive\hobl_bin\pytorch_inf_v2_resources"
checkCmd($?)

# --- Validate per-scenario venv and required imports ---
# Prep stages all Python packages into a private venv under this scenario's
# resource directory. We invoke that venv's python.exe by absolute path to
# bypass any pyenv/PATH instability caused by other scenarios. If the venv
# is missing or an expected package is not importable (e.g. an external tool
# quarantined a DLL), we fail fast with a clear diagnostic instead of a
# cryptic ModuleNotFoundError partway through the workload.
$venvPython = "$scriptDrive\hobl_bin\pytorch_inf_v2_resources\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    " ERROR - pytorch_inf_v2 venv missing at $venvPython" | log
    " ERROR - Prep state is corrupt. Re-prep required:" | log
    " ERROR -   delete C:\hobl_bin\prep_status\pytorch_inf_v2<version> on the DUT and re-run." | log
    Exit 1
}
"Using venv python: $venvPython" | log

"Validating venv has required packages..." | log
& $venvPython -c "import torch, transformers; print('torch', torch.__version__, '| transformers', transformers.__version__)" 2>&1 | log
if ($LASTEXITCODE -ne 0) {
    " ERROR - venv has missing/broken Python packages (import failed)." | log
    " ERROR - Possible causes: Defender quarantine, disk cleanup, or external tampering." | log
    " ERROR - Re-prep required:" | log
    " ERROR -   delete C:\hobl_bin\prep_status\pytorch_inf_v2<version> on the DUT and re-run." | log
    Exit 1
}

$logDir = Split-Path -Parent $logFile
"Log directory for storing additional logs: $logDir" | log

# run_benchmark.py writes pytorch_inf_v2_inference_info.csv to --log-dir with
# canonical HOBL keys (scenario_runtime, tokens_per_second,
# total_tokens_generated, total_generation_time_s, ai_model, ai_device,
# architecture) plus pytorch_inf_v2-specific metrics (cold_load_s,
# first_inference_s, compile_time_s, prefill/decode tok/s, serialized_bytes,
# peak_memory_bytes, median/p95/CV fields).
$inferenceCSV = Join-Path $logDir "pytorch_inf_v2_inference_info.csv"
"-- Metrics will be stored in $inferenceCSV" | log

Write-RunPhaseMarker "phase.run_prep.end"
Write-RunPhaseMarker "phase.run_build.start"

"-- Run pytorch_inf_v2 inferencing (model_tier=$modelTier lane=$lane quant=$quant shape=$shape)" | log
$runArgs = @("run_benchmark.py", "--model-tier", $modelTier, "--lane", $lane, "--quant", $quant, "--shape", $shape, "--log-dir", "$logDir")
if ($noGpu) {
    "Running in CPU-only mode (--no-gpu)" | log
    $runArgs += "--no-gpu"
}
& $venvPython @runArgs > "$logDir\pytorch_inf_v2_output.txt" 2>&1
check($lastexitcode)
Write-RunPhaseMarker "phase.run_build.end"
Write-RunPhaseMarker "phase.run_results.start"

"-- Parsing inference metrics" | log

if (Test-Path $inferenceCSV) {
    $csvContent = Get-Content $inferenceCSV
    $metricsHash = @{}
    foreach ($line in $csvContent) {
        $parts = $line -split ',', 2
        if ($parts.Count -eq 2) {
            $metricsHash[$parts[0]] = $parts[1]
        }
    }
} else {
    " ERROR - Inference metrics file not found: $inferenceCSV" | log
    Exit 1
}

$scenarioRuntime = if ($metricsHash['scenario_runtime']) { $metricsHash['scenario_runtime'] } else { 0 }

$resultsFile = Join-Path $logDir "pytorch_inf_v2_results.csv"

"" | log
"========================================" | log
"pytorch_inf_v2 Metrics Summary" | log
"========================================" | log
"Model:               $($metricsHash['ai_model'])" | log
"Device:              $($metricsHash['ai_device'])" | log
"Model Tier / Lane / Quant / Shape: $modelTier / $lane / $quant / $shape" | log
"Cold Load (s):       $($metricsHash['cold_load_s'])" | log
"First Inference (s): $($metricsHash['first_inference_s'])" | log
"Compile Time (s):    $($metricsHash['compile_time_s'])" | log
"TTFT (ms):           $($metricsHash['time_to_first_token_ms'])" | log
"Prefill tok/s:       $($metricsHash['prefill_tokens_per_second'])" | log
"Decode tok/s:        $($metricsHash['decode_tokens_per_second'])" | log
"Total Tokens:        $($metricsHash['total_tokens_generated'])" | log
"Serialized Bytes:    $($metricsHash['serialized_bytes'])" | log
"Peak Memory Bytes:   $($metricsHash['peak_memory_bytes'])" | log
"Scenario Runtime:    ${scenarioRuntime}s" | log
"========================================" | log

# Write metrics CSV file (key,value format - HOBL convention). Pass through
# every key run_benchmark.py produced, plus HOBL's own architecture key.
$metricsContent = New-Object System.Collections.Generic.List[string]
foreach ($key in $metricsHash.Keys) {
    $metricsContent.Add("$key,$($metricsHash[$key])")
}
$metricsContent.Add("architecture,$arch")
$metricsContent | Set-Content $resultsFile -Encoding UTF8
"Metrics saved to: $resultsFile" | log

"-- pytorch_inf_v2 run completed" | log

$elapsedTime = ((Get-Date) - [DateTime]$startTime).TotalSeconds
if (-not (Test-Path $timeTraceFile)) {
    Set-Content -Path $timeTraceFile -Value "Timestamp,scenario_runtime" -Encoding UTF8
}
if (-not (Test-Path $totalTokenTraceFile)) {
    Set-Content -Path $totalTokenTraceFile -Value "Timestamp,total_tokens" -Encoding UTF8
}
if (-not (Test-Path $tpsTraceFile)) {
    Set-Content -Path $tpsTraceFile -Value "Timestamp,tokens_per_second" -Encoding UTF8
}

Add-Content -Path $timeTraceFile -Value "$elapsedTime,$scenarioRuntime" -Encoding UTF8
Add-Content -Path $totalTokenTraceFile -Value "$elapsedTime,$($metricsHash['total_tokens_generated'])" -Encoding UTF8
Add-Content -Path $tpsTraceFile -Value "$elapsedTime,$($metricsHash['tokens_per_second'])" -Encoding UTF8

Write-RunPhaseMarker "phase.run_results.end"
