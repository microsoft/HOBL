# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Targeted process cleanup shared by normal actions and emergency cleanup."""

import base64
import logging
import os

from core.parameters import Params


DOWNLOAD_FILENAME = "SurfacePro7_Win10_18363_20.092.41920.0.msi"
DOWNLOAD_STATE_FILENAME = "download_process.json"
LARGE_FILE_STATE_FILENAME = "large_file_process.json"


def run_powershell(scenario, script):
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return scenario._call(
        ["powershell.exe", f"-NoProfile -ExecutionPolicy Bypass -EncodedCommand {encoded}"],
        expected_exit_code="0",
        fail_on_exception=True,
        timeout=30,
    )


def stop_tracked_powershell(scenario, state_file):
    if not os.path.isabs(state_file):
        raise ValueError("PowerShell cleanup requires an absolute process-state path")
    state_literal = state_file.replace("'", "''")
    run_powershell(scenario, f"""
$ErrorActionPreference = 'Stop'
$stateFile = '{state_literal}'
if (-not (Test-Path -LiteralPath $stateFile)) {{
    Write-Host "No recorded PowerShell process: $stateFile"
    exit 0
}}
$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
if ([string]$state.pid -notmatch '^[1-9][0-9]*$' -or [string]$state.started_ticks -notmatch '^[1-9][0-9]*$') {{
    throw " ERROR - Invalid process record: $stateFile"
}}
try {{
    $process = Get-Process -Id ([int]$state.pid) -ErrorAction Stop
    if ($process.ProcessName -ne 'powershell' -or $process.StartTime.ToUniversalTime().Ticks -ne [long]$state.started_ticks) {{
        Write-Host "Recorded PID $($state.pid) belongs to a different process; leaving it running."
    }} else {{
        Write-Host "Stopping recorded PowerShell process with PID: $($process.Id)"
        $stopped = Stop-Process -Id $process.Id -Force -PassThru -ErrorAction Stop
        if (-not $stopped.WaitForExit(10000)) {{
            throw " ERROR - Scenario PowerShell process did not exit: $($process.Id)"
        }}
    }}
}}
catch {{
    if ($_.FullyQualifiedErrorId -notlike 'NoProcessFoundForGivenId,*') {{
        throw
    }}
    Write-Host "Recorded PowerShell process already exited: $($state.pid)"
}}
Remove-Item -LiteralPath $stateFile -Force
""")


def cleanup_background_processes(scenario):
    from .code_19K5K7L import run as cleanup_download
    from .code_1YFTRC4 import run as cleanup_large_files

    failures = []
    for parameter, cleanup in (
        ("powershell_download", cleanup_download),
        ("large_file_operations", cleanup_large_files),
    ):
        if Params.get("cm_base", parameter) != "1":
            continue
        try:
            cleanup(scenario)
        except Exception as error:
            logging.exception("cm_base background cleanup failed: %s", parameter)
            failures.append((parameter, error))

    if failures:
        raise RuntimeError(
            "Background cleanup failed: " + ", ".join(parameter for parameter, error in failures)
        ) from failures[0][1]
