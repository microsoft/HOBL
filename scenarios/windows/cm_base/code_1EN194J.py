# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging

def run(scenario):
    logging.debug('Executing code block: code_1EN194J.py')
    scenario._upload("utilities\\proprietary\\ParseUtc\\UtcPerftrack.xml", "C:\\ProgramData\\Microsoft\\Diagnosis\\Sideload")
    scenario._upload("utilities\\proprietary\\ParseUtc\\DisableAllUploads.json", "C:\\ProgramData\\Microsoft\\Diagnosis\\Sideload")
    scenario._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 3 /f > null 2>&1'])
    scenario._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\Windows Error Reporting" /v DisableWerUpload /t REG_DWORD /d 1 /f > null 2>&1'])
    scenario._sleep_to_now()
            