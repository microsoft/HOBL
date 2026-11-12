# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

$scriptDrive = Split-Path -Qualifier $PSScriptRoot

function log {
    [CmdletBinding()] Param([Parameter(ValueFromPipeline)] $msg)
    process {
        if ($msg -Match " ERROR - ") {
            Write-Host $msg -ForegroundColor Red
        } else {
            Write-Host $msg
        }
    }
}

"-- pytorch_inf_v2 teardown started" | log

$osInfo = Get-CimInstance Win32_OperatingSystem
$arch = $osInfo.OSArchitecture
$processorArch = $env:PROCESSOR_ARCHITECTURE

if ($arch -eq "64-bit" -and $processorArch -eq "AMD64") {
    $pythonVersion = "3.14.8"
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    $pythonVersion = "3.14.8-arm"
} else {
    " ERROR - Unsupported architecture: $arch (Processor: $processorArch)" | log
    Exit 1
}

# Ensure pyenv shims are in PATH for this session
$pyenvShims = "$env:USERPROFILE\.pyenv\pyenv-win\shims"
$pyenvBin = "$env:USERPROFILE\.pyenv\pyenv-win\bin"
if ($env:PATH -notlike "*$pyenvShims*") {
    $env:PATH = "$pyenvShims;$pyenvBin;$env:PATH"
}

"Setting Python global version to $pythonVersion..." | log
pyenv global $pythonVersion
if ($lastexitcode -ne 0) {
    "-- pyenv global failed (non-fatal for teardown); continuing" | log
}

"-- CD to resources" | log
Set-Location "$scriptDrive\hobl_bin\pytorch_inf_v2_resources"

"-- Cleanup GPU caching" | log
# Use the per-scenario venv python (created during prep) rather than the
# shared pyenv python. The venv has torch installed; the shared pyenv
# environment may not after other scenarios run.
$venvPython = "$scriptDrive\hobl_bin\pytorch_inf_v2_resources\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    "-- venv missing at $venvPython; skipping GPU cleanup (will be recreated on next prep)" | log
    Exit 0
}
& $venvPython run_benchmark.py --cleanup-gpu
# Don't treat cleanup failure as fatal -- teardown should not break the run cycle.
if ($lastexitcode -ne 0) {
    "-- GPU cleanup returned exit code $lastexitcode (non-fatal)" | log
}

"-- pytorch_inf_v2 teardown completed" | log
Exit 0
