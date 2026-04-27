# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging

def run(scenario):
    logging.debug('Executing code block: code_1EN194J.py')
    # Always copy UtcPerftrack.xml to DUT (check_modified=False) — do not skip based on
    # existing-file-on-DUT comparison. Ensures sideloaded PT manifest is always the latest
    # one shipped in this HOBL checkout, even if the DUT already has a stale copy.
    scenario._upload("utilities\\proprietary\\ParseUtc\\UtcPerftrack.xml", "C:\\ProgramData\\Microsoft\\Diagnosis\\Sideload", check_modified=False)
    scenario._upload("utilities\\proprietary\\ParseUtc\\DisableAllUploads.json", "C:\\ProgramData\\Microsoft\\Diagnosis\\Sideload", check_modified=False)
    scenario._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 3 /f > null 2>&1'])
    scenario._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\Windows Error Reporting" /v DisableWerUpload /t REG_DWORD /d 1 /f > null 2>&1'])
    scenario._sleep_to_now()
            