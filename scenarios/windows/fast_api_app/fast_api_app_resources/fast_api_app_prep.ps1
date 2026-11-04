# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = ""
)

$scriptDrive = Split-Path -Qualifier $PSScriptRoot
$logDir = "$scriptDrive\hobl_data"
$binDir = "$scriptDrive\hobl_bin"
if (-not (Test-Path $logDir) -or -not (Test-Path $binDir)) {
    Write-Host " ERROR - Required HOBL directories were not found on $scriptDrive" -ForegroundColor Red
    Exit 1
}
if (-not $logFile) { $logFile = "$logDir\fast_api_app_prep.log" }

$executionPolicy = Get-ExecutionPolicy -Scope Process
if ($executionPolicy -eq "Restricted" -or $executionPolicy -eq "Undefined") {
    Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process -Force -ErrorAction Stop
}

function log {
    [CmdletBinding()] Param([Parameter(ValueFromPipeline)] $msg)
    process {
        if ($msg -Match " ERROR - ") {
            Write-Host $msg -ForegroundColor Red
        } else {
            Write-Host $msg
        }
        Add-Content -Path $logFile -Encoding utf8 "$msg"
    }
}

function check {
    param([int]$Code, [string]$Action)
    if ($Code -ne 0) {
        " ERROR - $Action failed with exit code $Code." | log
        Exit $Code
    }
}

function Find-VsWhere {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"),
        (Join-Path $env:ProgramFiles "Microsoft Visual Studio\Installer\vswhere.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }
    return $null
}

function Get-Arm64VisualStudio {
    $vswhere = Find-VsWhere
    if (-not $vswhere) { return $null }
    $path = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.ARM64 -property installationPath
    if ($LASTEXITCODE -eq 0 -and $path) {
        return $path.Trim()
    }
    return $null
}

function Install-Arm64VisualStudio {
    $existing = Get-Arm64VisualStudio
    if ($existing) {
        "Found Visual Studio ARM64 tools at: $existing" | log
        return
    }

    $vsConfig = Join-Path $PSScriptRoot ".vsconfig_arm64"
    if (-not (Test-Path $vsConfig)) {
        " ERROR - ARM64 Visual Studio configuration not found: $vsConfig" | log
        Exit 1
    }
    $installer = Join-Path $env:TEMP "fast_api_app_vs_community.exe"
    "Installing Visual Studio ARM64 native tools using: $vsConfig" | log
    Invoke-WebRequest -Uri "https://aka.ms/vs/17/release/vs_community.exe" -OutFile $installer
    try {
        $process = Start-Process -FilePath $installer -ArgumentList @(
            "--quiet", "--wait", "--norestart", "--config", "`"$vsConfig`""
        ) -Wait -PassThru
        if ($process.ExitCode -ne 0 -and $process.ExitCode -ne 3010) {
            " ERROR - Visual Studio installer failed with exit code $($process.ExitCode)." | log
            Exit $process.ExitCode
        }
    } finally {
        if (Test-Path $installer) {
            Remove-Item $installer -Force
        }
    }
    $installed = Get-Arm64VisualStudio
    if (-not $installed) {
        " ERROR - Visual Studio ARM64 tools were not found after installation." | log
        Exit 1
    }
    "Found Visual Studio ARM64 tools at: $installed" | log
}

Set-Content -Path $logFile -Encoding utf8 "-- FastAPI app prep started"

$osInfo = Get-CimInstance Win32_OperatingSystem
$processorArch = $env:PROCESSOR_ARCHITECTURE
if ($osInfo.OSArchitecture -eq "64-bit" -and $processorArch -eq "AMD64") {
    $pythonVersion = "3.12.10"
    $isArm64 = $false
} elseif ($osInfo.OSArchitecture -match "ARM" -or $processorArch -match "ARM") {
    $pythonVersion = "3.12.10-arm"
    $isArm64 = $true
} else {
    " ERROR - Unsupported architecture: $($osInfo.OSArchitecture) ($processorArch)" | log
    Exit 1
}
"Using Python distribution: $pythonVersion" | log

if (-not (Get-Command pyenv -ErrorAction SilentlyContinue)) {
    $installer = Join-Path $env:TEMP "install-pyenv-win.ps1"
    "Installing pyenv-win..." | log
    Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile $installer
    & $installer
    check $LASTEXITCODE "pyenv-win installation"
    Remove-Item $installer -Force
}

$pyenvBin = "$env:USERPROFILE\.pyenv\pyenv-win\bin"
$pyenvShims = "$env:USERPROFILE\.pyenv\pyenv-win\shims"
$env:PATH = "$pyenvBin;$pyenvShims;" + $env:PATH
if (-not (Get-Command pyenv -ErrorAction SilentlyContinue)) {
    " ERROR - pyenv was not found after installation." | log
    Exit 1
}

$installedVersions = (pyenv versions --bare 2>$null) -split "`n" | ForEach-Object { $_.Trim() }
if ($installedVersions -notcontains $pythonVersion) {
    "Installing Python $pythonVersion via pyenv..." | log
    pyenv install $pythonVersion
    check $LASTEXITCODE "Python $pythonVersion installation"
} else {
    "Python $pythonVersion already installed via pyenv - preserving existing install" | log
}
$env:PYENV_VERSION = $pythonVersion

$pyenvPythonRaw = pyenv which python 2>$null
if (-not $pyenvPythonRaw) {
    " ERROR - pyenv which python returned no path." | log
    Exit 1
}
$pyenvPython = $pyenvPythonRaw.Trim()
if (-not (Test-Path $pyenvPython)) {
    " ERROR - pyenv python not found at: $pyenvPython" | log
    Exit 1
}
"Using base Python: $pyenvPython" | log

if ($isArm64) {
    Install-Arm64VisualStudio
}

$toolsDir = "$binDir\fast_api_app_tools\.venv"
if (Test-Path $toolsDir) {
    Remove-Item -Recurse -Force $toolsDir
}
& $pyenvPython -m venv $toolsDir
check $LASTEXITCODE "Tools venv creation"

$toolsPip = Join-Path $toolsDir "Scripts\pip.exe"
$toolsPython = Join-Path $toolsDir "Scripts\python.exe"
$toolsUv = Join-Path $toolsDir "Scripts\uv.exe"
$indexUrl = "https://packagefeedproxy.microsoft.io/pypi/simple"
& $toolsPip install --index-url $indexUrl "uv==0.9.5" "psutil>=7,<8"
check $LASTEXITCODE "Pinned benchmark tool installation"

$appDir = Join-Path $binDir "fast_api_app_workload"
if (-not (Test-Path (Join-Path $appDir "uv.lock"))) {
    " ERROR - Shared FastAPI app workload is missing from: $appDir" | log
    Exit 1
}
Set-Location $appDir
$appVenv = Join-Path $appDir ".venv"
if (Test-Path $appVenv) {
    Remove-Item -Recurse -Force $appVenv
}
"Priming the locked uv cache outside measurement..." | log
& $toolsUv sync --frozen --python $pyenvPython
check $LASTEXITCODE "Locked app sync"

$appPython = Join-Path $appVenv "Scripts\python.exe"
& $appPython -c "import fastapi, httptools, pytest, watchfiles; print(fastapi.__version__)"
check $LASTEXITCODE "App dependency validation"
Remove-Item -Recurse -Force $appVenv

"-- FastAPI app prep completed" | log
Exit 0
