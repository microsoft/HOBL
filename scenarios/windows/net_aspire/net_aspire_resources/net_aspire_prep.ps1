# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = ""
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
if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\net_aspire_prep.log" }

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Determine processor architecture and set appropriate variables
$osInfo = Get-CimInstance Win32_OperatingSystem
$arch = $osInfo.OSArchitecture
$processorArch = $env:PROCESSOR_ARCHITECTURE

if ($arch -eq "64-bit" -and $processorArch -eq "AMD64") {
    $isARM64 = $false
    $logSuffix = "x64"
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    $isARM64 = $true
    $logSuffix = "ARM64"
} else {
    Write-Host " ERROR - Unsupported architecture: $arch (Processor: $processorArch)" -ForegroundColor Red
    Add-Content -Path $logFile -encoding utf8 " ERROR - Unsupported architecture: $arch (Processor: $processorArch)"
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

function checkWinget {
    param($code)
    # Winget exit codes:
    # 0 = Success
    # -1978335189 (0x8A15002B) = Already installed
    # -1978335215 (0x8A150011) = No applicable upgrade found
    # Other non-zero = Actual error
    if ($code -eq 0) {
        "Winget command succeeded" | log
    } elseif ($code -eq -1978335189) {
        "Package already installed (this is OK)" | log
    } elseif ($code -eq -1978335215) {
        "No applicable upgrade found (this is OK)" | log
    } else {
        " ERROR - Winget command failed with exit code: $code" | log
        Exit $code
    }
}

function checkGitClone {
    param($code, $repoPath)
    # Git clone exit codes:
    # 0 = Success
    # 128 = Usually means directory already exists or other repository error
    if ($code -eq 0) {
        "Git clone succeeded" | log
    } elseif ($code -eq 128 -and (Test-Path $repoPath)) {
        "Repository already exists (this is OK)" | log
    } else {
        " ERROR - Git clone failed with exit code: $code" | log
        Exit $code
    }
}

function checkSetLocation {
    param($path)
    if (Test-Path $path) {
        Set-Location $path
        "Changed directory to: $path" | log
    } else {
        " ERROR - Directory does not exist: $path" | log
        Exit 1
    }
}

Set-Content -Path $logFile -encoding utf8 "-- net_aspire prep started ($logSuffix version)"

# -------------------------------------------------------------------
# Install .NET SDK
# -------------------------------------------------------------------
"-- Installing .NET SDK 10.0 - 10.0.100-preview.5.25277.114 same version that's in restore.cmd" | log
winget install --id Microsoft.DotNet.SDK.Preview --version 10.0.100-preview.5.25277.114 --accept-source-agreements --accept-package-agreements
checkWinget($lastexitcode)
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# -------------------------------------------------------------------
# Install .NET 8.0 SDK
# -------------------------------------------------------------------
"-- Installing .NET 8.0 SDK" | log
winget install --id Microsoft.DotNet.SDK.8 --accept-source-agreements --accept-package-agreements
checkWinget($lastexitcode)
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

"-- Verifying dotnet installation" | log
$dotnetExe = Get-Command dotnet -ErrorAction SilentlyContinue
if ($dotnetExe) {
    "Found dotnet at: $($dotnetExe.Source)" | log
    dotnet --version 2>&1 | log
} else {
    " ERROR - dotnet not found on PATH after installation" | log
    Exit 1
}

# Verify architecture compatibility
if ($isARM64) {
    $dotnetPath = $dotnetExe.Source
    $bytes = [System.IO.File]::ReadAllBytes($dotnetPath)
    $peOffset = [BitConverter]::ToInt32($bytes, 0x3C)
    $machine = [BitConverter]::ToUInt16($bytes, $peOffset + 4)
    if ($machine -eq 0xAA64) {
        "Confirmed dotnet.exe is ARM64 native" | log
    } else {
        " ERROR - dotnet.exe is not ARM64 (machine type: 0x$($machine.ToString('X'))). ARM64 SDK is required." | log
        Exit 1
    }
}

# -------------------------------------------------------------------
# Install Git
# -------------------------------------------------------------------
"-- Installing git" | log
winget install --id Git.Git --accept-source-agreements --accept-package-agreements
checkWinget($lastexitcode)
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

"-- Verifying git installation" | log
git --version 2>&1 | log
check($lastexitcode)

# -------------------------------------------------------------------
# Clone and checkout Aspire repo
# -------------------------------------------------------------------
"-- Cloning dotnet/aspire repository" | log
Set-Location $scriptDrive\
git clone https://github.com/dotnet/aspire.git
checkGitClone $lastexitcode "$scriptDrive\aspire"

"-- Checking out tag v9.4.2" | log
checkSetLocation "$scriptDrive\aspire"
git checkout v9.4.2
check($lastexitcode)

# -------------------------------------------------------------------
# ARM64 workaround: remove incompatible .NET Core 2.0.9 runtime
# -------------------------------------------------------------------
if ($isARM64) {
    $net20RuntimePath = "C:\Program Files\dotnet\shared\Microsoft.NETCore.App\2.0.9"
    if (Test-Path $net20RuntimePath) {
        # Workaround: .NET Core 2.0.9 runtime does not have ARM64 Windows binaries (EOL Oct 2018).
        # The Azure Functions ExtensionsMetadataGenerator v4.0.1 targets netcoreapp2.0 and fails
        # with HRESULT 0x800700C1 (bad image) when it finds this x64-only runtime on an ARM64 host.
        # Removing it forces the runtime to roll forward to a compatible version.
        "-- Workaround: Removing incompatible .NET Core 2.0.9 runtime (x64-only, not ARM64 compatible)" | log
        "   Path: $net20RuntimePath" | log
        Remove-Item $net20RuntimePath -Recurse -Force
        "   Removed successfully" | log
    } else {
        "-- .NET Core 2.0.9 runtime not present (no workaround needed)" | log
    }
}

# -------------------------------------------------------------------
# Ensure system dotnet is used (not the repo-local Arcade SDK bootstrap)
# -------------------------------------------------------------------
# The Arcade SDK's InstallDotNetCore task installs x64 runtimes that overwrite ARM64
# native binaries on ARM64 hosts, causing hostpolicy.dll load failures (0x800700C1).
# Setting DOTNET_INSTALL_DIR to the system SDK tells the Arcade bootstrap to skip
# installing its own SDK, and using 'dotnet' directly bypasses build.cmd entirely.
$env:DOTNET_INSTALL_DIR = "C:\Program Files\dotnet"
"-- Set DOTNET_INSTALL_DIR=$($env:DOTNET_INSTALL_DIR) to use system SDK" | log

# -------------------------------------------------------------------
# Increase Playwright browser download timeout (default is too short for slow CDN)
# -------------------------------------------------------------------
$env:PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT = "300000"
"-- Set PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=300000 (5 minutes)" | log

# -------------------------------------------------------------------
# Initial restore (so run iterations only need build)
# -------------------------------------------------------------------
"-- Running initial dotnet restore" | log
dotnet restore Aspire.slnx
check($lastexitcode)
"   Restore completed successfully" | log

# -------------------------------------------------------------------
# Regenerate ConfigurationSchema.json files
# -------------------------------------------------------------------
# The Aspire repo validates that checked-in ConfigurationSchema.json files match
# what the installed SDK generates. A plain 'dotnet build' fails validation if they
# differ. The Aspire CI pipeline runs with /p:UpdateConfigurationSchema=true to
# regenerate them before the validation check. We do the same here during prep so
# that subsequent run iterations (which use plain 'dotnet build') pass cleanly.
"-- Regenerating ConfigurationSchema.json files" | log
dotnet build Aspire.slnx --no-incremental /p:UpdateConfigurationSchema=true
check($lastexitcode)
"   ConfigurationSchema regeneration completed" | log

"-- net_aspire prep completed ($logSuffix version)" | log
Exit 0