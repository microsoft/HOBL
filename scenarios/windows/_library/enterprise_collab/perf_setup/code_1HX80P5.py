# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
from core.parameters import Params

def run(scenario):
    logging.debug('Executing code block: code_1HX80P5.py')
    sideload_dir = "C:\\ProgramData\\Microsoft\\Diagnosis\\Sideload"
    minwin_workloads = Params.get("enterprise_collab", "minwin_workloads")
    logging.info(f"enterprise_collab:minwin_workloads='{minwin_workloads}'")

    if minwin_workloads and len(minwin_workloads.strip()) > 0:
        logging.info("Setting enterprise_collab:simple_office_launch=0 because mincp_workloads has entries")
        Params.setParam("enterprise_collab", "simple_office_launch", "0")
        logging.info("Sideloading ConsumerMultitaskerPTs.xml because mincp_workloads is set")
        scenario._upload("utilities\\proprietary\\ParseUtc\\ConsumerMultitaskerPTs.xml", sideload_dir)
        scenario._call(["cmd.exe", f'/C copy /Y "{sideload_dir}\\ConsumerMultitaskerPTs.xml" "{sideload_dir}\\UtcPerftrack.xml"'])
    else:
        logging.info("Sideloading UtcPerftrack.xml for enterprise _collab run")
        scenario._upload("utilities\\proprietary\\ParseUtc\\UtcPerftrack.xml", sideload_dir)

    scenario._upload("utilities\\proprietary\\ParseUtc\\DisableAllUploads.json", sideload_dir)
    scenario._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 3 /f > null 2>&1'])
    scenario._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\Windows Error Reporting" /v DisableWerUpload /t REG_DWORD /d 1 /f > null 2>&1'])
    scenario._sleep_to_now()
            