
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Calls executables on the DUT, either blocking or non-blocking
#
# Setup instructions:
##

import logging
from core.app_scenario import Scenario
from core.parameters import Params
import os
import core.call_rpc as rpc


class Tool(Scenario):
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'executable', '') # Specify full path on DUT to file to be executed
    Params.setDefault(module, 'arguments', '')
    Params.setDefault(module, 'source_path', '') # Will be copied to c:\hobl_bin befor test
    Params.setDefault(module, 'results_path', '') # Will be copied to c:\hobl_data after test
    Params.setDefault(module, 'stop_command', '') # Will be copied to c:\hobl_data after test
    Params.setDefault(module, 'blocking', 'False')

    # Get parameters
    executable = Params.get(module, 'executable')
    arguments = Params.get(module, 'arguments')
    source_path = Params.get(module, 'source_path')
    results_path = Params.get(module, 'results_path')
    stop_command = Params.get(module, 'stop_command')
    blocking = Params.get(module, 'blocking')



    def initCallback(self, scenario):
        self.scenario = scenario
        # Copy over any source file/folder
        if self.source_path != "":
            self._upload(self.source_path, self.dut_exec_path)


    def testBeginCallback(self):
        # Make call to DUT
        logging.info("Executing call: " + self.executable + " " + self.arguments)
        output = self._call([self.executable, self.arguments], blocking = (self.blocking == "True"))
        logging.info("Output:")
        lines = output.split('\n')
        for line in lines:
            logging.info(line.strip("\r\n"))


    def testEndCallback(self):
        # Kill any processes that were started by this call
        if self.blocking == "False":
            if self.stop_command != "":
                self._call(["cmd.exe", '/c ' + self.stop_command], expected_exit_code="")
            else:
                self._kill(os.path.basename(self.executable))


        # Copy back specified results
        logging.debug("Copying results from " + self.results_path + " to " + self.result_dir)
        if self._check_remote_file_exists(self.dut_data_path):
            if self.results_path != "" and self._check_remote_file_exists(self.results_path):
                logging.info("Copying results to " + self.dut_data_path)
                self._call(["cmd.exe", '/c copy ' + self.results_path + ' ' + self.dut_data_path], expected_exit_code="")

            logging.debug("Copying SimpleRemote log file to " + self.dut_data_path)
            log_path = "C:\\simple_remote_*.log"
            self._call(["cmd.exe", '/c copy ' + log_path + ' ' + self.dut_data_path], expected_exit_code="")

            rpc.download(self.dut_ip, self.rpc_port, self.dut_data_path, self.result_dir)


    def dataReadyCallback(self):
        return
