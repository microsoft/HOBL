# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os
from core.parameters import Params

def _kill_powershell_download(scenario):
    """Terminate an in-flight download process and remove any partial file if present."""
    module = "enterprise_collab"
    powershell_download_pid = Params.get(module,'powershell_download_pid')
    logging.info(f"Terminating download process with PID: {powershell_download_pid}")
    
    scenario._call(["cmd.exe", "/c taskkill /F /PID " + powershell_download_pid + " > null 2>&1"], expected_exit_code="")

def run(scenario):
    logging.debug('Executing code block: code_19K5K7L.py')
    _kill_powershell_download(scenario)