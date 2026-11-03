# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import os
import logging
from core.parameters import Params

def run(scenario):
    logging.debug('Executing code block: code_19K4MXK.py')
    module = "enterprise_collab"
    download_url = "https://download.microsoft.com/download/0/8/b/08b0f0ba-1571-41c0-9b8a-9af8a43681ae/SurfacePro7_Win11_22621_24.121.14800.0.msi"
    download_dir = os.path.join(scenario.userprofile, "OneDrive", "onedrivetest")
   
    logging.info("Downloading a large file from the internet SP7 driver at " + download_dir)
    
    powershell_download_path = os.path.join(download_dir, "SurfacePro7_Win10_18363_20.092.41920.0.msi")
    Params.setParam(module,'powershell_download_path',powershell_download_path)

    # Create directory if it doesn't exist
    scenario._remote_make_dir(download_dir)
   
    ps_command = f"$process = Start-Process powershell -ArgumentList 'Invoke-WebRequest -Uri {download_url} -OutFile \"{powershell_download_path}\"' -PassThru -WindowStyle Hidden; $process.Id"

    powershell_download_pid = scenario._call(["powershell.exe", ps_command])
        
    if powershell_download_pid and powershell_download_pid.strip().isdigit():
        powershell_download_pid = powershell_download_pid.strip()
        Params.setParam(module,'powershell_download_pid',powershell_download_pid)
        logging.info(f"Started download process with PID: {powershell_download_pid}")
    else:
        logging.info(f"Failed to get valid PID, got: '{powershell_download_pid}'")
        scenario.fail("Failed to start powershell download")

    