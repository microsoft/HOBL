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
if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\pytorch_inf_v2_prep.log" }

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

# Python 3.14.8 per the pytorch_inf_v2 design (config.py PYTHON_VERSION).
# N1X (Windows Arm64) ships an NVIDIA GPU, so the GPU-first design applies
# on both architectures -- CPU is a separate, explicitly-opted-in fallback,
# never silently substituted.
if ($arch -eq "64-bit" -and $processorArch -eq "AMD64") {
    $isARM64 = $false
    $logSuffix = "x64"
    $pythonVersion = "3.14.8"
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    $isARM64 = $true
    $logSuffix = "ARM64"
    $pythonVersion = "3.14.8-arm"
} else {
    Write-Host " ERROR - Unsupported architecture: $arch (Processor: $processorArch)" -ForegroundColor Red
    Exit 1
}

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

Set-Content -Path $logFile -encoding utf8 "-- pytorch_inf_v2 prep started ($logSuffix version)"
"Detected architecture: $arch (Processor: $processorArch)" | log

# --- Install pyenv-win ---
if (-not (Get-Command pyenv -ErrorAction SilentlyContinue)) {
    "Installing pyenv-win for Python version management..." | log
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"
        & "./install-pyenv-win.ps1"
        "pyenv-win installation completed" | log
    } catch {
        " ERROR - Failed to install pyenv-win: $($_.Exception.Message)" | log
        Exit 1
    }
    $Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
} else {
    "pyenv-win already installed" | log
}

# --- Install Python via pyenv (conditional -- DO NOT use -f) ---
# Force-reinstall (`-f`) wipes the pyenv version directory including any
# packages another scenario installed into it. Per copilot-instructions.md,
# always check first and only install when the version is genuinely missing.
#
# pyenv-win resolves installable versions from a bundled, periodically-synced
# ".versions_cache.xml" snapshot rather than a true live python.org query.
# That snapshot can lag behind brand-new CPython patch releases (observed:
# cache dated well before the 3.14.8 release, capping definitions at
# 3.14.5). `pyenv update` is supposed to refresh it, but on this locked-down
# Arm64 build it fails outright (`htmlfile: This command is not supported` --
# the VBScript updater depends on a legacy IE/WScript HTML COM object that is
# blocked by this device's security policy). If the pinned version is
# missing, fall back to installing the official python.org installer
# directly into pyenv's versions directory using the same installer flags
# pyenv-win itself uses, so `pyenv global`/`pyenv which` keep working
# unmodified afterward.
function Install-PyenvPythonWithFallback {
    param([string]$version, [bool]$isArm)

    "Installing Python $version via pyenv (this may take several minutes)..." | log
    $pyenvOutput = (pyenv install $version 2>&1 | Out-String)
    $pyenvOutput | Write-Host
    if ($lastexitcode -eq 0) { return }

    if ($pyenvOutput -notmatch "definition not found") {
        check($lastexitcode)
    }

    " WARNING - pyenv-win's bundled version-definition cache does not include $version (likely stale relative to the upstream release). Attempting 'pyenv update' then retrying..." | log
    pyenv update 2>&1 | Out-String | Write-Host
    $installedAfterUpdate = (pyenv versions --bare 2>$null) -split "`n" | ForEach-Object { $_.Trim() }
    if ($installedAfterUpdate -notcontains $version) {
        pyenv install $version 2>&1 | Out-String | Write-Host
    }
    if ($lastexitcode -eq 0) { return }

    " WARNING - 'pyenv update' did not make $version installable (update itself may be unsupported in this environment). Falling back to a direct python.org installer, placed into pyenv's versions directory so pyenv continues to resolve it normally." | log

    $baseVersion = $version -replace "-arm$", ""
    $archSuffix = if ($isArm) { "arm64" } else { "amd64" }
    $installerName = "python-$baseVersion-$archSuffix.exe"
    $installerUrl = "https://www.python.org/ftp/python/$baseVersion/$installerName"
    $installerPath = Join-Path $env:TEMP $installerName
    # Read from the registry directly (not $env:), since the pyenv-win installer
    # sets these as persistent User variables that a freshly-spawned process may
    # not yet have picked up without a shell/session restart.
    $pyenvRoot = [System.Environment]::GetEnvironmentVariable("PYENV_ROOT", "User")
    if (-not $pyenvRoot) { $pyenvRoot = [System.Environment]::GetEnvironmentVariable("PYENV", "User") }
    if (-not $pyenvRoot) { $pyenvRoot = $env:PYENV_ROOT }
    if (-not $pyenvRoot) { $pyenvRoot = $env:PYENV }
    if (-not $pyenvRoot) { $pyenvRoot = "$env:USERPROFILE\.pyenv\pyenv-win" }
    $targetDir = Join-Path (Join-Path $pyenvRoot "versions") $version

    "Downloading official installer: $installerUrl" | log
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $installerUrl -OutFile $installerPath
    } catch {
        " ERROR - Failed to download $installerUrl : $($_.Exception.Message)" | log
        Exit 1
    }

    if (Test-Path $targetDir) { Remove-Item -Recurse -Force $targetDir }
    "Installing Python $baseVersion directly into $targetDir ..." | log
    $proc = Start-Process -FilePath $installerPath -ArgumentList "/quiet InstallAllUsers=0 Include_launcher=0 Include_test=0 SimpleInstall=1 TargetDir=`"$targetDir`"" -Wait -PassThru
    if ($proc.ExitCode -ne 0 -or -not (Test-Path (Join-Path $targetDir "python.exe"))) {
        " ERROR - Direct python.org installer failed (exit code $($proc.ExitCode)) or did not produce python.exe at $targetDir" | log
        Exit 1
    }
    Remove-Item -Force $installerPath -ErrorAction SilentlyContinue

    & (Join-Path $targetDir "python.exe") -E -s -m ensurepip -U --default-pip | Out-String | Write-Host
    pyenv rehash

    $installedVersionsRetry = (pyenv versions --bare 2>$null) -split "`n" | ForEach-Object { $_.Trim() }
    if ($installedVersionsRetry -notcontains $version) {
        " ERROR - Direct install placed Python at $targetDir but pyenv still does not list $version via 'pyenv versions'." | log
        Exit 1
    }
    "Direct python.org fallback install succeeded; pyenv now recognizes $version." | log
}

