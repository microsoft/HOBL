# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.
#
# collect_5min_traces.ps1 - Background rolling WPR capture for perf_stress.
#
# Runs alongside the core HOBL trace using a named WPR instance
# (-instancename perfStressHeavy) so it does not collide with the default
# unnamed WPR session. Debug use only - a second concurrent WPR session
# perturbs measurements and the output of this run should not be used as
# a reference number.
#
# Default behavior: rolling 5-minute captures using general_cpi_collector.wprp,
# saved to C:\WPR_Traces\<RunName>\WPR_<timestamp>.etl.

param(
    [int]$IntervalMinutes = 5,
    [int]$Iterations = 0,
    [string]$OutputDir = "C:\WPR_Traces",
    [string]$RunName = "",

    # Default custom WPRP profile uploaded by code_PSECTRC.py
    [string]$WprpPath = "C:\hobl_bin\general_cpi_collector.wprp",

    # Optional fallback if WPRP not desired (e.g. -WprProfile GeneralProfile)
    [string]$WprProfile,

    # Named WPR instance - kept distinct from HOBL core's unnamed session
    [string]$InstanceName = "perfStressHeavy"
)

$ErrorActionPreference = "Continue"

# Elevation check
if (-not ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(`
    [Security.Principal.WindowsBuiltInRole]::Administrator)) {

    Start-Process powershell -Verb RunAs -ArgumentList `
        "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

# Build per-run subdirectory under OutputDir
if ($RunName) {
    $OutputDir = Join-Path $OutputDir $RunName
}
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

# Determine profile argument
if ($WprProfile) {
    Write-Host " INFO - Using built-in WPR profile -> $WprProfile"
    $profileArg = $WprProfile
}
else {
    if (-not (Test-Path $WprpPath)) {
        throw " ERROR - Default WPRP file not found: $WprpPath"
    }
    Write-Host " INFO - Using custom WPRP profile -> $WprpPath"
    $profileArg = "`"$WprpPath`""
}

Write-Host " INFO - WPR rolling capture started | Interval: $IntervalMinutes min | Instance: $InstanceName"
Write-Host " INFO - Output: $OutputDir"
Write-Host "---------------------------------------"

$iteration = 0

try {
    while ($true) {
        $iteration++
        if ($Iterations -gt 0 -and $iteration -gt $Iterations) {
            break
        }

        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $etlPath = Join-Path $OutputDir "WPR_${timestamp}.etl"

        Write-Host "[$timestamp] Recording started"

        # Cancel ONLY our named instance (do NOT touch HOBL core's unnamed session)
        wpr -cancel -instancename $InstanceName 2>$null | Out-Null

        wpr -start $profileArg -filemode -instancename $InstanceName | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning " ERROR - wpr -start failed with exit $LASTEXITCODE (instance=$InstanceName)"
            Start-Sleep -Seconds 30
            continue
        }

        Start-Sleep -Seconds ($IntervalMinutes * 60)

        wpr -stop $etlPath -instancename $InstanceName | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[$timestamp] Trace saved -> $etlPath"
        } else {
            Write-Warning " ERROR - wpr -stop failed with exit $LASTEXITCODE (instance=$InstanceName)"
        }
        Write-Host "---------------------------------------"
    }
}
catch {
    Write-Warning " ERROR - Tracing interrupted: $_"
}
finally {
    # Clean up only our named instance
    wpr -cancel -instancename $InstanceName 2>$null | Out-Null
    Write-Host " INFO - Tracing session ended (instance=$InstanceName)"
}
