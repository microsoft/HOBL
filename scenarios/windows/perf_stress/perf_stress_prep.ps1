# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# perf_stress prep script - installs pyenv + Python + numpy/psutil on DUT
# Follows the same pattern as pytorch_inf_prep.ps1

param(
    [string]$logFile = ""
)

$scriptDrive = Split-Path -Qualifier $PSScriptRoot
if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\perf_stress_prep.log" }

# Ensure execution policy allows modules like Microsoft.PowerShell.Archive (needed by pyenv install)
$executionPolicy = Get-ExecutionPolicy -Scope Process
if ($executionPolicy -eq "Restricted" -or $executionPolicy -eq "Undefined") {
    Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process -Force -ErrorAction Stop
}

function log($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$timestamp $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -ErrorAction SilentlyContinue
}

function checkCmd($cmd, $desc) {
    $result = & cmd /c $cmd 2>&1
    if ($LASTEXITCODE -ne 0) {
        log " ERROR - $desc failed: $result"
        return $false
    }
    log "$desc : OK"
    return $true
}

# --- Detect architecture ---
$arch = (Get-CimInstance Win32_Processor).Architecture
if ($arch -eq 12) {
    $pythonVersion = "3.12.10-arm"
    log "Detected ARM64 architecture, using Python $pythonVersion"
} else {
    $pythonVersion = "3.12.10"
    log "Detected x64 architecture, using Python $pythonVersion"
}

# --- Install pyenv-win if not present ---
$pyenvRoot = "$env:USERPROFILE\.pyenv\pyenv-win"
$pyenvBin = "$pyenvRoot\bin\pyenv.bat"

if (-not (Test-Path $pyenvBin)) {
    log "Installing pyenv-win..."
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "$env:TEMP\install-pyenv-win.ps1"
        & "$env:TEMP\install-pyenv-win.ps1"
        Remove-Item "$env:TEMP\install-pyenv-win.ps1" -Force -ErrorAction SilentlyContinue
    } catch {
        log " ERROR - pyenv-win installation failed: $_"
        exit 1
    }
} else {
    log "pyenv-win already installed at $pyenvRoot"
}

# --- Set PATH for pyenv ---
$pyenvShims = "$pyenvRoot\shims"
$pyenvBinDir = "$pyenvRoot\bin"

# Add pyenv to current session PATH (at front)
$pathParts = $env:PATH -split ";"
$newParts = @($pyenvShims, $pyenvBinDir) + ($pathParts | Where-Object { $_ -ne $pyenvShims -and $_ -ne $pyenvBinDir -and $_ -ne "" })
$env:PATH = ($newParts -join ";")

# Persist pyenv PATH for future sessions (User scope)
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$pyenvShims*") {
    [Environment]::SetEnvironmentVariable("PATH", "$pyenvShims;$pyenvBinDir;$userPath", "User")
    log "Added pyenv to User PATH"
}

# --- Install Python via pyenv ---
log "Installing Python $pythonVersion via pyenv..."
$pyenvExe = "$pyenvBinDir\pyenv.bat"
& $pyenvExe install $pythonVersion -f 2>&1 | ForEach-Object { log "  pyenv: $_" }
& $pyenvExe global $pythonVersion 2>&1 | ForEach-Object { log "  pyenv: $_" }

# Rehash shims
& $pyenvExe rehash 2>&1 | Out-Null

# --- Verify Python ---
$pythonExeRaw = & $pyenvExe which python 2>$null
if ($pythonExeRaw) {
    $pythonExe = $pythonExeRaw.Trim()
    if (Test-Path $pythonExe) {
        $pyVer = & $pythonExe --version 2>&1
        log "Python verified: $pythonExe ($pyVer)"
    } else {
        log " ERROR - pyenv which python returned path that doesn't exist: $pythonExe"
        exit 1
    }
} else {
    log " ERROR - pyenv which python failed"
    exit 1
}

# --- Install required pip packages ---
log "Installing numpy and psutil via pip..."
& $pythonExe -m pip install --upgrade pip 2>&1 | ForEach-Object { log "  pip: $_" }
& $pythonExe -m pip install numpy psutil 2>&1 | ForEach-Object { log "  pip: $_" }

# --- Verify imports ---
log "Verifying numpy and psutil imports..."
$verifyResult = & $pythonExe -c "import numpy; import psutil; print(f'numpy={numpy.__version__}, psutil={psutil.__version__}')" 2>&1
if ($LASTEXITCODE -eq 0) {
    log "Verification passed: $verifyResult"
} else {
    log " ERROR - Import verification failed: $verifyResult"
    exit 1
}

log "perf_stress prep completed successfully."
