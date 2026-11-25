# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# .NET Apire Compiling Workload
##

import logging
import os
import core.app_scenario
from core.parameters import Params
import time

class MacNetAspire(core.app_scenario.Scenario):

    module = __module__.split('.')[-1]
    prep_version = "12"
    resources = module + "_resources"


    # Set default parameters
    Params.setDefault(module, 'loops', '4')
    Params.setDefault(module, 'binlog', '0', desc="Collect an MSBuild binary log for each build (adds overhead).", valOptions=['0', '1'])
    Params.setDefault(module, 'skip_playwright_browser_install', '0', desc="Skip Playwright browser installation during the timed build.", valOptions=['0', '1'])
    Params.setDefault(module, 'max_cpu_count', '0', desc="Maximum concurrent MSBuild processes (0 keeps the original default; experiment B: 12).")


    def setUp(self):
        # Get parameters
        self.platform = Params.get('global', 'platform')
        self.loops = Params.get(self.module, 'loops')
        self.binlog = Params.get(self.module, 'binlog') == '1'
        self.skip_playwright_browser_install = Params.get(self.module, 'skip_playwright_browser_install') == '1'
        try:
            self.max_cpu_count = int(Params.get(self.module, 'max_cpu_count'))
        except (TypeError, ValueError):
            raise ValueError("max_cpu_count must be a non-negative 32-bit integer (0 keeps the original default).") from None
        if not 0 <= self.max_cpu_count <= 2147483647:
            raise ValueError("max_cpu_count must be a non-negative 32-bit integer (0 keeps the original default).")

        self.target = f"{self.dut_exec_path}/{self.resources}"

        # Test if already set up
        if self.checkPrepStatus([self.module + self.prep_version]):
            logging.info("Preparing for first use.")

            # Create SUDO_ASKPASS helper script to automate sudo password entry
            self._call(["zsh", f"-c \"echo '#!/bin/sh\necho {self.password}' > {self.dut_exec_path}/get_password.sh\""])
            self._call(["zsh", f"-c \"chmod 700 {self.dut_exec_path}/get_password.sh\""])

            # Copy over resources to DUT
            logging.info(f"Uploading test files to {self.target}")
            self._upload(f"scenarios\\MacOS\\{self.module}\\{self.resources}", self.dut_exec_path)

            # Excute prep script
            logging.info("Executing prep, this make take 10-15 minutes...")
            try:
                self._call(["zsh", f"{self.target}/{self.module}_prep.sh"])
            finally:
                self._copy_data_from_remote(self.result_dir)
            self.createPrepStatusControlFile(self.prep_version)
        elif self.binlog or self.skip_playwright_browser_install or self.max_cpu_count:
            self._upload(f"scenarios\\MacOS\\{self.module}\\{self.resources}\\{self.module}_run.sh", self.target, check_modified=False)


        try:
            self._call(["zsh", '-c "cd /Users/Shared/hobl_bin/aspire; ./build.sh --restore"'])
        finally:
            self._copy_data_from_remote(self.result_dir)

        # Call base class setUp() to dump config, call tool callbacks, and start measurment
        core.app_scenario.Scenario.setUp(self)


    def runTest(self):
        run_args = " --binlog" if self.binlog else ""
        if self.skip_playwright_browser_install:
            run_args += " --skip-playwright-browser-install"
        if self.max_cpu_count:
            run_args += f" --max-cpu-count {self.max_cpu_count}"
        for i in range(int(self.loops)):
            logging.info(f"Running loop {i + 1}")
            self._call(["zsh", f"{self.target}/{self.module}_run.sh{run_args}"])

            # TODO: Do we need to call teardown script between each loop to clear cache?


    def tearDown(self):
        logging.info("Performing teardown.")
        # Call base class tearDown() to stop measurment, copy back data from DUT, and call tool callbacks
        core.app_scenario.Scenario.tearDown(self)

        logging.info("Executing teardown script.")
        self._call(["zsh", '-c "cd /Users/Shared/hobl_bin/aspire; ./build.sh --clean"'])


    def kill(self):
        return
        try:
            logging.debug("Killing command shell")
            # self._kill("zsh")
        except:
            pass

