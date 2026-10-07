# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Run FishBowl workload
##

import logging
import core.app_scenario
from core.parameters import Params
import time

class FishBowl(core.app_scenario.Scenario):

    module = __module__.split('.')[-1]
    resources = f"{module}_resources"
    prep_file_dependencies = [
        f"scenarios\\windows\\{module}\\{resources}",
        __file__
    ]
    # prep_scenarios = [(module, prep_file_dependencies)]

    # Set default parameters
    Params.setDefault(module, 'fish_count', '10',  desc="Number of fish to use")
    Params.setDefault(module, 'duration',   '300', desc="Duration to run for")

    # Get parameters
    fish_count = int(Params.get(module, 'fish_count'))
    duration = int(Params.get(module, 'duration'))


    def setUp(self):
        self.target = f"{self.dut_exec_path}\\{self.resources}"

        self.prep()

        # Call base class setUp() to dump config, call tool callbacks, and start measurment
        core.app_scenario.Scenario.setUp(self)


    def prep(self):
        if not self.checkPrepStatusNew([(self.module, self.prep_file_dependencies)]):
            return

        logging.info("Preparing for first use")

        logging.info(f"Uploading test files to {self.target}")
        self._upload(f"scenarios\\windows\\{self.module}\\{self.resources}", self.dut_exec_path)

        self.createPrepStatusControlFile(self.prep_file_dependencies)


    def runTest(self):
        fishbowl_html = f"{self.target}\\Default.html?fish_count={self.fish_count}".replace("\\", "/")
        self._call(["powershell.exe", f'Start-Process msedge.exe" -ArgumentList "--start-maximized", file://{fishbowl_html}"'])

        logging.info(f"Waiting for {self.duration}s")
        time.sleep(self.duration)


    def tearDown(self):
        # Call base class tearDown() to stop measurment, copy back data from DUT, and call tool callbacks
        core.app_scenario.Scenario.tearDown(self)


    def kill(self):
        self._kill("msedge.exe")
