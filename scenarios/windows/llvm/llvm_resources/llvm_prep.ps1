# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = "",
    [string]$InstallerPath = "",
    [string]$InstallerSha256 = "",
    [string]$CompilerVersion = "21.1.8",
    [switch]$AllowUnsignedInstaller
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Check and set execution policy if needed
# This fixes the following error when running pyenv install:
# Microsoft.PowerShell.Archive\Expand-Archive : The module 'Microsoft.PowerShell.Archive' could not be loaded. For more
# information, run 'Import-Module Microsoft.PowerShell.Archive'.
$executionPolicy = Get-ExecutionPolicy -Scope Process
if ($executionPolicy -eq "Restricted" -or $executionPolicy -eq "Undefined") {
    Write-Host "Setting execution policy to Unrestricted for Process..." -ForegroundColor Yellow
    try {
        Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process -Force -ErrorAction Stop
        Write-Host "Execution policy set successfully" -ForegroundColor Green
    } catch {
        Write-Host " ERROR - Failed to set execution policy" -ForegroundColor Red
        Write-Host "Please run as administrator or manually set execution policy with:" -ForegroundColor Yellow
        Write-Host "  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Cyan
        Exit 1
    }
}

# Configuration
$llvmVersion = "llvmorg-21.1.8"
$llvmReleaseVersion = "21.1.8"
$scriptDrive = Split-Path -Qualifier $PSScriptRoot
if (-not (Test-Path "$scriptDrive\hobl_data")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_data" -ForegroundColor Red
    Exit 1
}
if (-not (Test-Path "$scriptDrive\hobl_bin")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_bin" -ForegroundColor Red
    Exit 1
}
if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\llvm_prep.log" }
$llvmSourceDir = "$scriptDrive\llvm-project"
$llvmBuildDir = "$scriptDrive\build_llvm"
$llvmInstallDir = "$env:ProgramFiles\llvm"

# Determine processor architecture
$osInfo = Get-CimInstance Win32_OperatingSystem
$arch = $osInfo.OSArchitecture
$processorArch = $env:PROCESSOR_ARCHITECTURE

