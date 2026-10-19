# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Battery Logger tool
#
# Produces a csv trace file of battery stats vs. time

from core.parameters import Params
from core.app_scenario import Scenario
import logging
import sys
import time
import os
import pandas as pd


class Tool(Scenario):
    '''
    Surface only.  Logs battery details over time.
    '''
    module = __module__.split('.')[-1]

    def initCallback(self, scenario):
        # Initialization code
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        self.conn_timeout = False
        self.output_path = self.scenario.dut_data_path + f"\\{self.module}"
        # Copy the exe if it doesn't already exist
        if not self._check_remote_file_exists("RunBatLogger.ps1"):
            self._upload("utilities\\open_source\\RunBatLogger.ps1", self.dut_exec_path)

    def testBeginCallback(self):
        #Make directory in dut_data_path of the tool name to put any outputs in that directory
        self._call(["cmd.exe", '/c if not exist "' + self.output_path + '" mkdir "' + self.output_path + '"'])
        output_file = self.output_path + "\\batlog.csv"
        cmd = "-ExecutionPolicy Unrestricted " + os.path.join(self.dut_exec_path, "RunBatLogger.ps1 -o " + output_file)
        self._call(["powershell.exe", cmd], blocking=False)
        logging.info("Battery log collection started.")

    def testEndCallback(self):
        self._kill("powershell.exe")
        logging.info("Battery log collection stopped.")
        # kill_cmd = 'powershell -command "Get-CimInstance Win32_Process -Filter \"Name=\'powershell.exe\'\" | Where-Object {$_.CommandLine -match \"RunBatLogger.ps1\"} | ForEach-Object {Stop-Process -Id $_.ProcessId }"'
        # self._call(kill_cmd)

        if self.conn_timeout:
            output_file = self.output_path + "\\batlog.csv"
            self._call(["cmd.exe", '/c del ' + output_file], expected_exit_code="")

    def testTimeoutCallback(self):
        self.conn_timeout = True
