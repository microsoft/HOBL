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
if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\fast_api_prep.log" }

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

# Set execution policy for current process to allow script execution
Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process -Force

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Determine processor architecture and set appropriate variables
$osInfo = Get-CimInstance Win32_OperatingSystem
$arch = $osInfo.OSArchitecture
$processorArch = $env:PROCESSOR_ARCHITECTURE

if ($arch -eq "64-bit" -and $processorArch -eq "AMD64") {
    $isARM64 = $false
    $logSuffix = "x64"
    $pythonVersion = "3.12.10"
    $vsArchParam = "x64"
    $vsHostArchParam = "x64"
    $vsProduct = "BuildTools"
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    $isARM64 = $true
    $logSuffix = "ARM64"
    $pythonVersion = "3.12.10-arm"
    $vsArchParam = "arm64"
    $vsHostArchParam = "arm64"
    $vsProduct = "Community"
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

function getVSVersion {
    param([string]$product)
    
    # vswhere.exe location is always in Program Files (x86) even on ARM64
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) {
        # Fallback for ARM64 where installer might be in Program Files
        $vswhere = "${env:ProgramFiles}\Microsoft Visual Studio\Installer\vswhere.exe"
        if (-not (Test-Path $vswhere)) {
            return $null
        }
    }
    
    try {
        $productFilter = if ($product -eq "BuildTools") { "Microsoft.VisualStudio.Product.BuildTools" } else { "Microsoft.VisualStudio.Product.Community" }
        $instances = & $vswhere -products $productFilter -format json | ConvertFrom-Json
        
        if ($instances) {
            $instance = $instances | Select-Object -First 1
            return @{
                Version = $instance.installationVersion
                DisplayName = $instance.displayName
                Path = $instance.installationPath
            }
        }
    } catch {
        return $null
    }
    
    return $null
}

