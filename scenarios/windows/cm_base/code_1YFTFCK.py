# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os
import threading

from scenarios.windows.cm_base.background_cleanup import LARGE_FILE_STATE_FILENAME


def _create_large_files(scenario):
    try:
        if scenario.large_file_stop.is_set():
            return
        output_directory = os.path.join(scenario.userprofile, "largefiles")
        logging.info(f"Creating DUT output directory if needed: {output_directory}")
        scenario._call(
            ["cmd.exe", f'/C if not exist "{output_directory}" mkdir "{output_directory}"'],
            expected_exit_code="0",
            fail_on_exception=True,
        )

        if scenario.large_file_stop.is_set():
            return
        script_path = os.path.join(scenario.dut_exec_path, "largefiles", "create_large_files.ps1")
        state_file = os.path.join(scenario.dut_exec_path, "largefiles", LARGE_FILE_STATE_FILENAME)
        logging.info(f"Running {script_path} with output directory {output_directory}")
        scenario._call(
            ["powershell.exe",
             f'-NoProfile -ExecutionPolicy Bypass -File "{script_path}" '
             f'-OutputDirectory "{output_directory}" -ProcessStateFile "{state_file}"'],
            expected_exit_code="0",
            fail_on_exception=True,
            timeout=3600,
        )
        logging.info("Background large-file creation completed")
    except Exception:
        if scenario.large_file_stop.is_set():
            logging.warning("Background large-file creation interrupted during cleanup", exc_info=True)
        else:
            logging.exception("Background large-file creation failed")


def run(scenario):
    logging.debug('Executing code block: code_1YFTFCK.py')
    scenario.large_file_stop = threading.Event()
    scenario.large_file_thread = threading.Thread(
        target=_create_large_files,
        args=(scenario,),
        name="large_file_worker",
        daemon=True,
    )
    logging.info("Starting background large-file creation")
    scenario.large_file_thread.start()