# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import os
import logging

def run(scenario):
    logging.debug('Executing code block: code_1CYAE3L.py')
    
    onedrivetestdir = os.path.join(scenario.userprofile, "OneDrive", "onedrivetest")
    logging.info(f"Removing directory {onedrivetestdir}")
    
    scenario._remote_make_dir(onedrivetestdir,delete=True)
    
    target_path = "scenarios\\windows\\enterprise_collab\\resources\\large"

    if not os.path.exists(target_path):
        os.makedirs(target_path)

    for i in range(3):
        os.system("fsutil file createnew " + target_path + "\\temp_" + str(i) + ".bin 1610612736")

    logging.info("Large files created for OneDrive copy operations")
    scenario._sleep_to_now()
    
    
