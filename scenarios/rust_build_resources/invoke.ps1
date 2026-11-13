# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root.
#Requires -Version 7.2
param(
    [Parameter(Mandatory)][ValidateSet('prep', 'run', 'teardown', 'kill')][string]$Phase,
    [Parameter(Mandatory)][ValidateSet('rust_analyzer_build', 'nushell_build')][string]$Workload,
    [Parameter(Mandatory)][string]$Scenario,
    [string]$WorkRoot = '',
    [string]$DataDir = '',
    [string]$PythonExe = '',
    [string]$Toolchain = '1.100.0',
    [string]$Repository = '',
    [int]$Jobs = 0,
    [int]$Sample = 1
)
$ErrorActionPreference = 'Stop'
try {
    if ($Scenario -notmatch '^(mac_)?(rust_analyzer_build|nushell_build)$') {
        throw 'Invalid scenario name.'
    }
    $scriptDrive = Split-Path -Qualifier $PSScriptRoot
    if (-not $WorkRoot) { $WorkRoot = Join-Path $scriptDrive "hobl_bin\$Scenario-work" }
    if (-not $DataDir) { $DataDir = Join-Path $scriptDrive 'hobl_data' }
    $venv = Join-Path $PSScriptRoot ".venvs\$Scenario"
    $venvPython = Join-Path $venv 'Scripts\python.exe'
    if ($Phase -eq 'prep' -and -not (Test-Path -LiteralPath $venvPython)) {
        if (-not $PythonExe) {
            $executionPolicy = Get-ExecutionPolicy -Scope Process
            if ($executionPolicy -eq 'Restricted' -or $executionPolicy -eq 'Undefined') {
                Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process -Force
            }
            if (-not (Get-Command pyenv -ErrorAction SilentlyContinue)) {
                throw 'Install HOBL pyenv first, or supply an explicit -PythonExe for standalone validation.'
            }
            $pythonVersion = if ([Runtime.InteropServices.RuntimeInformation]::OSArchitecture -eq 'Arm64') {
                '3.12.10-arm'
            } else { '3.12.10' }
            $versions = @(pyenv versions --bare) | ForEach-Object { $_.Trim() }
            if ($LASTEXITCODE -ne 0) { throw 'pyenv versions failed.' }
            if ($versions -notcontains $pythonVersion) {
                pyenv install $pythonVersion
                if ($LASTEXITCODE -ne 0) { throw 'pyenv install failed.' }
            }
            $env:PYENV_VERSION = $pythonVersion
            $PythonExe = (pyenv which python).Trim()
            if ($LASTEXITCODE -ne 0) { throw 'pyenv which python failed.' }
        }
        if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
            throw "Python executable not found: $PythonExe"
        }
        Write-Host "Python: $PythonExe"
        & $PythonExe -m venv --without-pip $venv
        if ($LASTEXITCODE -ne 0) { throw 'Creating the per-scenario Python environment failed.' }
    }
    if (-not (Test-Path -LiteralPath $venvPython)) { throw 'Scenario Python environment is missing; re-run prep.' }
    & $venvPython -c 'import json, subprocess, tomllib; import sys; assert sys.version_info >= (3, 11)'
    if ($LASTEXITCODE -ne 0) { throw 'Scenario Python environment is broken; re-run prep.' }
    $arguments = @(
        "$PSScriptRoot\build.py", $Phase, '--workload', $Workload, '--scenario', $Scenario,
        '--work-root', $WorkRoot, '--data-dir', $DataDir, '--toolchain', $Toolchain,
        '--jobs', "$Jobs", '--sample', "$Sample"
    )
    if ($Repository) { $arguments += @('--repository', $Repository) }
    & $venvPython @arguments
    if ($LASTEXITCODE -ne 0) { throw "Rust workload $Phase failed with exit code $LASTEXITCODE." }
} catch {
    Write-Host " ERROR - $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
