# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os
import time

from scenarios.windows.cm_base.background_cleanup import LARGE_FILE_STATE_FILENAME, run_powershell, stop_tracked_powershell


def run(scenario):
    logging.debug('Executing code block: code_1YFTRC4.py')
    if not os.path.isabs(scenario.userprofile) or not os.path.isabs(scenario.dut_exec_path):
        raise ValueError("Large-file cleanup requires absolute DUT userprofile and execution paths")

    output_directory = os.path.join(scenario.userprofile, "largefiles")
    script_directory = os.path.join(scenario.dut_exec_path, "largefiles")
    script_path = os.path.join(script_directory, "create_large_files.ps1")
    state_file = os.path.join(script_directory, LARGE_FILE_STATE_FILENAME)
    stop_event = getattr(scenario, "large_file_stop", None)
    if stop_event is not None:
        stop_event.set()

    worker = getattr(scenario, "large_file_thread", None)
    deadline = time.monotonic() + 60
    while worker is not None and worker.is_alive():
        stop_tracked_powershell(scenario, state_file)
        worker.join(timeout=1)
        if worker.is_alive() and time.monotonic() >= deadline:
            raise TimeoutError("Large-file worker did not stop; generated files were not deleted")

    stop_tracked_powershell(scenario, state_file)
    logging.info(f"Removing generated large files and directory: {output_directory}")
    logging.info(f"Removing uploaded creation script: {script_path}")
    output_literal = output_directory.replace("'", "''")
    script_literal = script_path.replace("'", "''")
    directory_literal = script_directory.replace("'", "''")
    run_powershell(scenario, f"""
$ErrorActionPreference = 'Stop'
$outputDirectory = '{output_literal}'
$scriptPath = '{script_literal}'
$scriptDirectory = '{directory_literal}'
if (Test-Path -LiteralPath $outputDirectory) {{
    Remove-Item -LiteralPath $outputDirectory -Recurse -Force
}} else {{
    Write-Host "Generated large-file directory already absent: $outputDirectory"
}}
if (Test-Path -LiteralPath $scriptPath) {{
    Remove-Item -LiteralPath $scriptPath -Force
}} else {{
    Write-Host "Cleanup artifact already absent: $scriptPath"
}}
if ((Test-Path -LiteralPath $scriptDirectory) -and -not (Get-ChildItem -LiteralPath $scriptDirectory -Force)) {{
    Remove-Item -LiteralPath $scriptDirectory -Force
}}
""")