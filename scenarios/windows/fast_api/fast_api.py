# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Fast API building Workload
##

import logging
import os
import re
import core.app_scenario
from core.parameters import Params
from datetime import datetime

class FastApi(core.app_scenario.Scenario):

    module = __module__.split('.')[-1]
    prep_version = "10"
    resources = module + "_resources"


    # Set default parameters
    Params.setDefault(module, 'loops', '5')
    Params.setDefault(module, 'workers', '0')


    def setUp(self):
        # Get parameters
        self.platform = Params.get('global', 'platform')
        self.loops = Params.get(self.module, 'loops')
        self.workers = Params.get(self.module, 'workers')
        if not re.fullmatch(r'auto|[0-9]+', self.workers):
            raise ValueError(f"{self.module}:workers must be 'auto' or a non-negative integer.")

        self.target = f"{self.dut_exec_path}\\{self.resources}"

        # Test if already set up
        if self.checkPrepStatus([self.module + self.prep_version]):
            logging.info("Preparing for first use.")

            # Copy over resources to DUT
            logging.info(f"Uploading test files to {self.target}")
            self._upload(f"scenarios\\windows\\{self.module}\\{self.resources}", self.dut_exec_path)

            # Excute prep script
            logging.info("Executing prep, this make take 10-15 minutes...")
            try:
                self._call(["pwsh", f"{self.target}\\{self.module}_prep.ps1"])
            finally:
                self._copy_data_from_remote(self.result_dir)
            self.createPrepStatusControlFile(self.prep_version)

        # Call base class setUp() to dump config, call tool callbacks, and start measurment
        core.app_scenario.Scenario.setUp(self)


    def runTest(self):
        start_time = datetime.now().astimezone().isoformat()
        for i in range(int(self.loops)):
            logging.info(f"Running loop {i + 1}")
            self._call(["pwsh", f"{self.target}\\{self.module}_run.ps1 -startTime {start_time} -Workers {self.workers}"], timeout = 3600)


    def tearDown(self):
        logging.info("Performing teardown.")
        # Call base class tearDown() to stop measurment, copy back data from DUT, and call tool callbacks
        core.app_scenario.Scenario.tearDown(self)


    def kill(self):
        try:
            logging.debug("Killing powershell shell")
            self._kill("pwsh.exe")
        except:
            pass

