# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = "",
    [string]$model = "qwen2.5-0.5b",
    [string]$prompt = "What is the meaning of life?"
)

$scriptDrive = Split-Path -Qualifier $PSScriptRoot

if (-not (Test-Path "$scriptDrive\hobl_data")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_data" -ForegroundColor Red
    Exit 1
}
if (-not (Test-Path "$scriptDrive\hobl_bin")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_bin" -ForegroundColor Red
    Exit 1
}

if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\foundrylocal_run.log" }

# Require PowerShell > 7
$required = [version]"7.0"
if (-not $PSVersionTable.PSVersion) {
    Write-Host "Cannot determine PowerShell version; aborting." -ForegroundColor Red
    Exit 1
}
if ([version]$PSVersionTable.PSVersion -le $required) {
    Write-Host "This script requires PowerShell greater than $required. Current: $($PSVersionTable.PSVersion)" -ForegroundColor Yellow
    Write-Host "Please install PowerShell 7 or later from https://aka.ms/powershell" -ForegroundColor Yellow
    Exit 1
}

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

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
        [HoblRunPhaseProvider]::Log.Phase($Marker, "foundrylocal")
    } catch {
    }
}

# Determine processor architecture
$osInfo = Get-CimInstance Win32_OperatingSystem
$arch = $osInfo.OSArchitecture
$processorArch = $env:PROCESSOR_ARCHITECTURE

if ($arch -eq "64-bit" -and $processorArch -eq "AMD64") {
    $logSuffix = "x64"
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    $logSuffix = "ARM64"
} else {
    Write-Host " ERROR - Unsupported architecture: $arch (Processor: $processorArch)" -ForegroundColor Red
    Exit 1
}

# Update log file name to include architecture
$logFile = $logFile -replace "\.log$", "_$($logSuffix.ToLower()).log"

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
        " ERROR - Last command failed with exit code: $code" | log
        Exit $code
    }
}

Set-Content -Path $logFile -encoding utf8 "-- Foundry Local run started ($logSuffix version)"

"Detected architecture: $arch (Processor: $processorArch)" | log
"Model: $model" | log
"Prompt: $prompt" | log
Write-RunPhaseMarker "phase.run_prep.start"

# Refresh PATH to ensure dotnet is available
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

$dotnetCmd = Get-Command dotnet -ErrorAction SilentlyContinue
if (-not $dotnetCmd) {
    " ERROR - Required command 'dotnet' not found on PATH after refresh." | log
    " ERROR - Prep may not have completed, or the RPC service has a stale PATH." | log
    " ERROR - PATH: $env:Path" | log
    Exit 1
}
"Found dotnet: $($dotnetCmd.Source)" | log

$appDll = Join-Path $PSScriptRoot "foundrylocal_app\publish\FoundryLocalWorkload.dll"
if (-not (Test-Path $appDll)) {
    " ERROR - Foundry Local workload app not found: $appDll" | log
    " ERROR - Re-prep is required." | log
    Exit 1
}

# Output directory for results
$outputDir = "$scriptDrive\hobl_data"
if (-not (Test-Path $outputDir)) {
    "Creating output directory: $outputDir" | log
    New-Item -Path $outputDir -ItemType Directory -Force | Out-Null
}

# ============================================================================
# Run inference
# ============================================================================
Write-RunPhaseMarker "phase.run_prep.end"
Write-RunPhaseMarker "phase.run_build.start"
"Running inference..." | log
"Running Foundry Local SDK inference for model: $model" | log

$startTime = Get-Date

# Run the model and capture output
$output = & dotnet $appDll run $model $prompt 2>&1
$exitCode = $LASTEXITCODE

$endTime = Get-Date
$duration = $endTime - $startTime

# Log the output
"" | log
"=== Model Output ===" | log
$output | ForEach-Object { "  $_" | log }
"====================" | log

check $exitCode
Write-RunPhaseMarker "phase.run_build.end"
Write-RunPhaseMarker "phase.run_results.start"

$scenarioRuntime = [math]::Round($duration.TotalSeconds, 2)

"" | log
"Scenario completed in $scenarioRuntime seconds" | log

# ============================================================================
# Save results
# ============================================================================
$resultsFile = Join-Path $outputDir "foundrylocal_results.csv"

# Save results file (HOBL convention: *_results.csv with key,value pairs for rollup)
# scenario_runtime is the standard metric name for execution time in seconds
$resultsContent = @(
    "scenario_runtime,$scenarioRuntime"
    "architecture,$logSuffix"
    "ai_model,$model"
    "prompt,$prompt"
)
$resultsContent | Set-Content $resultsFile -Encoding UTF8
"Results saved to: $resultsFile" | log

# ============================================================================
# Summary
# ============================================================================
"" | log
"========================================" | log
"Foundry Local run completed successfully ($logSuffix version)" | log
"Model: $model" | log
"Scenario runtime: $scenarioRuntime seconds" | log
"========================================" | log
"Log file: $logFile" | log
Write-RunPhaseMarker "phase.run_results.end"

Exit 0
