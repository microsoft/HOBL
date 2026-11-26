# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import os
import logging

from scenarios.windows.cm_base.code_19K5K7L import run as cleanup_download


def run(scenario):
    logging.debug('Executing code block: code_1CYAE3L.py')
    cleanup_download(scenario)
    onedrivetestdir = os.path.join(scenario.userprofile, "OneDrive", "onedrivetest")
    logging.info(f"Creating directory: {onedrivetestdir}")
    scenario._call(
        ["cmd.exe", f'/C if not exist "{onedrivetestdir}" mkdir "{onedrivetestdir}"'],
        expected_exit_code="0",
        fail_on_exception=True,
    )

    scenario._sleep_to_now()
    
    
