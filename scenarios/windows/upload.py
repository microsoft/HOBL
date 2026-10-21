# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import core.app_scenario
from core.parameters import Params

class Upload(core.app_scenario.Scenario):
    '''
    Uploads a file or folder to the DUT
    '''
    module = __module__.split('.')[-1]

    # Set default parameters
    Params.setDefault(module, 'source_path', '', desc="Source path (file or folder)")
    Params.setDefault(module, 'target_path', '', desc="Target folder (defaults to hobl_bin)")

    # Get parameters
    source_path = Params.get(module, 'source_path')
    target_path = Params.get(module, 'target_path')

    Params.setOverride("global", "collection_enabled", "0")

    def setUp(self):
        pass

    def runTest(self):
        if not self.target_path:
            self.target_path = self.dut_exec_path

        if self.source_path != "":
            logging.info(f"Uploading {self.source_path} to {self.target_path}")
            self._upload(self.source_path, self.target_path)
        else:
            logging.error("No source path specified")

    def tearDown(self):
        return
