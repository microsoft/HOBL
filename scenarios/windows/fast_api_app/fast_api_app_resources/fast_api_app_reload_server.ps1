# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8765
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:NO_COLOR = "1"

$scriptDrive = Split-Path -Qualifier $PSScriptRoot
$appDir = "$scriptDrive\hobl_bin\fast_api_app_workload"
$appPython = Join-Path $appDir ".venv\Scripts\python.exe"
if (-not (Test-Path $appPython)) {
    Write-Host " ERROR - App venv missing at $appPython. Run fast_api_app first." -ForegroundColor Red
    Exit 1
}

Set-Location $appDir
Write-Host "Starting foreground FastAPI reload server on port $Port"
Write-Host "Keep this console open while HOBL runs fast_api_app with reload_mode=external."
& $appPython -m fastapi dev app/main.py --host 127.0.0.1 --port $Port --reload-dir app
Exit $LASTEXITCODE
