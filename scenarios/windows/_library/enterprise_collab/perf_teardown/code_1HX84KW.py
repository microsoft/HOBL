# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging

def run(scenario):
    logging.debug('Executing code block: code_1HX84KW.py')
    scenario._call(["cmd.exe", '/C reg delete "HKLM\\SOFTWARE\\Microsoft\\Windows\\Windows Error Reporting" /v DisableWerUpload /f > null 2>&1'], expected_exit_code="")
    scenario._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 1 /f > null 2>&1'], expected_exit_code="")
    scenario._call(["cmd.exe", '/C del /f "C:\\ProgramData\\Microsoft\\Diagnosis\\Sideload\\UtcPerftrack.xml"'], expected_exit_code="")
    scenario._call(["cmd.exe", '/C del /f "C:\\ProgramData\\Microsoft\\Diagnosis\\Sideload\\DisableAllUploads.json"'], expected_exit_code="")
    scenario._sleep_to_now()