# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from core.app_scenario import Scenario
import logging
import time
import os

class Tool(Scenario):
    '''
    Records a screen cast from the DUT for debug purposes.  Has considerable power impact.
    '''
    module = __module__.split('.')[-1]
    Params.setDefault(module, 'device_index', '2', desc="MacOS-only.  1 for older or non-Pro macbooks", valOptions=["1", "2"])  # MacOS-only.  1 for older or non-Pro macbooks

    device_index = Params.get(module, 'device_index')

    already_started = False

    def testBeginEarlyCallback(self, scenario):
        self.initCallback(scenario)
        self.testBeginCallback()
        self.already_started = True

    def initCallback(self, scenario):
        if self.already_started:
            return
        self.conn_timeout = False
        self.scenario = scenario
        if self.platform.lower() == "windows":
            if not self._check_remote_file_exists("ffmpeg.exe"):
                self._upload("downloads\\ffmpeg_win64\\bin\\ffmpeg.exe", self.dut_exec_path)
            if not self._check_remote_file_exists("command_wrapper.ps1"):
                self._upload("utilities\\open_source\\command_wrapper.ps1", self.dut_exec_path)
            self.stop_file = os.path.join(self.dut_exec_path, "command_wrapper_stop.txt")
        elif self.platform.lower() == "macos":
            # self._upload("downloads\\ffmpeg_macos\\ffmpeg", self.dut_exec_path) # ffmpeg is installed by dut_setup.sh on macOS.
            self._upload("utilities\\open_source\\command_wrapper.sh", self.dut_exec_path)
            self.stop_file = self.dut_exec_path + "/command_wrapper_stop.txt"

    def testBeginCallback(self):
        if self.already_started:
            return
        self.scenario.ffmpeg_launched = True

        if self.platform.lower() == "windows":
            output_file = os.path.join(self.scenario.dut_data_path, self.scenario.testname + "_recording.mp4")
            cmd = os.path.join(self.dut_exec_path, "ffmpeg.exe")
            args = "-f gdigrab -framerate 6 -i desktop -loglevel quiet -c:v libx264 -tune stillimage -crf 40 -pix_fmt yuv420p " + output_file
            stop_key = "q"
            self._call(["powershell.exe", os.path.join(self.dut_exec_path, "command_wrapper.ps1"), " \"" + cmd + " \'" + args + "\' " + self.stop_file + " " + stop_key + "\"" ], blocking=False)
        elif self.platform.lower() == "macos":
            output_file = self.scenario.dut_data_path + "/" + self.scenario.testname + "_recording.mp4"
            cmd = "/opt/homebrew/bin/ffmpeg"
            args = f"-capture_cursor 1 -capture_mouse_clicks 1 -f avfoundation -framerate 6 -i {self.device_index} -loglevel quiet -c:v libx264 -tune stillimage -crf 40 -pix_fmt yuv420p " + output_file
            self._call(["/bin/bash", self.dut_exec_path + "/command_wrapper.sh " + cmd + " \"" + args + "\" " + self.stop_file + " " + "kill"], blocking=False)

        logging.info("Screen Recording started.")
        self.scenario.video_startTime = time.time()
        time.sleep(0.5)

    def testEndCallback(self):
        try:
            if not self._check_remote_file_exists(self.stop_file, in_exec_path=False):
                if self.platform.lower() == "windows":
                    self._call(["cmd.exe", "/C echo q > " + self.stop_file])
                elif self.platform.lower() == "macos":
                    self._call(["/bin/bash", '-c "echo q > ' + self.stop_file + '"'])
                logging.info("Screen Recording stopped.")
                # Give time to write file
                time.sleep(20)
                # # Just in case it didn't close gracefully
                # time.sleep(10)
                # self._kill("ffmpeg.exe")
            else:
                logging.info("Screen Recording already stopped.")
        except:
            pass

    def dataReadyCallback(self):
        pass

    def testScenarioFailed(self):
        logging.debug("Test failed, cleaning up.")
        self.testEndCallback()

    def testTimeoutCallback(self):
        self.testEndCallback()
        self.conn_timeout = True
        
    def cleanup(self):
        self.testEndCallback()

