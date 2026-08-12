# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import os

def _kill_upload_thread(scenario):
    """Wait for an active upload_thread to complete without attempting to stop it."""
    upload_thread = getattr(scenario, 'upload_thread', None)
    if upload_thread and upload_thread.is_alive():
        logging.info('Waiting (timeout 25s) for upload thread to finish.')
        upload_thread.join(timeout=25)
        if upload_thread.is_alive():
            # There is no API in python to forcibily kill a thread
            logging.warning('Upload thread still running after 200s timeout.')
        else:
            logging.info('Upload thread finished within timeout.')
        
            # Delete the extra docs from onedrive, recursively and quietly
    
    onedrivetestdir = os.path.join(scenario.userprofile, "OneDrive", "onedrivetest")
    logging.info(f"Removing directory {onedrivetestdir}")
    del_out = scenario._call(["cmd.exe", "/C rmdir /S /Q " + onedrivetestdir], expected_exit_code="", fail_on_exception=True)
    if del_out:
        logging.warning(f"Could not delete {onedrivetestdir}, Kindly delete manually for next run")

def run(scenario):
    logging.debug('Executing code block: code_19K5L2R.py')
    _kill_upload_thread(scenario)