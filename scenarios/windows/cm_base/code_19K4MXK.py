# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import base64
import os
import logging

from scenarios.windows.cm_base.background_cleanup import DOWNLOAD_FILENAME, DOWNLOAD_STATE_FILENAME, run_powershell

def run(scenario):
    logging.debug('Executing code block: code_19K4MXK.py')
    download_url = "https://download.microsoft.com/download/0/8/b/08b0f0ba-1571-41c0-9b8a-9af8a43681ae/SurfacePro7_Win11_22621_24.121.14800.0.msi"
    download_dir = os.path.join(scenario.userprofile, "OneDrive", "onedrivetest")
   
    logging.info("Downloading a large file from the internet SP7 driver at " + download_dir)
    
    powershell_download_path = os.path.join(download_dir, DOWNLOAD_FILENAME)

    # Create directory if it doesn't exist
    scenario._call(
        ["cmd.exe", f'/C if not exist "{download_dir}" mkdir "{download_dir}"'],
        expected_exit_code="0",
        fail_on_exception=True,
    )
    path_literal = powershell_download_path.replace("'", "''")
    download_command = f"$ErrorActionPreference = 'Stop'; Invoke-WebRequest -Uri '{download_url}' -OutFile '{path_literal}'"
    encoded_download = base64.b64encode(download_command.encode("utf-16-le")).decode("ascii")
    state_file = os.path.join(download_dir, DOWNLOAD_STATE_FILENAME).replace("'", "''")
    run_powershell(scenario, f"""
$ErrorActionPreference = 'Stop'
$stateFile = '{state_file}'
$process = Start-Process powershell.exe -ArgumentList '-NoProfile -ExecutionPolicy Bypass -EncodedCommand {encoded_download}' -PassThru -WindowStyle Hidden
try {{
    @{{ pid = $process.Id; started_ticks = $process.StartTime.ToUniversalTime().Ticks.ToString() }} |
        ConvertTo-Json -Compress | Set-Content -LiteralPath $stateFile -Encoding UTF8
}} catch {{
    if (-not $process.HasExited) {{ Stop-Process -Id $process.Id -Force -ErrorAction Stop }}
    throw
}}
Write-Host "Started download process with PID: $($process.Id)"
""")