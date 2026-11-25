# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os
from scenarios.windows.cm_base.background_cleanup import DOWNLOAD_STATE_FILENAME, stop_tracked_powershell
from scenarios.windows.cm_base.code_19K5L2R import run as remove_download_files


def _kill_powershell_download(scenario):
    """Stop the recorded download before removing its files."""
    if not os.path.isabs(scenario.userprofile):
        raise ValueError("Download cleanup requires an absolute DUT userprofile path")

    state_file = os.path.join(
        scenario.userprofile, "OneDrive", "onedrivetest",
        DOWNLOAD_STATE_FILENAME,
    )
    logging.info(f"Stopping background download recorded in {state_file}")
    stop_tracked_powershell(scenario, state_file)


def run(scenario):
    logging.debug('Executing code block: code_19K5K7L.py')
    _kill_powershell_download(scenario)
    remove_download_files(scenario)