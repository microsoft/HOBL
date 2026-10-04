# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# AI Foundry Local Workload
##

import logging
import os
import core.app_scenario
from core.parameters import Params
import time

class Foundrylocal(core.app_scenario.Scenario):

    module = __module__.split('.')[-1]
    prep_version = "8"
    resources = module + "_resources"


    # Set default parameters
    Params.setDefault(module, 'loops', '1')
    Params.setDefault(module, 'model', 'qwen2.5-0.5b')
    Params.setDefault(module, 'prompt', 'What is the meaning of life?')
    Params.setDefault(module, 'foundry_version', '2.0.1')


    def setUp(self):
        # Get parameters
        self.platform = Params.get('global', 'platform')
        self.loops = Params.get(self.module, 'loops')
        self.model = Params.get(self.module, 'model')
        self.prompt = Params.get(self.module, 'prompt')
        self.foundry_version = Params.get(self.module, 'foundry_version')

        self.target = f"{self.dut_exec_path}\\{self.resources}"

        # Test if already set up
        if self.checkPrepStatus([self.module + self.prep_version]):
            logging.info("Preparing for first use.")

            # Copy over resources to DUT
            logging.info(f"Uploading test files to {self.target}")
            self._upload(f"scenarios\\windows\\{self.module}\\{self.resources}", self.dut_exec_path)

            # Execute prep script (installs the Foundry Local SDK and publishes the workload app)
            logging.info(f"Executing prep, installing Foundry Local SDK version {self.foundry_version}...")
            try:
                self._call(["pwsh", f"{self.target}\\{self.module}_prep.ps1 -foundryVersion {self.foundry_version}"], timeout=1800)
            finally:
                self._copy_data_from_remote(self.result_dir)
            self.createPrepStatusControlFile(self.prep_version)

        # Execute setup script (downloads the model)
        logging.info(f"Setting up model: {self.model}")
        try:
            self._call(["pwsh", f"{self.target}\\{self.module}_setup.ps1 -model {self.model}"], timeout=3600)
        finally:
            self._copy_data_from_remote(self.result_dir)

        # Call base class setUp() to dump config, call tool callbacks, and start measurement
        core.app_scenario.Scenario.setUp(self)


    def runTest(self):
        for i in range(int(self.loops)):
            logging.info(f"Running loop {i + 1}")
            self._call(["pwsh", f"{self.target}\\{self.module}_run.ps1 -model {self.model} -prompt \"{self.prompt}\""], timeout=600)


    def tearDown(self):
        logging.info("Performing teardown.")
        # Call base class tearDown() to stop measurement, copy back data from DUT, and call tool callbacks
        core.app_scenario.Scenario.tearDown(self)

        # Remove the model from cache
        logging.info(f"Removing model from cache: {self.model}")
        self._call(["pwsh", f"{self.target}\\{self.module}_teardown.ps1 -model {self.model}"])


    def kill(self):
        try:
            logging.debug("Killing powershell and foundry processes")
            self._kill("pwsh.exe")
            self._kill("foundry.exe")
        except:
            pass
