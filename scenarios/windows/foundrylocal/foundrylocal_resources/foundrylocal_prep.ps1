# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = "",
    [string]$foundryVersion = "2.0.1"
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
if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\foundrylocal_prep.log" }

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
    $runtimeIdentifier = "win-x64"
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    $logSuffix = "ARM64"
    $runtimeIdentifier = "win-arm64"
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

function checkWinget {
    param($code)
    # Winget exit codes:
    # 0 = Success
    # -1978335189 (0x8A15002B) = Already installed
    # -1978335215 (0x8A150011) = No applicable upgrade found
    if ($code -eq 0) {
        "Winget command succeeded" | log
        return
    } elseif ($code -eq -1978335189) {
        "Package already installed" | log
        return
    } elseif ($code -eq -1978335215) {
        "No upgrade available (already up to date)" | log
        return
    } else {
        " ERROR - Winget command failed with exit code: $code" | log
        Exit $code
    }
}

Set-Content -Path $logFile -encoding utf8 "-- Foundry Local prep started ($logSuffix version)"

"Detected architecture: $arch (Processor: $processorArch)" | log

# ============================================================================
# Step 1: Install the .NET 8 SDK
# ============================================================================
"Step 1: Installing .NET 8 SDK..." | log

# --- Remove the msstore source before any winget install so a broken pinned
# certificate on that source cannot fail the command (winget 0x8a15005e /
# -1978335138) behind an SSL-inspecting proxy. All needed packages are on 'winget'. ---
try {
    if ((winget source list 2>$null) -match "msstore") {
        "Removing msstore winget source to avoid pinned-certificate failures (0x8a15005e)" | log
        winget source remove msstore 2>&1 | log
    }
} catch {
    "Could not remove msstore source (continuing): $($_.Exception.Message)" | log
}

"Installing Microsoft.DotNet.SDK.8 via winget..." | log
winget install --id Microsoft.DotNet.SDK.8 --source winget --accept-source-agreements --accept-package-agreements 2>&1 | ForEach-Object { "  $_" | log }
checkWinget $LASTEXITCODE

# Refresh PATH to pick up the newly installed SDK
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# ============================================================================
# Step 2: Download the Foundry Local 2.0.1 packages
# ============================================================================
"Step 2: Downloading Foundry Local SDK version $foundryVersion..." | log

$dotnetCmd = Get-Command dotnet -ErrorAction SilentlyContinue
if (-not $dotnetCmd) {
    " ERROR - dotnet not found on PATH after installation" | log
    Exit 1
}
"Found dotnet at: $($dotnetCmd.Source)" | log
dotnet --info 2>&1 | ForEach-Object { "  $_" | log }

$curlCmd = Get-Command curl.exe -ErrorAction SilentlyContinue
if (-not $curlCmd) {
    " ERROR - curl.exe not found on PATH" | log
    Exit 1
}
"Found curl.exe at: $($curlCmd.Source)" | log

$appDir = Join-Path $PSScriptRoot "foundrylocal_app"
$projectFile = Join-Path $appDir "FoundryLocalWorkload.csproj"
$packageDir = Join-Path $appDir "packages"
$publishDir = Join-Path $appDir "publish"

if (-not (Test-Path $projectFile)) {
    " ERROR - Foundry Local workload project not found: $projectFile" | log
    Exit 1
}

New-Item -Path $packageDir -ItemType Directory -Force | Out-Null
if (Test-Path $publishDir) {
    Remove-Item -Path $publishDir -Recurse -Force
}
New-Item -Path $publishDir -ItemType Directory | Out-Null

$packages = @(
    "Microsoft.AI.Foundry.Local"
    "Microsoft.AI.Foundry.Local.Runtime"
)

foreach ($package in $packages) {
    $packageFile = Join-Path $packageDir "$package.$foundryVersion.nupkg"
    $packageUrl = "https://www.nuget.org/api/v2/package/$package/$foundryVersion"
    "Downloading $package $foundryVersion from: $packageUrl" | log
    & $curlCmd.Source -L --fail --retry 3 --output $packageFile $packageUrl 2>&1 | ForEach-Object { "  $_" | log }
    check $LASTEXITCODE

    if (-not (Test-Path $packageFile) -or (Get-Item $packageFile).Length -eq 0) {
        " ERROR - Downloaded package is missing or empty: $packageFile" | log
        Exit 1
    }
}

# ============================================================================
# Step 3: Restore and publish the workload app
# ============================================================================
"Step 3: Publishing Foundry Local workload for $runtimeIdentifier..." | log

dotnet restore $projectFile --runtime $runtimeIdentifier --configfile (Join-Path $appDir "NuGet.config") 2>&1 | ForEach-Object { "  $_" | log }
check $LASTEXITCODE

dotnet publish $projectFile --configuration Release --runtime $runtimeIdentifier --self-contained false --no-restore --output $publishDir 2>&1 | ForEach-Object { "  $_" | log }
check $LASTEXITCODE

$appDll = Join-Path $publishDir "FoundryLocalWorkload.dll"
if (-not (Test-Path $appDll)) {
    " ERROR - Published Foundry Local workload not found: $appDll" | log
    Exit 1
}
"Published workload: $appDll" | log

# ============================================================================
# Summary
# ============================================================================
"" | log
"========================================" | log
"Foundry Local prep completed successfully ($logSuffix version)" | log
"SDK version: $foundryVersion" | log
"========================================" | log
"Log file: $logFile" | log

Exit 0
