# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os

def _remove_onedrive_test_directory(scenario):
    onedrivetestdir = os.path.join(scenario.userprofile, "OneDrive", "onedrivetest")
    logging.info(f"Removing directory if present: {onedrivetestdir}")
    scenario._call(
        ["cmd.exe",
         f'/C if exist "{onedrivetestdir}" (rmdir /S /Q "{onedrivetestdir}") '
         'else (echo OneDrive test directory already absent & exit /b 0)'],
        expected_exit_code="0",
        fail_on_exception=True,
    )

def run(scenario):
    logging.debug('Executing code block: code_19K5L2R.py')
    _remove_onedrive_test_directory(scenario)