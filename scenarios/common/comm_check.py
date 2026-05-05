# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Idle at the Desktop
#
# Setup instructions:
#   None
##

import logging

import qoi
from PIL import Image
import core.app_scenario
from core.parameters import Params
import core.call_rpc as rpc
import json
import time


class CommCheck(core.app_scenario.Scenario):
    '''
    Checks for valid communications between host and DUT.
    
    Steps:
    
    1. Ping DUT
    2. SimpleRemote RPC call
    3. SimpleRemote Async call
    4. WinAppDriver launch and communication
    5. Report results
    '''

    module = __module__.split('.')[-1]

    Params.setOverride("global", "prep_tools", "")
    is_prep = True

    def setUp(self):
        # Intentionally not calling base method to prevent extraneous call attempts to DUT
        pass


    def runTest(self):
        failed = False

        # Ping
        ping_result = self._host_call("cmd.exe /c ping.exe /4 " + self.dut_ip + " -n 1", expected_exit_code="")
        if "unreachable" in ping_result:
            logging.info("Ping: FAIL")
        elif ("Sent = 1, Received = 1, Lost = 0 (0% loss)" in ping_result):
            logging.info("Ping:\t\t\tOK")
        else:
            logging.info("Ping:\t\t\tFAIL")
            failed = True

        # Sync SimpleRemote
        try:
            output = rpc.call_rpc(self.dut_ip, self.rpc_port, "GetVersion", [], timeout = 5)
            if "result" in output:
                sr_version_json = json.loads(output)
                ver = sr_version_json["result"]
                logging.info("SimpleRemote Sync:\tOK (version = " + ver + ")")
            else:
                logging.info("SimpleRemote Sync:\tFAIL")
                failed = True
        except:
            logging.info("SimpleRemote Sync:\tFAIL")
            failed = True

        # Async SimpleRemote
        if (self.async_comm == "1"):
            try:
                output = self._call(["curl", "-V"], timeout=5)
                # if self.platform.lower() == "windows":
                #     output = self._call(["cmd.exe", "/c echo ok"], timeout=5)
                # elif self.platform.lower() == "macos":
                #     output = self._call(["zsh", '-c "echo ok"'], timeout=5)
                # else:
                #     logging.error(f"Unsupported platform {self.platform}")
                #     self.fail(f"Unsupported platform {self.platform}")
                logging.debug(output)
                if "Release-Date" in output:
                    logging.info("SimpleRemote Async:\tOK")
                else:
                    logging.info("SimpleRemote Async:\tFAIL")
                    failed = True
            except:
                logging.info("SimpleRemote Async:\tFAIL")
                failed = True

        # WinAppDriver
        # try:
        if self.platform.lower() == "windows":
            self._call([(self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"), (self.dut_resolved_ip + " " + self.app_port)], blocking=False, timeout=5)
            time.sleep(1)
            desired_caps = {}
            desired_caps["app"] = "Root"
            desktop = self._launchApp(desired_caps)
            logging.info("WinAppDriver launch:\tOK")
            # except:
            #     logging.info("WinAppDriver launch:\tFAIL")
            #     failed = True

            try:
                desktop.find_element_by_name("Start")
                self._kill("winappdriver.exe")
                logging.info("WinAppDriver comm:\tOK")
            except:
                logging.info("WinAppDriver comm:\tFAIL")
                self._page_source(desktop)
                failed = True
        
        if failed:
            self.fail("At least one communication check failed")

        # Calculate roundtrip time for how long it takes for a screenshot to be sent back to host.
        start_time = time.time()
        screen_data = rpc.plugin_screenshot(self.dut_ip, self.rpc_port, "InputInject")
        img_array = qoi.decode(screen_data)
        image = Image.fromarray(img_array)
        image.save(self.result_dir + "/screenshot.png")
        end_time = time.time()
        roundtrip_time = end_time - start_time
        logging.info(f"Screenshot roundtrip time: {roundtrip_time:.2f} seconds")




    def tearDown(self):
        # Don't call base tearDown so that we don't interact with DUT.
        pass


    def kill(self):
        # Prevent base kill routine from running
        return 0
