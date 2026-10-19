# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Wireshark dumpcap tool

from core.parameters import Params
from core.app_scenario import Scenario
import logging
import sys
import time

class Tool(Scenario):
    '''
    Dump Wireshark capture.

    Utilizes Wireshark's dumpcap tool to capture network traffic on the specified interface.

    Parameters:
        interface: The network interface on which to capture traffic (e.g., 'Wi-Fi').
    '''
    module = __module__.split('.')[-1]

    # Set default parameters
    Params.setDefault(module, 'interface', 'Wi-Fi')

    # Get parameters
    interface = Params.get(module, 'interface')

    def initCallback(self, scenario):
        # Initialization code
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        self.conn_timeout = False

    def testBeginCallback(self):
        self.file_name = Params.getCalculated("test_name")
        self._call(["C:\\Program Files\\wireshark\\dumpcap.exe", "-i " + self.interface + " -p -w c:\\hobl_data\\" + self.file_name + "_net_capture.pcap"], blocking = False)
    
    def testEndCallback(self):
        self._kill("dumpcap.exe")
        self._call(["cmd.exe", "/C xcopy /K /Y C:\\hobl_bin\\ssl_keys.log " + self.dut_data_path], fail_on_exception=False, expected_exit_code="")


    def dataReadyCallback(self):
        return

    def testTimeoutCallback(self):
        self._kill("dumpcap.exe")
        self.conn_timeout = True

    def cleanup(self):
        self.testEndCallback()
