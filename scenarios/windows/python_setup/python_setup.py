# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Preps by downloading python env and python
##

import logging
import core.app_scenario
from core.parameters import Params

class PythonSetup(core.app_scenario.Scenario):

    module = __module__.split('.')[-1]
    prep_version = "1"
    resources = module + "_resources"
    is_prep = True

    def runTest(self):

        # Get parameters
        self.platform = Params.get('global', 'platform')


        if self.platform.lower() == "macos":
            self.target = f"{self.dut_exec_path}/{self.resources}"
            # Upload prep script for macOS
            logging.info(f"Uploading test files to {self.target}")
            self._upload(f"scenarios\\windows\\{self.module}\\{self.resources}\\{self.module}_prep.sh", f"{self.dut_exec_path}/{self.resources}")

            # Execute prep script for macos
            logging.info("Executing prep")
            self._call(["zsh", f"{self.target}/{self.module}_prep.sh"])
        else:
            self.target = f"{self.dut_exec_path}\\{self.resources}"
            # Copy over resources to DUT
            logging.info(f"Uploading test files to {self.target}")
            self._upload(f"scenarios\\windows\\{self.module}\\{self.resources}\\{self.module}_prep.ps1", f"{self.dut_exec_path}\\{self.resources}")

            # Execute prep script for Windows
            logging.info("Executing prep")
            self._call(["pwsh", f"{self.target}\\{self.module}_prep.ps1"])

        self.createPrepStatusControlFile(self.prep_version)

    def tearDown(self):
        # Call base class tearDown() to stop measurement, copy back data from DUT, and call tool callbacks
        core.app_scenario.Scenario.tearDown(self)


    def kill(self):
        if self.platform.lower() == "windows":
            try:
                logging.debug("Killing powershell shell")
                self._kill("pwsh.exe")
            except:
                pass

    
