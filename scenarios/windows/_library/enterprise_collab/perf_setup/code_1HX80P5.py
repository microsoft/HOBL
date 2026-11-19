# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
from core.parameters import Params

def run(scenario):
    logging.debug('Executing code block: code_1HX80P5.py')
    sideload_dir = "C:\\ProgramData\\Microsoft\\Diagnosis\\Sideload"
    perftrack_manifest = Params.get("perf_setup", "perftrack_manifest")
    logging.info(f"perf_setup:perftrack_manifest='{perftrack_manifest}'")

    if perftrack_manifest == "ConsumerMutitasker":
        logging.info("Sideloading ConsumerMultitaskerPTs.xml for ConsumerMutitasker")
        scenario._upload("utilities\\proprietary\\ParseUtc\\ConsumerMultitaskerPTs.xml", sideload_dir, check_modified=False)
        scenario._call(["cmd.exe", f'/C copy /Y "{sideload_dir}\\ConsumerMultitaskerPTs.xml" "{sideload_dir}\\UtcPerftrack.xml"'])
    elif perftrack_manifest == "EnterpriseCollaborator":
        logging.info("Sideloading UtcPerftrack.xml for EnterpriseCollaborator")
        scenario._upload("utilities\\proprietary\\ParseUtc\\UtcPerftrack.xml", sideload_dir)
    else:
        raise ValueError(f"Unsupported perf_setup:perftrack_manifest: {perftrack_manifest!r}")

    scenario._upload("utilities\\proprietary\\ParseUtc\\DisableAllUploads.json", sideload_dir)
    scenario._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 3 /f > null 2>&1'])
    scenario._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\Windows Error Reporting" /v DisableWerUpload /t REG_DWORD /d 1 /f > null 2>&1'])
    scenario._sleep_to_now()
            