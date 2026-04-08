# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging

def run(scenario):
    logging.debug('Executing code block: code_1HX80P5.py')
    sideload_dir = "C:\\ProgramData\\Microsoft\\Diagnosis\\Sideload"
    logging.info("Sideloading StressUtcPerftrack.xml before WPR starts")
    scenario._upload("utilities\\proprietary\\ParseUtc\\StressUtcPerftrack.xml", sideload_dir)
    scenario._call(["cmd.exe", f'/C copy /Y "{sideload_dir}\\StressUtcPerftrack.xml" "{sideload_dir}\\UtcPerftrack.xml"'], expected_exit_code="")
    scenario._upload("utilities\\proprietary\\ParseUtc\\DisableAllUploads.json", sideload_dir)
    scenario._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 3 /f > null 2>&1'], expected_exit_code="")
    scenario._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\Windows Error Reporting" /v DisableWerUpload /t REG_DWORD /d 1 /f > null 2>&1'], expected_exit_code="")
    logging.info("Restarting DiagTrack to load sideloaded UtcPerftrack.xml")
    scenario._call(["cmd.exe", "/c net stop DiagTrack & net start DiagTrack"], expected_exit_code="")
    import time
    time.sleep(5)  # Give DiagTrack time to register scenarios
    scenario._sleep_to_now()
            