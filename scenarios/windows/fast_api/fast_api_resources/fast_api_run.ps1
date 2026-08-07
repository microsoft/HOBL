# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = "",
    [string]$startTime = (Get-Date).ToString("o")
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
        [HoblRunPhaseProvider]::Log.Phase($Marker, "fast_api")
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

$timeTraceFile = "$scriptDrive\hobl_data\result_time.trace"

# Determine processor architecture and set appropriate Python version
$osInfo = Get-CimInstance Win32_OperatingSystem
$arch = $osInfo.OSArchitecture
$processorArch = $env:PROCESSOR_ARCHITECTURE

if ($arch -eq "64-bit" -and $processorArch -eq "AMD64") {
    $pythonVersion = "3.12.10"
    $logSuffix = "x64"
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    $pythonVersion = "3.12.10-arm"
    $logSuffix = "ARM64"
} else {
    Write-Host " ERROR - Unsupported architecture: $arch (Processor: $processorArch)" -ForegroundColor Red
    Exit 1
}

Write-Host "Detected architecture: $arch (Processor: $processorArch)" -ForegroundColor Green
Write-Host "Using Python version: $pythonVersion for $logSuffix" -ForegroundColor Green

$LOG_DIR = "$scriptDrive\hobl_data"
$METRICS_FILE = "$LOG_DIR\fast_api_results.csv"

Write-RunPhaseMarker "phase.run_prep.start"

# Create log directory if it doesn't exist
if (-not (Test-Path $LOG_DIR)) {
    New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
}

if (-not $logFile) { $logFile = "$LOG_DIR\fast_api_run.log" }
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
Set-Content -Path $logFile -encoding utf8 "-- fast_api run started"

# Fix Windows Store Python PATH issue by prioritizing pyenv paths permanently
"Optimizing Python PATH priority permanently..." | log

$pyenvPaths = @(
    "$env:USERPROFILE\.pyenv\pyenv-win\shims",
    "$env:USERPROFILE\.pyenv\pyenv-win\bin"
)

