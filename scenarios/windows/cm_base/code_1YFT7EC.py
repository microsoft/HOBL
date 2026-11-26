# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os

from scenarios.windows.cm_base.code_1YFTRC4 import run as cleanup_large_files


def run(scenario):
    logging.debug('Executing code block: code_1YFT7EC.py')
    source = os.path.join(os.path.dirname(__file__), "scripts", "create_large_files.ps1")
    if not os.path.isfile(source):
        raise FileNotFoundError(f"Large-file creation script not found: {source}")

    cleanup_large_files(scenario)
    destination = os.path.join(scenario.dut_exec_path, "largefiles")
    logging.info(f"Creating DUT directory if needed: {destination}")
    scenario._call(
        ["cmd.exe", f'/C if not exist "{destination}" mkdir "{destination}"'],
        expected_exit_code="0",
        fail_on_exception=True,
    )
    logging.info(f"Uploading {source} to {destination}")
    scenario._upload(source, destination, check_modified=False)