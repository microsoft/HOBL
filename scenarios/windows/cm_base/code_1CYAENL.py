# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import time
import threading

def _upload_large_files(scenario):
    """Encapsulates the content upload/download logic with retry loop."""
    logging.debug('Starting download/upload thread logic: code_1CYAENL.py')
    upload_successful = False
    for i in range(12):
        try:            
            scenario._upload("scenarios\\\windows\\enterprise_collab\\resources\\large", scenario.userprofile + "\\OneDrive\\onedrivetest")
            upload_successful = True
            break
        except Exception:
            logging.error("Could not copy large files to onedrive.")
    if not upload_successful:
        logging.error("Could not copy large files to onedrive in 12 tries.")


def run(scenario):
    """Starts the download/upload logic in a background thread and returns immediately."""
    t = threading.Thread(target=_upload_large_files, args=(scenario,), name="upload_worker", daemon=True)
    scenario.upload_thread = t  # Persist thread object on scenario
    t.start()