# Function to optimize PATH order permanently
function Set-OptimizedPathOrder {
    Write-Host "`n=== Optimizing PATH Permanently ===" -ForegroundColor Magenta

    function ConvertTo-NormalizedPathEntry {
        param([string]$Entry)

        if (-not $Entry) { return $null }
        $value = $Entry.Trim().Trim('"')
        if (-not $value) { return $null }

        if ($value.Length -gt 3 -and $value.EndsWith("\")) {
            $value = $value.TrimEnd("\\")
        }

        return $value
    }

    function Get-PathEntries {
        param([string]$PathValue)

        $entries = New-Object System.Collections.Generic.List[string]
        if (-not $PathValue) { return $entries }

        foreach ($segment in ($PathValue -split ';')) {
            $normalized = ConvertTo-NormalizedPathEntry -Entry $segment
            if ($normalized) {
                $entries.Add($normalized)
            }
        }

        return $entries
    }

    function Add-UniquePathEntry {
        param(
            [System.Collections.Generic.List[string]]$List,
            [hashtable]$Seen,
            [string]$Entry
        )

        $normalized = ConvertTo-NormalizedPathEntry -Entry $Entry
        if (-not $normalized) { return }

        $key = $normalized.ToLowerInvariant()
        if (-not $Seen.ContainsKey($key)) {
            $List.Add($normalized)
            $Seen[$key] = $true
        }
    }
    
    # Check if running as administrator
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
    
    # Get current User PATH
    $currentUserPath = [System.Environment]::GetEnvironmentVariable('PATH', 'User')
    Write-Host "Original User PATH length: $($currentUserPath.Length) characters" -ForegroundColor Gray

    $windowsAppsCanonical = ConvertTo-NormalizedPathEntry -Entry "$env:LOCALAPPDATA\Microsoft\WindowsApps"
    $windowsAppsCanonicalKey = $windowsAppsCanonical.ToLowerInvariant()
    $windowsAppsEnvKey = "%localappdata%\microsoft\windowsapps"

    $pyenvPathKeys = @{}
    foreach ($pyenvPath in $pyenvPaths) {
        $normalizedPyenv = ConvertTo-NormalizedPathEntry -Entry $pyenvPath
        if ($normalizedPyenv) {
            $pyenvPathKeys[$normalizedPyenv.ToLowerInvariant()] = $true
        }
    }

    $userEntries = Get-PathEntries -PathValue $currentUserPath
    $cleanUserEntries = New-Object System.Collections.Generic.List[string]
    $cleanUserSeen = @{}
    $hadWindowsAppsInUserPath = $false

    foreach ($entry in $userEntries) {
        $entryKey = $entry.ToLowerInvariant()

        if ($entryKey -eq $windowsAppsCanonicalKey -or $entryKey -eq $windowsAppsEnvKey) {
            $hadWindowsAppsInUserPath = $true
            continue
        }

        if ($pyenvPathKeys.ContainsKey($entryKey)) {
            Write-Host "Removing existing pyenv path: $entry" -ForegroundColor Gray
            continue
        }

        Add-UniquePathEntry -List $cleanUserEntries -Seen $cleanUserSeen -Entry $entry
    }

    $newUserEntries = New-Object System.Collections.Generic.List[string]
    $newUserSeen = @{}

    foreach ($pyenvPath in $pyenvPaths) {
        Add-UniquePathEntry -List $newUserEntries -Seen $newUserSeen -Entry $pyenvPath
    }

    foreach ($entry in $cleanUserEntries) {
        Add-UniquePathEntry -List $newUserEntries -Seen $newUserSeen -Entry $entry
    }

    if ($hadWindowsAppsInUserPath -or (Test-Path $windowsAppsCanonical)) {
        Add-UniquePathEntry -List $newUserEntries -Seen $newUserSeen -Entry $windowsAppsCanonical
    }

    $newUserPath = ($newUserEntries -join ';')
    
    try {
        # Update User PATH permanently
        Write-Host "Updating User PATH permanently..." -ForegroundColor Yellow
        [System.Environment]::SetEnvironmentVariable('PATH', $newUserPath, 'User')
        Write-Host "New User PATH length: $($newUserPath.Length) characters" -ForegroundColor Gray
        
        if ($isAdmin) {
            Write-Host "Running as Administrator - also updating Machine PATH" -ForegroundColor Green
            
            # Get and clean Machine PATH
            $machinePath = [System.Environment]::GetEnvironmentVariable('PATH', 'Machine')
            $machineEntries = Get-PathEntries -PathValue $machinePath
            $cleanMachineEntries = New-Object System.Collections.Generic.List[string]
            $cleanMachineSeen = @{}

            foreach ($entry in $machineEntries) {
                if ($pyenvPathKeys.ContainsKey($entry.ToLowerInvariant())) {
                    continue
                }
                Add-UniquePathEntry -List $cleanMachineEntries -Seen $cleanMachineSeen -Entry $entry
            }

            $newMachineEntries = New-Object System.Collections.Generic.List[string]
            $newMachineSeen = @{}
            foreach ($pyenvPath in $pyenvPaths) {
                Add-UniquePathEntry -List $newMachineEntries -Seen $newMachineSeen -Entry $pyenvPath
            }
            foreach ($entry in $cleanMachineEntries) {
                Add-UniquePathEntry -List $newMachineEntries -Seen $newMachineSeen -Entry $entry
            }

            $newMachinePath = ($newMachineEntries -join ';')
            
            Write-Host "Updating Machine PATH permanently..." -ForegroundColor Yellow
            [System.Environment]::SetEnvironmentVariable('PATH', $newMachinePath, 'Machine')
        }
        
        # Update current session PATH to match Windows standard: Machine + User
        $machinePath = [System.Environment]::GetEnvironmentVariable('PATH', 'Machine')
        $env:PATH = $machinePath + ";" + $newUserPath
        
        Write-Host "PATH optimization complete!" -ForegroundColor Green
        Write-Host "pyenv paths have FIRST priority" -ForegroundColor Green
        if ($hadWindowsAppsInUserPath -or (Test-Path $windowsAppsCanonical)) {
            Write-Host "Windows Store Python moved to LAST priority" -ForegroundColor Green
        }
        if ($isAdmin) {
            Write-Host "Changes applied system-wide for all users" -ForegroundColor Green
        }
        
    } catch {
        Write-Host "Failed to update PATH: $($_.Exception.Message)" -ForegroundColor Red
        Exit 1
    }
}

# Optimize PATH permanently
Set-OptimizedPathOrder

# PATH is now optimized: pyenv first (from User PATH), then system dirs (from Machine PATH)
# Windows Store Python is at the end with lowest priority

# Verify required commands are findable on PATH after Set-OptimizedPathOrder.
# Fail fast with a clear diagnostic instead of a chain of "term not recognized" errors.
foreach ($cmd in @('pyenv')) {
    $resolved = Get-Command $cmd -ErrorAction SilentlyContinue
    if (-not $resolved) {
        " ERROR - Required command '$cmd' not found on PATH after PATH optimization." | log
        " ERROR - Prep may not have completed, or the RPC service has a stale PATH." | log
        " ERROR - PATH: $env:Path" | log
        Exit 1
    }
    "Found ${cmd}: $($resolved.Source)" | log
}

Set-Location "$scriptDrive\FastAPI"

"Setting Python global version to $pythonVersion..." | log
pyenv global $pythonVersion
if ($LASTEXITCODE -ne 0) {
    " ERROR - Failed to set Python version $pythonVersion. Make sure it's installed via pyenv." | log
    "Run the FastAPI prep script first to install the correct Python version." | log
    Exit 1
}

# --- Validate per-scenario venv and required packages ---
# Prep stages all Python packages into a private venv under this scenario's
# resource directory. We invoke that venv's python.exe by absolute path to
# bypass any pyenv/PATH instability caused by other scenarios. If the venv
# is missing or an expected package is not importable, we fail fast with a
# clear diagnostic instead of cryptic errors mid-build.
$venvPython = "$scriptDrive\hobl_bin\fast_api_resources\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    " ERROR - fast_api venv missing at $venvPython" | log
    " ERROR - Prep state is corrupt. Re-prep required:" | log
    " ERROR -   delete $scriptDrive\hobl_bin\prep_status\fast_api<version> on the DUT and re-run." | log
    Exit 1
}
"Using venv python: $venvPython" | log

