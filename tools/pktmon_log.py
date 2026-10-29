# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Netsh tool

from core.parameters import Params
from core.app_scenario import Scenario
import logging
import sys
import time

class Tool(Scenario):
    '''
    Use pktmon to log network traffic.
    '''
    module = __module__.split('.')[-1]

    # Set default parameters
    Params.setDefault(module, 'comp', '')

    # Get parameters
    comp = Params.get(module, 'comp')

    def initCallback(self, scenario):
        # Initialization code
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        self.conn_timeout = False
        self.host_output_path = self.scenario.result_dir + f"\\{self.module}"
        self.output_dir = f"c:\\hobl_data\\{self.module}"
        self._call(["cmd.exe", f"/C if not exist \"{self.output_dir}\" mkdir \"{self.output_dir}\""])

    def testBeginCallback(self):
        self._call(["cmd.exe", "/C pktmon stop"], expected_exit_code="")
        self.file_name = Params.getCalculated("test_name")
        if self.comp == "":
            self._call(["cmd.exe", "/C pktmon start --capture --pkt-size 0 -f " + self.output_dir + "\\pktmon.etl"])
        else:
            self._call(["cmd.exe", "/C pktmon start --capture --pkt-size 0 -f " + self.output_dir + "\\pktmon.etl --comp " + self.comp])
    
    def testEndCallback(self):
        self._call(["cmd.exe", f"/C pktmon stop > {self.output_dir}\\pktmon.txt"], expected_exit_code="")
        self._call(["cmd.exe", "/C xcopy /K /Y C:\\hobl_bin\\ssl_keys.log " + self.dut_data_path], fail_on_exception=False, expected_exit_code="")

    def dataReadyCallback(self):
        self.file_name = Params.getCalculated("test_name")

        etl_path = self.host_output_path + "\\pktmon.etl"
        pcap_path = self.host_output_path + "\\" + self.file_name + "_net_capture.pcap"
        self._host_call("cmd.exe /C pktmon etl2pcap " + etl_path + " --out " + pcap_path)

    def testTimeoutCallback(self):
        self._call(["cmd.exe", "/C pktmon stop"])
        self.conn_timeout = True