$installedVersions = (pyenv versions --bare 2>$null) -split "`n" | ForEach-Object { $_.Trim() }
if ($installedVersions -notcontains $pythonVersion) {
    Install-PyenvPythonWithFallback -version $pythonVersion -isArm $isARM64
} else {
    "Python $pythonVersion already installed via pyenv -- preserving existing install" | log
}

pyenv global $pythonVersion
check($lastexitcode)
pyenv rehash

$currentPythonVersion = (pyenv version 2>$null) -replace '\s.*', ''
if ($currentPythonVersion -ne $pythonVersion) {
    " ERROR - Wrong Python version active. Expected: $pythonVersion, Got: $currentPythonVersion" | log
    Exit 1
}
"Active pyenv Python: $currentPythonVersion" | log

# --- Create per-scenario venv ---
# Packages live in this scenario's private venv, NOT the shared pyenv
# site-packages, so another scenario's `pyenv install`/`pyenv global` cannot
# disturb pytorch_inf_v2's dependencies.
$venvDir = "$scriptDrive\hobl_bin\pytorch_inf_v2_resources\.venv"
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

# Microsoft-managed devices block direct access to public PyPI (CISO Central
# Feed Services policy); resolve pip installs through the approved Microsoft
# feed proxy. requirements_win*.txt also pin this index.
$pypiIndexUrl = "https://packagefeedproxy.microsoft.io/pypi/simple"

if ($isARM64) {
    # --- Arm64 (N1X): verified NVIDIA out-of-tree CUDA torch wheel ---
    # Stock PyTorch does not publish CUDA wheels for win_arm64. NVIDIA's
    # index is not a standard PyPI/pytorch.org mirror, so the wheel is
    # downloaded explicitly and its SHA256 is verified against config.py's
    # pinned hash before install -- fail fast on any mismatch, never
    # silently proceed (mirrors the signed-installer verification pattern
    # used elsewhere in HOBL, e.g. the llvm scenario).
    $configValues = & $venvPython -c "import config; print(config.TORCH_ARM64_INDEX_URL); print(config.TORCH_ARM64_WHEEL_NAME); print(config.TORCH_ARM64_SHA256_CP314)"
    $torchIndexUrl, $torchWheelName, $expectedSha256 = $configValues
    # The '+' in the local-version segment (e.g. "+cu134") must be percent-encoded
    # as %2B in the URL path -- NVIDIA's index serves the literal '+' as 404 Not
    # Found (confirmed against https://pypi.nvidia.com/nvtorch_oot/torch/, whose
    # own index hrefs use %2B). pip/standard package indices handle this
    # transparently; a raw Invoke-WebRequest does not, so encode explicitly.
    $torchWheelNameEncoded = $torchWheelName -replace '\+', '%2B'
    $wheelUrl = "$torchIndexUrl$torchWheelNameEncoded"
    $wheelPath = Join-Path $env:TEMP $torchWheelName
    "Downloading Arm64 NVIDIA torch wheel from $wheelUrl" | log
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $wheelUrl -OutFile $wheelPath
    } catch {
        " ERROR - Failed to download torch wheel: $($_.Exception.Message)" | log
        Exit 1
    }
    $actualSha256 = (Get-FileHash -Path $wheelPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha256 -ne $expectedSha256.ToLowerInvariant()) {
        " ERROR - SHA256 mismatch for $torchWheelName" | log
        " ERROR - Expected: $expectedSha256" | log
        " ERROR - Actual:   $actualSha256" | log
        " ERROR - Refusing to install an unverified wheel." | log
        Remove-Item -Force $wheelPath -ErrorAction SilentlyContinue
        Exit 1
    }
    "SHA256 verified for $torchWheelName" | log

    "-- Installing verified torch wheel into venv" | log
    & $venvPip install --index-url $pypiIndexUrl $wheelPath
    check($lastexitcode)

    "-- Installing remaining dependencies from requirements_win_arm64.txt into venv" | log
    & $venvPip install -r requirements_win_arm64.txt
    check($lastexitcode)
} else {
    "-- Installing Python packages from requirements_win.txt into venv" | log
    & $venvPip install -r requirements_win.txt
    check($lastexitcode)
}

# --- Download model weights (using venv python so torch is available) ---
# Cache/download happens here, outside any scored time in the run script.
"-- Downloading portable + quantized headline model weights" | log
& $venvPython run_benchmark.py --setup --model-tier portable
check($lastexitcode)
& $venvPython run_benchmark.py --setup --model-tier quantized
check($lastexitcode)

"-- pytorch_inf_v2 prep completed ($logSuffix version)" | log
Exit 0