"Validating venv has required packages..." | log
& $venvPython -c "import build, coverage, pytest; print('build', build.__version__, '| coverage', coverage.__version__, '| pytest', pytest.__version__)" 2>&1 | log
if ($LASTEXITCODE -ne 0) {
    " ERROR - venv has missing/broken Python packages (build, coverage, pytest expected)." | log
    " ERROR - Possible causes: Defender quarantine, disk cleanup, or external tampering." | log
    " ERROR - Re-prep required: delete $scriptDrive\hobl_bin\prep_status\fast_api<version> on the DUT and re-run." | log
    Exit 1
}

# Route PEP 517 build isolation through the approved Microsoft PyPI feed proxy.
# `python -m build` spins up its own isolated environment and pip-installs the build
# backend (pdm-backend) on every run; that isolated pip honors PIP_INDEX_URL. Without
# this it targets public PyPI, which is blocked/SSL-inspected on Microsoft-managed
# devices (CISO Central Feed Services policy) and injects network variability into
# build_time. Setting it here keeps the timed build off the non-approved feed.
$env:PIP_INDEX_URL = "https://packagefeedproxy.microsoft.io/pypi/simple"
$env:UV_DEFAULT_INDEX = $env:PIP_INDEX_URL
"Set PIP_INDEX_URL for build isolation: $env:PIP_INDEX_URL" | log
"Set UV_DEFAULT_INDEX for uv build isolation: $env:UV_DEFAULT_INDEX" | log

"Running legacy Python package build..." | log
Write-RunPhaseMarker "phase.run_prep.end"
Write-RunPhaseMarker "phase.run_build.start"
# Redirect output to a per-phase log so it is preserved in the results share.
# Measure-Command discards pipeline output, and the RPC buffer is lost on timeout,
# so file redirection is the only way to capture build/test output.
$buildLog = "$LOG_DIR\fast_api_build.log"
"Build output: $buildLog" | log
if (Test-Path ".\dist") {
    Remove-Item -Recurse -Force ".\dist"
}
$buildTime = (Measure-Command {
    & $venvPython -m build *> $buildLog
}).TotalSeconds
$buildExitCode = $LASTEXITCODE
Write-RunPhaseMarker "phase.run_build.end"
if ($buildExitCode -ne 0) {
    " ERROR - Build failed. See $buildLog for details." | log
    Exit 1
}
$buildTime = [math]::Round($buildTime, 2)
"Legacy python -m build completed in ${buildTime}s" | log

