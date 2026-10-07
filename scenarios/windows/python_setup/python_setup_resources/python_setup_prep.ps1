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
if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\python_setup_prep.log" }

# Set execution policy for current process (required for pyenv's Expand-Archive)
$executionPolicy = Get-ExecutionPolicy -Scope Process
if ($executionPolicy -eq "Restricted" -or $executionPolicy -eq "Undefined") {
    Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process -Force -ErrorAction Stop
}

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Determine processor architecture
$osInfo = Get-CimInstance Win32_OperatingSystem
$arch = $osInfo.OSArchitecture
$processorArch = $env:PROCESSOR_ARCHITECTURE

if ($arch -eq "64-bit" -and $processorArch -eq "AMD64") {
    # $isARM64 = $false
    $logSuffix = "x64"
    $pythonVersion = "3.12.10"
    
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    # $isARM64 = $true
    $logSuffix = "ARM64"
    $pythonVersion = "3.12.10-arm"    
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

# --- Install pyenv-win ---
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

# --- Optimize PATH: pyenv shims before WindowsApps ---
"Optimizing Python PATH priority permanently..." | log

$pyenvPaths = @(
    "$env:USERPROFILE\.pyenv\pyenv-win\shims",
    "$env:USERPROFILE\.pyenv\pyenv-win\bin"
)

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

    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

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
        "Updating User PATH permanently..." | log
        [System.Environment]::SetEnvironmentVariable('PATH', $newUserPath, 'User')
        "New User PATH length: $($newUserPath.Length) characters" | log

        if ($isAdmin) {
            "Running as Administrator - also updating Machine PATH" | log
            $machinePath = [System.Environment]::GetEnvironmentVariable('PATH', 'Machine')
            $machineEntries = Get-PathEntries -PathValue $machinePath
            $cleanMachineEntries = New-Object System.Collections.Generic.List[string]
            $cleanMachineSeen = @{}

            foreach ($entry in $machineEntries) {
                if ($pyenvPathKeys.ContainsKey($entry.ToLowerInvariant())) { continue }
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

        $machinePath = [System.Environment]::GetEnvironmentVariable('PATH', 'Machine')
        $env:PATH = $machinePath + ";" + $newUserPath

        "PATH optimization complete!" | log
        "pyenv paths have FIRST priority" | log
        if ($hadWindowsAppsInUserPath -or (Test-Path $windowsAppsCanonical)) {
            "Windows Store Python moved to LAST priority" | log
        }
    } catch {
        " ERROR - Failed to update PATH: $($_.Exception.Message)" | log
        Exit 1
    }
}

Set-OptimizedPathOrder

# --- Install Python via pyenv (conditional — DO NOT use -f) ---
# Force-reinstall (`-f`) wipes the pyenv version directory including any packages
# installed by other scenarios that share this Python version. Multiple scenarios
# use 3.12.10-arm, so we only install when truly missing.
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

# --- Verify Python installation ---
function Find-AllPython {
    "=== Python Detection Report ===" | log
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
    "`n2. pyenv-win managed Python:" | log
    if (Get-Command pyenv -ErrorAction SilentlyContinue) {
        "  pyenv is available" | log
        pyenv versions | log
    } else {
        "  pyenv not found" | log
    }
}

Find-AllPython

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

# # --- Copy resources (always overwrite to pick up script changes) ---
# "-- Setting up pytorch_inf_resources in $scriptDrive\hobl_bin\pytorch_inf_resources" | log
# if ($PSScriptRoot -ne "$scriptDrive\hobl_bin\pytorch_inf_resources") {
#     if (-not (Test-Path "$scriptDrive\hobl_bin\pytorch_inf_resources")) {
#         New-Item -ItemType Directory -Force -Path "$scriptDrive\hobl_bin\pytorch_inf_resources" | Out-Null
#     }
#     Copy-Item -Path "$PSScriptRoot\*" -Destination "$scriptDrive\hobl_bin\pytorch_inf_resources" -Exclude "*.ps1" -Recurse -Force
#     "Resources copied from $PSScriptRoot" | log
# } else {
#     "Already running from target directory, skipping copy" | log
# }

# Set-Location "$scriptDrive\hobl_bin\pytorch_inf_resources"
# checkCmd($?)

# --- Install Python packages ---
$currentPythonVersion = & python --version 2>&1
"Current Python version: $currentPythonVersion" | log

$expectedVersionPattern = $pythonVersion -replace "-arm", ""
if ($currentPythonVersion -like "*$expectedVersionPattern*") {
    "Correct Python version ($pythonVersion) is active" | log
} else {
    " ERROR - Wrong Python version active. Expected: $pythonVersion, Got: $currentPythonVersion" | log
    Exit 1
}


"-- python setup prep completed ($logSuffix version)" | log
Exit 0