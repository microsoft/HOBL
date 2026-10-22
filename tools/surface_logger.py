# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from core.app_scenario import Scenario
import logging
import sys
import os
import time


class Tool(Scenario):
    '''
    Surface-only.  Run SurfaceLogger tool for debug.
    '''
    module = __module__.split('.')[-1]
    # Set default parameters
    ##Autologger method starts trace after reboot and if reboot is not required you can use other trace methods (Logman, Tracelog)
    Params.setDefault(module, 'start_args', '-Start SSHLogs -Method Tracelog -Drivers SurfaceSerialHubDriver') 
    Params.setDefault(module, 'stop_args', '-Stop SSHLogs -Method Tracelog')

    start_args = Params.get(module, 'start_args')
    stop_args = Params.get(module, 'stop_args')

    def initCallback(self, scenario):
        # Initialization code
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        self.scenario_failed = False
        logging.info("Stoping previous Surface Logger.")
        self._call(["powershell.exe", r"c:\tools\SurfaceLogger\SurfaceLogger.ps1 " + self.stop_args], blocking = True, fail_on_exception=False, expected_exit_code="")
        logging.info("Setting up Surface Logger.")       
        self._call(["cmd.exe", "/C del C:\\Logs\\*.* /Q"], expected_exit_code="")
        self._call(["powershell.exe", r"c:\tools\SurfaceLogger\SurfaceLogger.ps1 " + self.start_args], blocking = True, fail_on_exception=True, expected_exit_code="0")
        # We need to reboot for tracing to take effect
        ## Uncomment logging.info, self._call, and self._wait_for_dut_comm if using Autologger.
        #logging.info("Restarting to enable auto logging.")       
        #self._call(["shutdown.exe", "/r /f /t 5"])
        time.sleep(15)
        #self._wait_for_dut_comm()

    def testBeginCallback(self):
        pass
    
    def testEndCallback(self):
        self._remote_make_dir(os.path.join(self.scenario.dut_data_path, self.module))
        self._call(["powershell.exe", r"c:\tools\SurfaceLogger\SurfaceLogger.ps1 " + self.stop_args], blocking = True, fail_on_exception=True, expected_exit_code="0")
        self._call(["cmd.exe", "/C xcopy C:\\Logs\\*.* " + os.path.join(self.scenario.dut_data_path, self.module)], expected_exit_code="0")

    def dataReadyCallback(self):
        # You can do any post processing of data here.
        pass

    def testScenarioFailed(self):
        pass

    def testScenarioFailed(self):
        logging.debug("Test failed, cleaning up.")
        self.testBeginCallback()

    def testTimeoutCallback(self):
        self.testBeginCallback()
        self.conn_timeout = True

    def cleanup(self):
        logging.debug("Cleanup")
        self.testBeginCallback()

