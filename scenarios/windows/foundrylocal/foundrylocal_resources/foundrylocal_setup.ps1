# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = "",
    [string]$model = "qwen2.5-0.5b"
)

$scriptDrive = Split-Path -Qualifier $PSScriptRoot
if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\foundrylocal_setup.log" }

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

function check {
    param($code)
    if ($code -ne 0) {
        " ERROR - Last command failed with exit code: $code" | log
        Exit $code
    }
}

Set-Content -Path $logFile -encoding utf8 "-- Foundry Local setup started ($logSuffix version)"

"Detected architecture: $arch (Processor: $processorArch)" | log
"Model to download: $model" | log

# Refresh PATH to ensure dotnet is available
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# ============================================================================
# Download model to cache
# ============================================================================
"Downloading model to local cache..." | log

$appDll = Join-Path $PSScriptRoot "foundrylocal_app\publish\FoundryLocalWorkload.dll"
if (-not (Test-Path $appDll)) {
    " ERROR - Foundry Local workload app not found: $appDll" | log
    " ERROR - Re-prep is required." | log
    Exit 1
}

"Running SDK setup for model: $model" | log
$startTime = Get-Date

dotnet $appDll setup $model 2>&1 | ForEach-Object { "  $_" | log }
check $LASTEXITCODE

$endTime = Get-Date
$duration = $endTime - $startTime
"Model download completed in $($duration.TotalSeconds) seconds" | log

# ============================================================================
# Summary
# ============================================================================
"" | log
"========================================" | log
"Foundry Local setup completed successfully ($logSuffix version)" | log
"Model: $model" | log
"Download time: $($duration.TotalSeconds) seconds" | log
"========================================" | log
"Log file: $logFile" | log

Exit 0
