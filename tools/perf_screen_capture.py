# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Template for creating a tool wrapper

import os
import logging
from scenarios.app_scenario import Scenario
import utilities.call_rpc as rpc

class Tool(Scenario):
    '''
    A tool that captures partial screen recordings for later performance analysis.
    '''
    module = __module__.split('.')[-1]
    perf_path_name = "perf_screenshots"

    def initCallback(self, scenario):
        # Initialization code
        if self.platform.lower() == "windows":
            if not self._check_remote_file_exists("ffmpeg.exe"):
                self._upload("downloads\\ffmpeg_win64\\bin\\ffmpeg.exe", self.dut_exec_path)

        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario

        logging.info("Perf Screen Capture Tool - Clearing capture memory")
        try:
            rpc.plugin_clear_captures(self.dut_ip, self.rpc_port, "InputInject")
        except Exception as e:
            logging.warning(f"Error clearing capture memory: {e}")
        return

    def testBeginCallback(self):
        return

    def testEndCallback(self):

        logging.info("Perf Screen Capture Tool - Writing screenshots to results directory")
        output_path = os.path.join(self.scenario.dut_data_path, self.perf_path_name)
        rpc.plugin_write_captures_to_disk(self.dut_ip, self.rpc_port, "InputInject", output_path)
        return

    def dataReadyCallback(self):
        # You can do any post processing of data here.
        logging.info("Perf Screen Capture Tool - dataReadyCallback")
        self._host_call("python utilities\\open_source\\perf_process.py " + self.scenario.result_dir, expected_exit_code="")
        
        return
    
    def cleanup(self):
        self.kill_proc()

    def kill_proc(self):
        rpc.plugin_stop_performance_capture(self.dut_ip, self.rpc_port, "InputInject")
        rpc.plugin_clear_captures(self.dut_ip, self.rpc_port, "InputInject")