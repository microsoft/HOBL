# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [ValidateRange(1, 100)]
    [int]$Loops = 5,
    [ValidateSet("none", "external")]
    [string]$ReloadMode = "none",
    [ValidateRange(1024, 65535)]
    [int]$Port = 8765,
    [string]$logFile = ""
)

$scriptDrive = Split-Path -Qualifier $PSScriptRoot
$logDir = "$scriptDrive\hobl_data"
if (-not (Test-Path $logDir)) {
    Write-Host " ERROR - Required directory not found: $logDir" -ForegroundColor Red
    Exit 1
}
if (-not $logFile) { $logFile = "$logDir\fast_api_app_run.log" }
$metricsFile = "$logDir\fast_api_app_results.csv"
$detailDir = "$logDir\fast_api_app_detail"

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

Set-Content -Path $logFile -Encoding utf8 "-- FastAPI app run started"

$toolsDir = "$scriptDrive\hobl_bin\fast_api_app_tools\.venv"
$toolsPython = Join-Path $toolsDir "Scripts\python.exe"
$toolsUv = Join-Path $toolsDir "Scripts\uv.exe"
foreach ($required in @($toolsPython, $toolsUv)) {
    if (-not (Test-Path $required)) {
        " ERROR - Prep artifact missing: $required. Re-prep required." | log
        Exit 1
    }
}

$osInfo = Get-CimInstance Win32_OperatingSystem
$processorArch = $env:PROCESSOR_ARCHITECTURE
if ($osInfo.OSArchitecture -eq "64-bit" -and $processorArch -eq "AMD64") {
    $pythonVersion = "3.12.10"
} elseif ($osInfo.OSArchitecture -match "ARM" -or $processorArch -match "ARM") {
    $pythonVersion = "3.12.10-arm"
} else {
    " ERROR - Unsupported architecture: $($osInfo.OSArchitecture) ($processorArch)" | log
    Exit 1
}
$env:PYENV_VERSION = $pythonVersion
$pyenvBin = "$env:USERPROFILE\.pyenv\pyenv-win\bin"
$pyenvShims = "$env:USERPROFILE\.pyenv\pyenv-win\shims"
$env:PATH = "$pyenvBin;$pyenvShims;" + $env:PATH
if (-not (Get-Command pyenv -ErrorAction SilentlyContinue)) {
    " ERROR - pyenv is not available. Re-prep required." | log
    Exit 1
}
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
$reportedVersion = & $pyenvPython --version 2>&1
if ($reportedVersion -ne "Python 3.12.10") {
    " ERROR - Expected Python 3.12.10 from $pythonVersion, got: $reportedVersion" | log
    Exit 1
}

$appDir = "$scriptDrive\hobl_bin\fast_api_app_workload"
$harness = Join-Path $appDir "benchmark_inner_loop.py"
if (-not (Test-Path $harness)) {
    " ERROR - Benchmark harness not found: $harness" | log
    Exit 1
}
if (Test-Path $detailDir) {
    Remove-Item -Recurse -Force $detailDir
}
New-Item -ItemType Directory -Path $detailDir | Out-Null

$harnessLog = "$logDir\fast_api_app_harness.log"
"Detailed output: $detailDir" | log
"Harness output: $harnessLog" | log
& $toolsPython $harness `
    --output $detailDir `
    --uv $toolsUv `
    --python $pyenvPython `
    --loops $Loops `
    --port $Port `
    --reload-mode $ReloadMode *> $harnessLog
$harnessExitCode = $LASTEXITCODE
if ($harnessExitCode -ne 0) {
    " ERROR - FastAPI app benchmark failed. See $harnessLog for details." | log
    Exit $harnessExitCode
}

$detailMetrics = Join-Path $detailDir "metrics.csv"
if (-not (Test-Path $detailMetrics)) {
    " ERROR - Harness did not produce metrics: $detailMetrics" | log
    Exit 1
}
Copy-Item $detailMetrics $metricsFile -Force

"" | log
"========================================" | log
"FastAPI Application Developer Metrics" | log
"========================================" | log
Get-Content $metricsFile | ForEach-Object { $_ | log }
"========================================" | log
"Metrics saved to: $metricsFile" | log
Exit 0
