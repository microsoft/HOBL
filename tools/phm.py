# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from core.app_scenario import Scenario
import logging
import time
import sys
import glob


class Tool(Scenario):
    '''
    Run Intel's Power House Mountain tool.
    '''
    module = __module__.split('.')[-1]

    # Set default parameters
    # phm_args must be comma separated
    Params.setDefault(module, 'node', 'C:\\Program Files\\nodejs\\node.exe')
    # Params.setDefault(module, 'phm_args', 'all')
    Params.setDefault(module, 'phm_args', '!cpup')
    Params.setDefault(module, 'phm_base_path', 'C:\\Program Files\\PowerhouseMountain\\')
    Params.setDefault(module, 'phm_server', 'app.js')
    Params.setDefault(module, 'phm_trace', 'phm-client.js')
    Params.setDefault(module, 'phm_dut_trace_path', 'C:\\Program Files\\PowerhouseMountain\\traces')

    # Get parameters
    node = Params.get(module, 'node')
    phm_args = Params.get(module, 'phm_args')
    phm_base_path = Params.get(module, 'phm_base_path')
    phm_server = Params.get(module, 'phm_server')
    phm_trace = Params.get(module, 'phm_trace')
    phm_dut_trace_path = Params.get(module, 'phm_dut_trace_path')

    def initCallback(self, scenario):
        # Pointer to scenario this tool is being run with
        self.scenario = scenario
        self.conn_timeout = False

        # remove whitespace from phm_args
        logging.info("Removing white space from phm_args...")
        self.phm_args = "".join(self.phm_args.split())

        # # Append appropriate pch paramter if necessary
        # if "all" not in self.phm_args:
        #     if "pch[" not in self.phm_args:
        #         cs_scenarios = ["cs_active", "cs_floor", "abl_standby"]
        #         is_cs = [ele for ele in cs_scenarios if (ele in str(scenario))]
        #         if bool(is_cs):
        #             self.phm_args += ',pch[lvl4+lvl5]'
        #         else:
        #             self.phm_args += ',pch[lvl1]'

        # Remove existing traces from DUT
        logging.info("Cleaning up " + self.phm_dut_trace_path)
        self._call(["cmd.exe", " ".join(["/C", "DEL /F/Q/S", '"' + self.phm_dut_trace_path + '\\*"'])], expected_exit_code="")

        # Terminate existing PHM server
        logging.info("Terminating existing PHM servers...")
        self._kill("node.exe")
        # self._call(['cmd.exe', '/C taskkill /f /T /IM ' + "node.exe"], expected_exit_code="")
        time.sleep(2)

        # Start PHM server on the DUT
        logging.info("Starting PHM server...")
        self._call([self.node, '"' + self.phm_base_path + self.phm_server + '"' + " 1337"], blocking=False)
        time.sleep(5)
        logging.info("PHM server is now running.")

    def testBeginCallback(self):
        # Start PHM Trace on the DUT
        logging.info("Starting PHM trace...")
        self._call([self.node, '"' + self.phm_base_path + self.phm_trace + '"' + " -p 1337 start -s man -d " + self.phm_args], fail_on_exception=False, expected_exit_code="")
        logging.info("PHM trace is now running.")

    def testEndCallback(self):
        # Stop PHM Trace on the DUT
        logging.info("Stoping PHM trace...")
        self._call([self.node, '"' + self.phm_base_path + self.phm_trace + '"' + " -p 1337 stop"], timeout=3600, fail_on_exception=False, expected_exit_code="")
        time.sleep(5)
        logging.info("PHM trace stopped.")

        if not self.conn_timeout:
            # Copy over trace to results dir
            logging.info("Moving PHM trace to " + self.dut_data_path)
            self._call(["robocopy.exe", " ".join(["/MOVE", "/S", '"' + self.phm_dut_trace_path + '"', self.dut_data_path])], expected_exit_code="")        

    def cleanup(self):
        # Terminate PHM server
        logging.info("Terminating PHM server...")
        self._kill("node.exe")
        # self._call(['cmd.exe', '/C taskkill /f /T /IM ' + "node.exe"])
        logging.info("PHM server terminated.")
        time.sleep(5)

        # Clean up trace directory
        logging.info("Cleaning up " + self.phm_dut_trace_path)
        self._call(["cmd.exe", " ".join(["/C", "DEL /F/Q/S", '"' + self.phm_dut_trace_path + '\\*"'])], expected_exit_code="")

    def dataReadyCallback(self):
        if self.conn_timeout:
            return

        logging.info("PHM tool dataReadyCallback")
        logging.info("collection_enabled = " + Params.get('global', 'collection_enabled'))
        if Params.get('global', 'collection_enabled') != '0':
            logging.info("Parsing PHM data...")
            # host call of script_path
            infile = glob.glob(self.scenario.result_dir + "\\Scenario20*\\**\\Mountains.csv", recursive=True)
            infile = infile[0]
            outfile = self.scenario.result_dir + "\\" + self.scenario.testname + "_PHM.csv"
            self._host_call("python.exe utilities\\open_source\\parse_socwatch.py" + " -i " + infile + " -o " + outfile)

    def testTimeoutCallback(self):
        self.conn_timeout = True
