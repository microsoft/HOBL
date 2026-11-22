# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = "",
    [string]$startTime = (Get-Date).ToString("o"),
    [switch]$binlog,
    [switch]$skipPlaywrightBrowserInstall,
    [ValidateRange(0, 2147483647)]
    [int]$maxCpuCount = 0
)

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
        [HoblRunPhaseProvider]::Log.Phase($Marker, "net_aspire")
    } catch {
    }
}

# Configuration
$scriptDrive = Split-Path -Qualifier $PSScriptRoot

# Refresh PATH from Machine+User environment so dotnet (installed via winget during prep)
# is visible to this session. The HOBL RPC service started before prep ran, so the inherited
# PATH is stale and does not include C:\Program Files\dotnet without this refresh.
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# Fallback: ensure the default dotnet install directory is on PATH even if the env var
# was not updated (e.g. dotnet installed by a non-winget installer that did not update PATH).
$dotnetDir = "C:\Program Files\dotnet"
if ((Test-Path "$dotnetDir\dotnet.exe") -and (";$env:Path;" -notlike "*;$dotnetDir;*")) {
    $env:Path = "$dotnetDir;$env:Path"
}

if (-not (Test-Path "$scriptDrive\hobl_data")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_data" -ForegroundColor Red
    Exit 1
}
if (-not (Test-Path "$scriptDrive\hobl_bin")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_bin" -ForegroundColor Red
    Exit 1
}

if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\net_aspire_run.log" }
$metricsFile = "$scriptDrive\hobl_data\net_aspire_results.csv"
$traceFile = "$scriptDrive\hobl_data\net_aspire_results.trace"
$aspireDir = "$scriptDrive\aspire"

# Ensure log directory exists
$logDir = Split-Path $logFile -Parent
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

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
        Exit 1
    }
}

"-- net_aspire run started" | log
Write-RunPhaseMarker "phase.run_prep.start"

# Change to aspire directory
if (-not (Test-Path $aspireDir)) {
    " ERROR - Aspire directory not found: $aspireDir" | log
    " ERROR - Please run net_aspire_prep.ps1 first" | log
    Exit 1
}
Set-Location $aspireDir
"Current directory: $(Get-Location)" | log

# Verify Aspire.slnx exists
if (-not (Test-Path ".\Aspire.slnx")) {
    " ERROR - Aspire.slnx not found in $aspireDir" | log
    Exit 1
}

# ARM64 workaround: Redirect the Arcade SDK's runtime bootstrap to the system SDK.
#
# The Aspire repo uses Microsoft's Arcade SDK, which includes an MSBuild task called
# InstallDotNetCore. This task runs DURING the build (not before it) and downloads
# additional .NET runtimes into a local .dotnet directory (e.g. C:\aspire\.dotnet\).
# The problem: those downloaded runtimes are x64-only, which causes hostpolicy.dll
# load failures (HRESULT 0x800700C1 = bad image format) on ARM64 hosts.
#
# Setting DOTNET_INSTALL_DIR tells the Arcade SDK "the .NET install lives here" —
# so instead of creating C:\aspire\.dotnet\ with x64 binaries, it points at
# C:\Program Files\dotnet where the correct ARM64 SDK and runtimes were installed
# during prep. The Arcade bootstrap sees the runtimes already exist and skips the
# x64 download entirely.
#
# This must be set in every process because HOBL launches run in a separate shell
# that doesn't inherit env vars set during prep.
$env:DOTNET_INSTALL_DIR = "C:\Program Files\dotnet"
"-- DOTNET_INSTALL_DIR set to '$($env:DOTNET_INSTALL_DIR)' (prevents Arcade SDK from downloading x64 runtimes)" | log
$dotnetCmd = Get-Command dotnet -ErrorAction SilentlyContinue
if (-not $dotnetCmd) {
    " ERROR - dotnet not found on PATH. Prep may not have completed, or PATH was not refreshed." | log
    " ERROR - PATH: $env:Path" | log
    Exit 1
}
"-- dotnet on PATH: $($dotnetCmd.Source)" | log
"-- Active SDK version: $(dotnet --version 2>&1)" | log
"-- All installed SDKs:" | log
dotnet --list-sdks 2>&1 | ForEach-Object { "   $_" | log }

# Increase Playwright browser download timeout (default is too short for slow CDN)
$env:PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT = "300000"
"-- Set PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=300000 (5 minutes)" | log

# ============================================================================
# Clean phase (not timed)
# ============================================================================
"-- net_aspire clean started" | log
dotnet clean Aspire.slnx > "$logDir\net_aspire_clean.log" 2>&1
check($lastexitcode)
"-- net_aspire clean completed" | log

# ============================================================================
# Restore phase (not timed)
# ============================================================================
"-- net_aspire restore started" | log
dotnet restore Aspire.slnx > "$logDir\net_aspire_restore.log" 2>&1
check($lastexitcode)
"-- net_aspire restore completed" | log

# ============================================================================
# Build phase (timed)
# ============================================================================
$buildArgs = @("build", "Aspire.slnx", "--no-restore")
if ($skipPlaywrightBrowserInstall) {
    $buildArgs += "-p:InstallBrowsersForPlaywright=false"
}
if ($maxCpuCount -gt 0) {
    $buildArgs += "-m:$maxCpuCount"
}
if ($binlog) {
    $binlogFile = Join-Path "$scriptDrive\hobl_data" "net_aspire_build_$(Get-Date -Format 'yyyyMMdd_HHmmss_fffffff').binlog"
    $buildArgs += "-bl:$binlogFile"
    "-- Binary logging enabled (adds build overhead): $binlogFile" | log
}

"-- Build command: dotnet $($buildArgs -join ' ')" | log
"-- net_aspire build started" | log
Write-RunPhaseMarker "phase.run_prep.end"
Write-RunPhaseMarker "phase.run_build.start"

$buildDuration = Measure-Command {
    dotnet @buildArgs > "$logDir\net_aspire_build.log" 2>&1
}
check($lastexitcode)

$buildTime = [math]::Round($buildDuration.TotalSeconds, 2)
"-- net_aspire build completed in ${buildTime}s" | log
Write-RunPhaseMarker "phase.run_build.end"
Write-RunPhaseMarker "phase.run_results.start"

# ============================================================================
# Calculate scenario_runtime and save metrics
# ============================================================================
$scenarioRuntime = $buildTime

"" | log
"========================================" | log
".NET Aspire Metrics Summary" | log
"========================================" | log
"Build Time:  ${buildTime}s" | log
"scenario_runtime (total): ${scenarioRuntime}s" | log
"========================================" | log

# Write metrics CSV file (key,value format)
$metricsContent = @"
scenario_runtime,$scenarioRuntime
build_time,$buildTime
"@

Set-Content -Path $metricsFile -Value $metricsContent -NoNewline
"Metrics saved to: $metricsFile" | log

# Append to .trace file for timeline correlation (key,value format)
if (-not (Test-Path $traceFile)) {
    "Creating trace file with header: $traceFile" | log
    Set-Content -Path $traceFile -Value "Timestamp,net_aspire_build_time" -Encoding UTF8
}

$elapsedTime = ((Get-Date) - [DateTime]$startTime).TotalSeconds
$traceContent = @"
$elapsedTime,$buildTime
"@

"Appending build time to trace file: $traceFile" | log  
Add-Content -Path $traceFile -Value $traceContent -Encoding UTF8

Write-RunPhaseMarker "phase.run_results.end"

Exit 0