# Visual Studio installation using direct installer download
# Architecture-aware: Build Tools for x64, Community for ARM64
function installVisualStudio {
    # Get the directory where the script is located
    $scriptDir = Split-Path -Parent $PSCommandPath
    
    if ($isARM64) {
        "-- Installing Visual Studio Community 2022 (direct installer for ARM64)" | log
        $installerUrl = "https://aka.ms/vs/17/release/vs_community.exe"
        $installerPath = "$env:TEMP\vs_community.exe"
        $productName = "VS Community"
        $vsconfigPath = Join-Path $scriptDir ".vsconfig_arm64"
    } else {
        "-- Installing Visual Studio Build Tools 2022 (direct installer for x64)" | log
        $installerUrl = "https://aka.ms/vs/17/release/vs_buildtools.exe"
        $installerPath = "$env:TEMP\vs_buildtools.exe"
        $productName = "VS Build Tools"
        $vsconfigPath = Join-Path $scriptDir ".vsconfig_x64"
    }
    
    # Verify .vsconfig file exists
    if (-not (Test-Path $vsconfigPath)) {
        " ERROR - .vsconfig file not found at: $vsconfigPath" | log
        return $false
    }
    
    "Using .vsconfig file: $vsconfigPath" | log
    
    # Check if VS is already installed by getting version info
    $existingVS = getVSVersion -product $vsProduct
    if ($existingVS -and $existingVS.Path) {
        # VS Installer is in a shared location, not in the product folder
        $sharedInstaller = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\setup.exe"
        
        if (Test-Path $sharedInstaller) {
            "Found existing Visual Studio installer at: $sharedInstaller" | log
            "Using existing installer to apply .vsconfig (handles LTSC and version mismatches)" | log
            $installerPath = $sharedInstaller
        } else {
            "Existing VS installation found but no installer at expected location, downloading new installer..." | log
            
            try {
                Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
                "$productName installer downloaded successfully" | log
            } catch {
                " ERROR - Failed to download $productName installer: $($_.Exception.Message)" | log
                return $false
            }
            
            if (-not (Test-Path $installerPath)) {
                " ERROR - $productName installer not found after download" | log
                return $false
            }
        }
    } else {
        "No existing Visual Studio installation found, downloading new installer..." | log
        
        try {
            Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
            "$productName installer downloaded successfully" | log
        } catch {
            " ERROR - Failed to download $productName installer: $($_.Exception.Message)" | log
            return $false
        }
        
        if (-not (Test-Path $installerPath)) {
            " ERROR - $productName installer not found after download" | log
            return $false
        }
    }
    
    if ($existingVS) {
        # Build modify arguments using .vsconfig file and install path
        $installArgs = @(
            "modify"
            "--installPath", "`"$($existingVS.Path)`""
            "--quiet"
            "--config", "`"$vsconfigPath`""
        )
        "Visual Studio Modify args: $($installArgs -join ' ')" | log
    } else {
        # Build install arguments using .vsconfig file
        $installArgs = @(
            "install"
            "--quiet"
            "--wait"
            "--config", "`"$vsconfigPath`""
        )
        "Visual Studio Install args: $($installArgs -join ' ')" | log
    }
    
    "Starting $productName installation (this will wait for completion)..." | log
    $logDirectory = Split-Path -Path $logFile -Parent
    $vsStdOut = Join-Path $logDirectory "vs_install_fast_api_stdout_$($logSuffix.ToLower()).log"
    $vsStdErr = Join-Path $logDirectory "vs_install_fast_api_stderr_$($logSuffix.ToLower()).log"
    "VS installer stdout redirected to: $vsStdOut" | log
    "VS installer stderr redirected to: $vsStdErr" | log
    try {
        $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru -RedirectStandardOutput $vsStdOut -RedirectStandardError $vsStdErr
        $exitCode = $process.ExitCode
        
        "$productName installer completed with exit code: $exitCode" | log
        
        # VS installer exit codes:
        # 0 = Success
        # 3010 = Success but reboot required
        if ($exitCode -eq 0 -or $exitCode -eq 3010) {
            if ($exitCode -eq 3010) {
                "Installation successful but may require reboot for full functionality" | log
            }
            return $true
        } else {
            " ERROR - $productName installation failed with exit code: $exitCode" | log
            return $false
        }
    } catch {
        " ERROR - Failed to run $productName installer: $($_.Exception.Message)" | log
        return $false
    } finally {
        # Clean up downloaded installer (not existing installer)
        " Cleaning up installer file..." | log
        if ($installerPath -like "$env:TEMP\*" -and (Test-Path $installerPath)) {
            Remove-Item $installerPath -ErrorAction SilentlyContinue
        }
    }
}

function verifyVSInstallation {
    "Verifying Visual Studio $vsProduct installation..." | log
    
    # First, try to find VS using vswhere which handles non-default locations
    $vsInfo = getVSVersion -product $vsProduct
    
    if (-not $vsInfo -or -not $vsInfo.Path) {
        " ERROR - Visual Studio $vsProduct not found using vswhere" | log
        return $false
    }
    
    $actualVSPath = $vsInfo.Path
    "Found Visual Studio at: $actualVSPath" | log
    "Version: $($vsInfo.Version)" | log
    "Display Name: $($vsInfo.DisplayName)" | log
    
    # Use actual installation path for verification
    $vsPath = Join-Path $actualVSPath "Common7\Tools\VsDevCmd.bat"
    $msbuildPath = Join-Path $actualVSPath "MSBuild\Current\Bin\MSBuild.exe"
    $clPath = Join-Path $actualVSPath "VC\Tools\MSVC"
    
    $vsDevReady = Test-Path $vsPath
    $msbuildReady = Test-Path $msbuildPath  
    $vcToolsReady = Test-Path $clPath
    
    # Additional ARM64-specific verification
    $archSpecificReady = $true
    if ($isARM64) {
        $arm64ToolsReady = $false
        if (Test-Path $clPath) {
            $msvcVersions = Get-ChildItem $clPath -Directory
            foreach ($version in $msvcVersions) {
                $arm64CompilerPath = Join-Path $version.FullName "bin\Hostarm64\arm64\cl.exe"
                if (Test-Path $arm64CompilerPath) {
                    $arm64ToolsReady = $true
                    "Found ARM64 compiler at: $arm64CompilerPath" | log
                    break
                }
            }
        }
        $archSpecificReady = $arm64ToolsReady
        "VS Components Check - VsDevCmd: $vsDevReady, MSBuild: $msbuildReady, VCTools: $vcToolsReady, ARM64Tools: $arm64ToolsReady" | log
    } else {
        "VS Components Check - VsDevCmd: $vsDevReady, MSBuild: $msbuildReady, VCTools: $vcToolsReady" | log
    }
    
    if ($vsDevReady -and $msbuildReady -and $vcToolsReady -and $archSpecificReady) {
        "Visual Studio $vsProduct verification successful" | log
        return $true
    } else {
        " ERROR - Visual Studio $vsProduct verification failed - missing components" | log
        return $false
    }
}
function diagnoseVSInstallation {
    "=== Diagnosing Visual Studio Installation for CMake ($logSuffix) ===" | log
    
    # Check vswhere.exe
    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path $vswhere) {
        "vswhere.exe found, checking installed instances:" | log
        try {
            $instances = & $vswhere -format json | ConvertFrom-Json
            foreach ($instance in $instances) {
                "  - $($instance.displayName) v$($instance.installationVersion) at $($instance.installationPath)" | log
            }
        } catch {
            "Could not parse vswhere output: $($_.Exception.Message)" | log
        }
    } else {
        " ERROR - vswhere.exe not found - this is required for CMake VS detection" | log
    }
    
    # Check VS environment variables
    $vsComnTools = $env:VS170COMNTOOLS
    if ($vsComnTools) {
        "VS170COMNTOOLS found: $vsComnTools" | log
    } else {
        "VS170COMNTOOLS environment variable not set" | log
    }
    
    # Check for architecture-specific VS components
    $vsInfo = getVSVersion -product $vsProduct
    if ($vsInfo -and $vsInfo.Path) {
        $vsDevCmdPath = Join-Path $vsInfo.Path "Common7\Tools\VsDevCmd.bat"
        if (Test-Path $vsDevCmdPath) {
            "Found VsDevCmd.bat at: $vsDevCmdPath" | log
        }
    }
    
    # Check processor architecture
    "Processor Architecture: $processorArch" | log
    "OS Architecture: $arch" | log
    "Target Architecture: $logSuffix" | log
    
    "=== End VS Diagnosis ===" | log
}

function initializeVSEnvironment {
    "Initializing Visual Studio environment for CMake ($logSuffix)..." | log
    
    # Use vswhere to find actual VS installation path
    $vsInfo = getVSVersion -product $vsProduct
    
    if (-not $vsInfo -or -not $vsInfo.Path) {
        " ERROR - Visual Studio $vsProduct not found using vswhere" | log
        return $false
    }
    
    $actualVSPath = $vsInfo.Path
    "Using Visual Studio from: $actualVSPath" | log
    
    # Use actual installation path for VsDevCmd
    $vsDevCmd = Join-Path $actualVSPath "Common7\Tools\VsDevCmd.bat"
    
    if (-not (Test-Path $vsDevCmd)) {
        " ERROR - VsDevCmd.bat not found at expected location: $vsDevCmd" | log
        return $false
    }
    
    "Using VsDevCmd.bat from: $vsDevCmd" | log
    
    # Initialize VS environment with architecture-specific parameters
    $tempBat = "$env:TEMP\vsinit_$($logSuffix.ToLower()).bat"
    Set-Content -Path $tempBat -Value @"
@echo off
call "$vsDevCmd" -arch=$vsArchParam -host_arch=$vsHostArchParam > nul 2>&1
set
"@
    
    # Execute the batch file and capture environment variables
    $envVars = cmd /c "$tempBat" 2>nul
    Remove-Item $tempBat -ErrorAction SilentlyContinue
    
    # Parse and set environment variables
    $envVars | ForEach-Object {
        if ($_ -match "^([^=]+)=(.*)$") {
            $name = $matches[1]
            $value = $matches[2]
            
            # Set important VS-related environment variables
            if ($name -match "^(PATH|INCLUDE|LIB|LIBPATH|VS.*|VC.*|WindowsSDK.*|Platform.*|PROCESSOR_ARCHITECTURE)$") {
                Set-Item "env:$name" $value -ErrorAction SilentlyContinue
            }
        }
    }
    
    "Visual Studio environment initialized successfully for $logSuffix" | log
    return $true
}

Set-Content -Path $logFile -encoding utf8 "-- FastAPI prep started ($logSuffix version)"

"Detected architecture: $arch (Processor: $processorArch)" | log
"Using Visual Studio $vsProduct for $logSuffix" | log


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

"-- Installing git" | log
winget install --id git.git --source winget --accept-source-agreements --accept-package-agreements
checkWinget($lastexitcode)
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

"-- Cloning git repo" | log
checkSetLocation "$scriptDrive\"
git clone https://github.com/fastapi/fastapi.git
checkGitClone $lastexitcode "$scriptDrive\fastapi"

"-- Checkout" | log
checkSetLocation "$scriptDrive\fastapi"
$targetVersion = "0.119.1"

# Ensure tags are available for checkout when repo already exists
git fetch --tags --force 2>$null | Out-Null

if (-not (Test-Path ".git")) {
    " ERROR - $scriptDrive\fastapi is not a git repository" | log
    Exit 1
}

if ((git rev-parse -q --verify "refs/tags/$targetVersion" 2>$null) -and $LASTEXITCODE -eq 0) {
    git checkout "tags/$targetVersion"
    check($lastexitcode)
} else {
    " ERROR - FastAPI tag not found: $targetVersion" | log
    "Available matching tags:" | log
    git tag -l "*$targetVersion*" | Select-Object -Last 20 | ForEach-Object { "  $_" | log }
    Exit 1
}

# Check Visual Studio version before installation
"Checking Visual Studio version before installation..." | log
$vsBefore = getVSVersion -product $vsProduct
if ($vsBefore) {
    "Existing $vsProduct installation found:" | log
    "  Version: $($vsBefore.Version)" | log
    "  Display Name: $($vsBefore.DisplayName)" | log
    "  Path: $($vsBefore.Path)" | log
} else {
    "No existing $vsProduct installation found" | log
}

# Install Visual Studio using architecture-appropriate installer
if (-not (installVisualStudio)) {
    " ERROR - Visual Studio $vsProduct installation failed" | log
    Exit 1
}

# Check Visual Studio version after installation
"Checking Visual Studio version after installation..." | log
$vsAfter = getVSVersion -product $vsProduct
if ($vsAfter) {
    "Current $vsProduct installation:" | log
    "  Version: $($vsAfter.Version)" | log
    "  Display Name: $($vsAfter.DisplayName)" | log
    "  Path: $($vsAfter.Path)" | log
} else {
    " ERROR - $vsProduct not found after installation" | log
    Exit 1
}

# Verify installation completed properly
if (-not (verifyVSInstallation)) {
    " ERROR - Visual Studio $vsProduct verification failed" | log
    Exit 1
}

# Diagnose VS installation for CMake
diagnoseVSInstallation

# Initialize VS environment to ensure CMake can find it
if (-not (initializeVSEnvironment)) {
    " ERROR - Failed to initialize Visual Studio environment" | log
    Exit 1
}

# Refresh environment variables after VS installation - CRITICAL for CMake detection
"Refreshing environment variables after VS installation..." | log
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# Refresh all VS-related environment variables
$vsEnvVars = @("VS170COMNTOOLS", "VSINSTALLDIR", "VCINSTALLDIR", "WindowsSDKDir", "WindowsSDKVersion")
foreach ($varName in $vsEnvVars) {
    $value = [System.Environment]::GetEnvironmentVariable($varName, "Machine")
    if ($value) {
        Set-Item "env:$varName" $value
        "$varName set to: $value" | log
    }
}

# Force refresh of process environment from registry
try {
    # Signal that environment changed to all windows
    $HWND_BROADCAST = [IntPtr]0xffff
    $WM_SETTINGCHANGE = 0x1a
    $null = Add-Type -TypeDefinition @"
        using System;
        using System.Runtime.InteropServices;
        public class Win32 {
            [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
            public static extern IntPtr SendMessageTimeout(
                IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam,
                uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
        }
"@
    $result = [UIntPtr]::Zero
    [Win32]::SendMessageTimeout($HWND_BROADCAST, $WM_SETTINGCHANGE, [UIntPtr]::Zero, "Environment", 2, 5000, [ref]$result)
    "Environment change notification sent" | log
} catch {
    "Could not send environment change notification: $($_.Exception.Message)" | log
}
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

"-- Installing python environment" | log
"Installing pyenv-win for Python version management..." | log
try {
    Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"
    & "./install-pyenv-win.ps1"
    "pyenv-win installation completed" | log
} catch {
    " ERROR - Failed to install pyenv-win: $($_.Exception.Message)" | log
    Exit 1
}

# Fix Windows Store Python PATH issue by prioritizing pyenv paths permanently
"Optimizing Python PATH priority permanently..." | log

$pyenvPaths = @(
    "$env:USERPROFILE\.pyenv\pyenv-win\shims",
    "$env:USERPROFILE\.pyenv\pyenv-win\bin"
)

# Function to optimize PATH order permanently
function Set-OptimizedPathOrder {
    "=== Optimizing PATH Permanently ===" | log

    function Normalize-PathEntry {
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
            $normalized = Normalize-PathEntry -Entry $segment
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

        $normalized = Normalize-PathEntry -Entry $Entry
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
    "Original User PATH length: $($currentUserPath.Length) characters" | log

    $windowsAppsCanonical = Normalize-PathEntry -Entry "$env:LOCALAPPDATA\Microsoft\WindowsApps"
    $windowsAppsCanonicalKey = $windowsAppsCanonical.ToLowerInvariant()
    $windowsAppsEnvKey = "%localappdata%\microsoft\windowsapps"

    $pyenvPathKeys = @{}
    foreach ($pyenvPath in $pyenvPaths) {
        $normalizedPyenv = Normalize-PathEntry -Entry $pyenvPath
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
            "Removing existing pyenv path: $entry" | log
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
        "Updating User PATH permanently..." | log
        [System.Environment]::SetEnvironmentVariable('PATH', $newUserPath, 'User')
        "New User PATH length: $($newUserPath.Length) characters" | log
        
        if ($isAdmin) {
            "Running as Administrator - also updating Machine PATH" | log
            
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
            
            "Updating Machine PATH permanently..." | log
            [System.Environment]::SetEnvironmentVariable('PATH', $newMachinePath, 'Machine')
        }
        
        # Update current session PATH to match Windows standard: Machine + User
        $machinePath = [System.Environment]::GetEnvironmentVariable('PATH', 'Machine')
        $env:PATH = $machinePath + ";" + $newUserPath
        
        # Log PATH diagnostic information
        "=== PATH Diagnostic Information ===" | log
        "Final User PATH length: $($newUserPath.Length) characters" | log
        "Final Machine PATH length: $($machinePath.Length) characters" | log
        "Combined session PATH length: $($env:PATH.Length) characters" | log
        "First 3 paths in session PATH:" | log
        $firstThreePaths = ($env:PATH -split ";")[0..2]
        for ($i = 0; $i -lt $firstThreePaths.Count; $i++) {
            "  [$($i+1)]: $($firstThreePaths[$i])" | log
        }
        "Last 3 paths in session PATH:" | log
        $allPaths = $env:PATH -split ";"
        $lastThreePaths = $allPaths[($allPaths.Count-3)..($allPaths.Count-1)]
        for ($i = 0; $i -lt $lastThreePaths.Count; $i++) {
            "  [$(($allPaths.Count-3)+$i+1)]: $($lastThreePaths[$i])" | log
        }
        
        "PATH optimization complete!" | log
        "pyenv paths have FIRST priority" | log
        if ($hadWindowsAppsInUserPath -or (Test-Path $windowsAppsCanonical)) {
            "Windows Store Python moved to LAST priority" | log
        }
        if ($isAdmin) {
            "Changes applied system-wide for all users" | log
        }
        
    } catch {
        " ERROR - Failed to update PATH: $($_.Exception.Message)" | log
        Exit 1
    }
}

# Optimize PATH permanently
Set-OptimizedPathOrder

# Additional PATH verification for troubleshooting
"=== POST-OPTIMIZATION PATH VERIFICATION ===" | log
"Current session PATH contains pyenv shims: $($env:PATH -like "*pyenv*shims*")" | log
"Current session PATH contains System32: $($env:PATH -like "*System32*")" | log
"Current session PATH contains WindowsApps: $($env:PATH -like "*WindowsApps*")" | log

# --- Install Python via pyenv (conditional — DO NOT use -f) ---
# Force-reinstall (`-f`) wipes the pyenv version directory including any packages
# installed by other scenarios that share this Python version. We only install
# when the version is truly missing.
"-- Installing python $pythonVersion for $logSuffix" | log
$installedVersions = (pyenv versions --bare 2>$null) -split "`n" | ForEach-Object { $_.Trim() }
if ($installedVersions -notcontains $pythonVersion) {
    "Installing Python $pythonVersion via pyenv (this may take several minutes)..." | log
    pyenv install $pythonVersion
    check($lastexitcode)
} else {
    "Python $pythonVersion already installed via pyenv — preserving existing install" | log
}

"Setting Python $pythonVersion as global version..." | log
pyenv global $pythonVersion
check($lastexitcode)

# Comprehensive Python detection and verification
function Find-AllPython {
    "=== Python Detection Report ===" | log
    
    # Resolve the real interpreter through pyenv, not its batch-file shim.
    "`n1. Python selected by pyenv:" | log
    try {
        $pathPythonRaw = pyenv which python 2>$null
        $pathPython = if ($pathPythonRaw) { $pathPythonRaw.Trim() } else { $null }
        if ($pathPython -and (Test-Path $pathPython)) {
            "  Found: $pathPython" | log
            & $pathPython --version 2>&1 | log
        } else {
            "  pyenv did not resolve python.exe" | log
        }
    } catch {
        "  pyenv did not resolve python.exe" | log
    }
    
    # Check pyenv
    "`n2. pyenv-win managed Python:" | log
    if (Get-Command pyenv -ErrorAction SilentlyContinue) {
        "  pyenv is available" | log
        pyenv versions | log
    } else {
        "  pyenv not found" | log
    }
}

# Run the detection
Find-AllPython

# Verify the real pyenv Python is available
"`n=== Python Resolution Verification ===" | log
$whichPythonRaw = pyenv which python 2>$null
$whichPython = if ($whichPythonRaw) { $whichPythonRaw.Trim() } else { $null }
if ($whichPython -and (Test-Path $whichPython)) {
    "Resolved python.exe: $whichPython" | log
} else {
    " ERROR - pyenv did not resolve a valid python.exe path" | log
    Exit 1
}

"Verifying Python installation..." | log
pyenv versions | log

"-- Installing dependencies" | log
checkSetLocation "$scriptDrive\FastAPI"

# Final verification that correct Python version is active
"Final Python version verification before installing dependencies..." | log
$currentPythonVersion = & $whichPython --version 2>&1
"Current Python version: $currentPythonVersion" | log

$expectedVersionPattern = $pythonVersion -replace "-arm", ""
if ($currentPythonVersion -like "*$expectedVersionPattern*") {
    "Correct Python version ($pythonVersion) is active" | log
} else {
    " ERROR - Wrong Python version active. Expected: $pythonVersion, Got: $currentPythonVersion" | log
    "Please check pyenv configuration" | log
    Exit 1
}

# --- Create per-scenario venv ---
# Packages live in this scenario's private venv directory, NOT in the shared pyenv
# site-packages. This isolates fast_api's packages from any future `pyenv install`
# (force or otherwise) from other scenarios, and from `pyenv global` switches.
$venvDir = "$scriptDrive\hobl_bin\fast_api_resources\.venv"
$pyenvPythonRaw = (pyenv which python 2>$null)
if (-not $pyenvPythonRaw) {
    " ERROR - pyenv which python returned no path; pyenv install may have failed" | log
    Exit 1
}
$pyenvPython = $pyenvPythonRaw.Trim()
if (-not (Test-Path $pyenvPython)) {
    " ERROR - pyenv python not found at: $pyenvPython" | log
    Exit 1
}
"Base pyenv python: $pyenvPython" | log

if (Test-Path $venvDir) {
    "Removing existing venv to ensure clean rebuild: $venvDir" | log
    Remove-Item -Recurse -Force $venvDir
}
"Creating venv at: $venvDir" | log
& $pyenvPython -m venv $venvDir
check($lastexitcode)

$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvPip = Join-Path $venvDir "Scripts\pip.exe"
if (-not (Test-Path $venvPython)) {
    " ERROR - venv python missing after venv creation: $venvPython" | log
    Exit 1
}
"Venv python: $venvPython" | log

# Microsoft-managed devices block direct access to public PyPI (CISO Central Feed
# Services policy). Install through the approved Microsoft package feed proxy instead.
# Same pinned versions are served, so there is no functional or performance change.
$pypiIndexUrl = "https://packagefeedproxy.microsoft.io/pypi/simple"
$env:UV_DEFAULT_INDEX = $pypiIndexUrl
"Using approved PyPI feed proxy: $pypiIndexUrl" | log

"Installing requirements.txt into venv..." | log
& $venvPip install --index-url $pypiIndexUrl -r requirements.txt
check($lastexitcode)

"Installing build tool into venv..." | log
& $venvPip install --index-url $pypiIndexUrl build
check($lastexitcode)

"Installing pinned uv tool into venv..." | log
$uvVersion = "0.9.5"
& $venvPip install --index-url $pypiIndexUrl "uv==$uvVersion"
check($lastexitcode)

$venvUv = Join-Path $venvDir "Scripts\uv.exe"
if (-not (Test-Path $venvUv)) {
    " ERROR - uv executable missing after installation: $venvUv" | log
    Exit 1
}
"Venv uv: $venvUv" | log

# Warm the uv build path outside the measured run while preserving its normal
# isolated sdist-then-wheel behavior.
$uvPrimeDir = "$scriptDrive\hobl_bin\fast_api_resources\uv_build_prime"
if (Test-Path $uvPrimeDir) {
    Remove-Item -Recurse -Force $uvPrimeDir
}
"Priming uv build cache..." | log
& $venvUv build --out-dir $uvPrimeDir
check($lastexitcode)
if (Test-Path $uvPrimeDir) {
    Remove-Item -Recurse -Force $uvPrimeDir
}

"-- FastAPI prep completed ($logSuffix version)" | log
"Python version: $pythonVersion installed successfully" | log
Exit 0