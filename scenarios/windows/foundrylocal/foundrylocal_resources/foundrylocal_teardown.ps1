# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = "",
    [string]$model = "qwen2.5-0.5b"
)

$scriptDrive = Split-Path -Qualifier $PSScriptRoot
if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\foundrylocal_teardown.log" }

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

Set-Content -Path $logFile -encoding utf8 "-- Foundry Local teardown started ($logSuffix version)"

"Model to remove: $model" | log

# Refresh PATH to ensure dotnet is available
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# ============================================================================
# Remove model from cache
# ============================================================================
"Removing model from cache..." | log

$appDll = Join-Path $PSScriptRoot "foundrylocal_app\publish\FoundryLocalWorkload.dll"
$dotnetCmd = Get-Command dotnet -ErrorAction SilentlyContinue

if ($dotnetCmd -and (Test-Path $appDll)) {
    "Running SDK teardown for model: $model" | log
    $output = & dotnet $appDll teardown $model 2>&1
    $output | ForEach-Object { "  $_" | log }
    
    if ($LASTEXITCODE -eq 0) {
        "Model removed successfully" | log
    } else {
        "Warning: Model removal returned exit code $LASTEXITCODE (model may not have been cached)" | log
    }
} else {
    "Warning: Foundry Local workload app or dotnet not found, skipping cache removal" | log
}

# ============================================================================
# Summary
# ============================================================================
"" | log
"========================================" | log
"Foundry Local teardown completed ($logSuffix version)" | log
"========================================" | log
"Log file: $logFile" | log

Exit 0