if ($arch -eq "64-bit" -and $processorArch -eq "AMD64") {
    $isARM64 = $false
    $vsArchParam = "x64"
    $vsHostArchParam = "x64"
    $logSuffix = "x64"
    $vsProduct = "Community"
    $pythonVersion = "3.12.10"
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    $isARM64 = $true
    $vsArchParam = "arm64"
    $vsHostArchParam = "arm64"
    $logSuffix = "ARM64"
    $vsProduct = "Community"
    $pythonVersion = "3.12.10-arm"
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

function getVSVersion {
    param([string]$product)

    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) {
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

function installVisualStudio {
    $scriptDir = Split-Path -Parent $PSCommandPath

    $installerUrl = "https://aka.ms/vs/17/release/vs_community.exe"
    $installerPath = "$env:TEMP\vs_community.exe"
    $productName = "VS Community"
    "-- Installing $productName 2022 ($logSuffix)" | log

    if ($isARM64) {
        $vsconfigPath = Join-Path $scriptDir ".vsconfig_arm64"
    } else {
        $vsconfigPath = Join-Path $scriptDir ".vsconfig_x64"
    }

    "Using .vsconfig file: $vsconfigPath" | log
    if (-not (Test-Path $vsconfigPath)) {
        " ERROR - .vsconfig file not found: $vsconfigPath" | log
        return $false
    }

    $existingVS = getVSVersion -product $vsProduct
    if ($existingVS -and $existingVS.Path) {
        $sharedInstaller = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\setup.exe"

        if (Test-Path $sharedInstaller) {
            "Found existing Visual Studio installer at: $sharedInstaller" | log
            $installerPath = $sharedInstaller
        } else {
            "Downloading new installer..." | log
            try {
                Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
            } catch {
                " ERROR - Failed to download $productName installer: $($_.Exception.Message)" | log
                return $false
            }
        }

        $installArgs = @(
            "modify"
            "--installPath", "`"$($existingVS.Path)`""
            "--quiet"
            "--config", "`"$vsconfigPath`""
        )
    } else {
        "No existing VS installation found, downloading new installer..." | log
        try {
            Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
        } catch {
            " ERROR - Failed to download $productName installer: $($_.Exception.Message)" | log
            return $false
        }

        $installArgs = @(
            "install"
            "--quiet"
            "--wait"
            "--config", "`"$vsconfigPath`""
        )
    }

    "$productName install/modify args: $($installArgs -join ' ')" | log
    "Starting $productName installation (this will wait for completion)..." | log

    # Redirect VS installer output to separate log files to keep main log clean
    $logDirectory = Split-Path -Path $logFile -Parent
    $vsStdOut = Join-Path $logDirectory "vs_install_llvm_stdout_$($logSuffix.ToLower()).log"
    $vsStdErr = Join-Path $logDirectory "vs_install_llvm_stderr_$($logSuffix.ToLower()).log"
    "VS installer stdout redirected to: $vsStdOut" | log
    "VS installer stderr redirected to: $vsStdErr" | log

    try {
        $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru -RedirectStandardOutput $vsStdOut -RedirectStandardError $vsStdErr
        $exitCode = $process.ExitCode

        "$productName installer completed with exit code: $exitCode" | log

        if ($exitCode -eq 0 -or $exitCode -eq 3010) {
            if ($exitCode -eq 3010) {
                "Installation successful but may require reboot" | log
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
        if ($installerPath -like "$env:TEMP\*" -and (Test-Path $installerPath)) {
            Remove-Item $installerPath -ErrorAction SilentlyContinue
        }
    }
}

function installLLVMPrebuilt {
    if (Test-Path "$llvmInstallDir\bin\clang.exe") {
        "LLVM pre-built binaries already installed at $llvmInstallDir" | log
        return
    }

    if ($isARM64) {
        "-- Installing LLVM $llvmReleaseVersion pre-built binaries for ARM64" | log
        $llvmUrl = "https://github.com/llvm/llvm-project/releases/download/$llvmVersion/LLVM-$llvmReleaseVersion-woa64.exe"
    } else {
        "-- Installing LLVM $llvmReleaseVersion pre-built binaries for x64" | log
        $llvmUrl = "https://github.com/llvm/llvm-project/releases/download/$llvmVersion/LLVM-$llvmReleaseVersion-win64.exe"
    }

    $llvmInstaller = "$env:TEMP\LLVM-$llvmReleaseVersion-installer.exe"

    try {
        "Downloading LLVM $llvmReleaseVersion installer..." | log
        Invoke-WebRequest -Uri $llvmUrl -OutFile $llvmInstaller -UseBasicParsing

        "Installing LLVM to $llvmInstallDir..." | log
        Start-Process $llvmInstaller -ArgumentList "/S /D=$llvmInstallDir" -Wait

        Remove-Item $llvmInstaller -Force -ErrorAction SilentlyContinue

        if (Test-Path "$llvmInstallDir\bin\clang.exe") {
            "✓ LLVM pre-built binaries installed successfully" | log
        } else {
            " ERROR - LLVM installation verification failed - clang.exe not found at $llvmInstallDir\bin\clang.exe" | log
            Exit 1
        }
    } catch {
        " ERROR - Failed to install LLVM pre-built binaries: $($_.Exception.Message)" | log
        Exit 1
    }
}



# ============================================================================
# Main Prep Logic
# ============================================================================
Set-Content -Path $logFile -encoding utf8 "-- llvm prep started ($logSuffix version)"

"=========================================" | log
"LLVM Prep Script for Windows" | log
"Version: $llvmVersion" | log
"Architecture: $logSuffix" | log
"=========================================" | log

"Detected architecture: $arch (Processor: $processorArch)" | log

# Validate the supplied artifact before any installers/toolchain changes.
try {
    . (Join-Path $PSScriptRoot 'llvm_toolchain.ps1')
    if ($InstallerPath) {
        Assert-LlvmMsi -Path $InstallerPath -Sha256 $InstallerSha256 -Version $CompilerVersion -AllowUnsigned:$AllowUnsignedInstaller | Out-Null
    } elseif ($InstallerSha256 -or $AllowUnsignedInstaller -or $CompilerVersion -ne $llvmReleaseVersion) {
        throw 'Custom compiler options require InstallerPath.'
    } elseif (Test-Path -LiteralPath (Join-Path $llvmInstallDir 'bin\clang.exe')) {
        # Never silently reuse or downgrade a manually installed/custom compiler.
        try {
            Get-LlvmCompilerInfo -InstallDir $llvmInstallDir -ExpectedVersion $llvmReleaseVersion | Out-Null
        } catch {
            throw "Existing LLVM does not match the default $llvmReleaseVersion toolchain. Select the approved MSI parameters, or have the DUT owner restore the default compiler before prep. $($_.Exception.Message)"
        }
    }
} catch {
    " ERROR - $($_.Exception.Message)" | log
    Exit 1
}

# Refresh PATH
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

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

# --- Install VC Runtime Redistributable ---
"-- Installing VC Runtime Redistributable" | log
if ($isARM64) {
    winget install --id=Microsoft.VCRedist.2015+.arm64 --source winget --silent --accept-package-agreements --accept-source-agreements --scope=machine
} else {
    winget install --id=Microsoft.VCRedist.2015+.x64 --source winget --silent --accept-package-agreements --accept-source-agreements --scope=machine
}
checkWinget($lastexitcode)

# --- Install Git ---
"-- Installing Git" | log
winget install --id Git.Git --source winget --silent --accept-source-agreements --accept-package-agreements
checkWinget($lastexitcode)
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# --- Install CMake ---
"-- Installing CMake" | log
winget install --id Kitware.CMake --version 4.1.1 --source winget --silent --accept-source-agreements --accept-package-agreements
checkWinget($lastexitcode)
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# --- Install Ninja ---
"-- Installing Ninja" | log
winget install --id Ninja-build.Ninja --version 1.13.2 --source winget --silent --accept-source-agreements --accept-package-agreements
checkWinget($lastexitcode)
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# --- Install Python via pyenv-win ---
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

    # Check PATH
    "`n1. Python in PATH:" | log
    try {
        $pathPython = Get-Command python -ErrorAction SilentlyContinue
        if ($pathPython) {
            "  Found: $($pathPython.Source)" | log
            & python --version 2>&1 | log
        } else {
            "  No python in PATH" | log
        }
    } catch {
        "  No python in PATH" | log
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

# Verify pyenv Python is being used
"`n=== Python Resolution Verification ===" | log
$whichPython = Get-Command python -ErrorAction SilentlyContinue
if ($whichPython) {
    "Resolved python.exe: $($whichPython.Source)" | log
    if ($whichPython.Source -like "*pyenv*") {
        "SUCCESS: pyenv Python is being used" | log
    } else {
        "WARNING: Non-pyenv Python is being used" | log
        "This may cause version conflicts" | log
    }
} else {
    " ERROR - No python found in PATH" | log
    Exit 1
}

"Verifying Python installation..." | log
pyenv versions | log

# Final verification that correct Python version is active
"Final Python version verification..." | log
$currentPythonVersion = & python --version 2>&1
"Current Python version: $currentPythonVersion" | log

$expectedVersionPattern = $pythonVersion -replace "-arm", ""
if ($currentPythonVersion -like "*$expectedVersionPattern*") {
    "Correct Python version ($pythonVersion) is active" | log
} else {
    " ERROR - Wrong Python version active. Expected: $pythonVersion, Got: $currentPythonVersion" | log
    "Please check pyenv configuration" | log
    Exit 1
}

# --- Install Visual Studio ---
"-- Checking Visual Studio $vsProduct" | log
$vsBefore = getVSVersion -product $vsProduct
if ($vsBefore) {
    "Existing $vsProduct installation found:" | log
    "  Version: $($vsBefore.Version)" | log
    "  Path: $($vsBefore.Path)" | log
} else {
    "No existing $vsProduct installation found" | log
}

if (-not (installVisualStudio)) {
    " ERROR - Visual Studio $vsProduct installation failed" | log
    Exit 1
}

$vsAfter = getVSVersion -product $vsProduct
if ($vsAfter) {
    "Current $vsProduct installation:" | log
    "  Version: $($vsAfter.Version)" | log
    "  Path: $($vsAfter.Path)" | log
} else {
    " ERROR - $vsProduct not found after installation" | log
    Exit 1
}

# --- Install the compiler separately from the LLVM source benchmark version ---
try {
    if ($InstallerPath) {
        # Always process an explicitly selected MSI during prep. The legacy
        # 'any clang exists' shortcut must not skip an upgrade/custom build.
        $msiLog = Join-Path (Split-Path $logFile -Parent) "llvm_msi_install_$($logSuffix.ToLower()).log"
        Install-LlvmMsi -Path $InstallerPath -Sha256 $InstallerSha256 -Version $CompilerVersion -InstallDir $llvmInstallDir -InstallLog $msiLog -AllowUnsigned:$AllowUnsignedInstaller
    } else {
        "-- Installing pre-built LLVM $llvmReleaseVersion" | log
        installLLVMPrebuilt
    }
    $compiler = Get-LlvmCompilerInfo -InstallDir $llvmInstallDir -ExpectedVersion $CompilerVersion
    "Using LLVM compiler $($compiler.Version) ($($compiler.Architecture)): $($compiler.ClangCl)" | log
    if ($InstallerPath) {
        @{ InstallerSha256 = $InstallerSha256; Version = $compiler.Version; ClangSha256 = $compiler.ClangSha256; ClangClSha256 = $compiler.ClangClSha256 } |
            ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'llvm_msi_receipt.json') -Encoding utf8 -ErrorAction Stop
    }
} catch {
    " ERROR - $($_.Exception.Message)" | log
    Exit 1
}

# --- Initialize Visual Studio Developer Command environment ---
"-- Initializing Visual Studio Developer Command environment" | log
$llvmBinPath = "$llvmInstallDir\bin"

$vsInfo = getVSVersion -product $vsProduct
if (-not $vsInfo -or -not $vsInfo.Path) {
    " ERROR - Visual Studio $vsProduct installation not found via vswhere" | log
    Exit 1
}
"Found Visual Studio at: $($vsInfo.Path)" | log

$vsDevCmd = Join-Path $vsInfo.Path "Common7\Tools\VsDevCmd.bat"
if (-not (Test-Path $vsDevCmd)) {
    " ERROR - VsDevCmd.bat not found at: $vsDevCmd" | log
    Exit 1
}
"Using VsDevCmd.bat: $vsDevCmd" | log

# Source VsDevCmd.bat with architecture parameters and import all environment variables
$vsDevCmdArgs = "-arch=$vsArchParam -host_arch=$vsHostArchParam -no_logo"
"Sourcing VsDevCmd.bat with args: $vsDevCmdArgs" | log
cmd /c "`"$vsDevCmd`" $vsDevCmdArgs && set" | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}
"✓ Visual Studio Developer Command environment initialized" | log

# Add LLVM bin to PATH
if (Test-Path $llvmBinPath) {
    $Env:Path = "$llvmBinPath;$Env:Path"
    "✓ LLVM bin added to PATH: $llvmBinPath" | log
} else {
    " ERROR - LLVM bin directory not found: $llvmBinPath" | log
    Exit 1
}

# Verify cl.exe is now available via VsDevCmd environment
$clCheck = Get-Command cl.exe -ErrorAction SilentlyContinue
if ($clCheck) {
    "✓ cl.exe available at: $($clCheck.Source)" | log
} else {
    " ERROR - cl.exe not found in PATH after VsDevCmd initialization" | log
    Exit 1
}

# --- Clone LLVM ---
"-- Cloning LLVM repository ($llvmVersion)" | log
if (Test-Path $llvmSourceDir) {
    "Removing existing LLVM source directory..." | log
    Remove-Item -Path $llvmSourceDir -Recurse -Force
}

git clone --depth 1 --branch $llvmVersion --config core.autocrlf=false https://github.com/llvm/llvm-project.git $llvmSourceDir
check($lastexitcode)
"✓ LLVM source cloned to $llvmSourceDir" | log

# --- Create build directory ---
"-- Creating build directory" | log
if (Test-Path $llvmBuildDir) {
    "Removing existing build directory..." | log
    Remove-Item -Path $llvmBuildDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $llvmBuildDir | Out-Null

# --- Configure CMake ---
"-- Configuring CMake for LLVM ($logSuffix)" | log

# Resolve Python path for CMake's FindPython3
$pythonExe = (pyenv which python 2>$null).Trim()
if ($pythonExe -and (Test-Path $pythonExe)) {
    "Using Python for CMake: $pythonExe" | log
} else {
    " ERROR - Python not found via pyenv for CMake configuration" | log
    Exit 1
}

# Target set matches ProjectD 'Default': AArch64;ARM;X86
# This is sufficient for cross-architecture testing and matches official Apple clang config.
cmake -S "$llvmSourceDir\llvm" -B $llvmBuildDir -G "Ninja" `
    -DCMAKE_BUILD_TYPE=Release `
    -DCMAKE_C_COMPILER="$($compiler.ClangCl)" `
    -DCMAKE_CXX_COMPILER="$($compiler.ClangCl)" `
    -DLLVM_ENABLE_PROJECTS="clang;lld" `
    -DLLVM_TARGETS_TO_BUILD="AArch64;ARM;X86" `
    -DPython3_EXECUTABLE="$pythonExe"
check($lastexitcode)
"✓ CMake configuration complete" | log

"=========================================" | log
"LLVM Prep Complete!" | log
"=========================================" | log
"LLVM source: $llvmSourceDir" | log
"Build directory: $llvmBuildDir" | log
"-- llvm prep completed ($logSuffix version)" | log
Exit 0