$venvUv = "$scriptDrive\hobl_bin\fast_api_resources\.venv\Scripts\uv.exe"
if (-not (Test-Path $venvUv)) {
    " ERROR - uv executable missing at $venvUv. Re-prep required." | log
    Exit 1
}

"Running modern uv package build..." | log
Write-RunPhaseMarker "phase.run_uv_build.start"
$uvBuildLog = "$LOG_DIR\fast_api_uv_build.log"
"uv build output: $uvBuildLog" | log
if (Test-Path ".\dist_uv") {
    Remove-Item -Recurse -Force ".\dist_uv"
}
$uvBuildTime = (Measure-Command {
    & $venvUv build --out-dir ".\dist_uv" *> $uvBuildLog
}).TotalSeconds
$uvBuildExitCode = $LASTEXITCODE
Write-RunPhaseMarker "phase.run_uv_build.end"
if ($uvBuildExitCode -ne 0) {
    " ERROR - uv build failed. See $uvBuildLog for details." | log
    Exit 1
}
$uvBuildTime = [math]::Round($uvBuildTime, 2)
"uv build completed in ${uvBuildTime}s" | log

"Setting environment variables..." | log
$env:PYTHONPATH = "./docs_src"
$env:PYTHONIOENCODING = "utf-8"

"Running tests with coverage..." | log
Write-RunPhaseMarker "phase.run_test.start"
$testLog = "$LOG_DIR\fast_api_test.log"
"Test output: $testLog" | log
# Invoke coverage via the venv's python so it resolves to the venv-installed
# coverage package (installed via requirements-tests.txt). A bare `coverage`
# would go through PATH lookup and either fail or hit a different Python.
$testTime = (Measure-Command {
    & $venvPython -m coverage run -m pytest tests *> $testLog
}).TotalSeconds
$testExitCode = $LASTEXITCODE
Write-RunPhaseMarker "phase.run_test.end"
Write-RunPhaseMarker "phase.run_results.start"
$testTime = [math]::Round($testTime, 2)

if ($testExitCode -eq 0) {
    "FastAPI tests completed successfully!" | log
} else {
    "Tests failed with exit code: $testExitCode" | log
}
"Tests completed in ${testTime}s" | log

# ============================================================================
# Calculate scenario_runtime and save metrics
# ============================================================================
$scenarioRuntime = [math]::Round($buildTime + $uvBuildTime + $testTime, 2)

"" | log
"========================================" | log
"FastAPI Maintainer Release Validation Metrics" | log
"========================================" | log
"Legacy python -m build: ${buildTime}s" | log
"Modern uv build:        ${uvBuildTime}s" | log
"Full coverage tests:    ${testTime}s" | log
"scenario_runtime (total): ${scenarioRuntime}s" | log
"========================================" | log

# Write metrics CSV file (key,value format)
$metricsContent = @"
scenario_runtime,$scenarioRuntime
build_time,$buildTime
uv_build_time,$uvBuildTime
test_time,$testTime
architecture,$logSuffix
"@

Set-Content -Path $METRICS_FILE -Value $metricsContent -NoNewline
"Metrics saved to: $METRICS_FILE" | log

$elapsedTime = ((Get-Date) - [DateTime]$startTime).TotalSeconds
# Append to .trace files for timeline correlation (key,value format)
if (-not (Test-Path $timeTraceFile)) {
    "Creating trace file with header: $timeTraceFile" | log
    Set-Content -Path $timeTraceFile -Value "Timestamp,build_time,uv_build_time,test_time,total_time" -Encoding UTF8
}

$traceContent = @"
$elapsedTime,$buildTime,$uvBuildTime,$testTime,$scenarioRuntime
"@
"Appending time info to trace file: $timeTraceFile" | log  
Add-Content -Path $timeTraceFile -Value $traceContent -Encoding UTF8

Write-RunPhaseMarker "phase.run_results.end"

Exit $testExitCode