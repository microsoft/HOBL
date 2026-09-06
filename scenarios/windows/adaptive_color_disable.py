# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Disable adaptive color
##

import time
import logging

import core.app_scenario


class AdaptiveColorDisable(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]

    is_prep = True

    def runTest(self):
        self._status_window(f"Disabling Adaptive Color setting for testing consistency.\nClosing UI for this.")
        logging.info("Launching WinAppDriver.exe on DUT")

        self._call([
            (self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"),
            (self.dut_resolved_ip + " " + self.app_port)],
            blocking=False
        )

        desired_caps = {}
        desired_caps["app"] = "Root"

        self.driver = self._launchApp(desired_caps)

        self._call(["cmd.exe", '/C start ms-settings:display'])
        time.sleep(1)

        try:
            toggle_switch = self.driver.find_element_by_xpath("//*[@Name = 'Adaptive color' and @ClassName = 'ToggleSwitch']")
        except:
            logging.info("Adaptive color setting not found, exiting.")
            self.driver.close()
            time.sleep(1)
            self.createPrepStatusControlFile()
            return

        if toggle_switch.is_selected():
            toggle_switch.click()
            logging.info(f"Adaptive color disabled")
        else:
            logging.info(f"Adaptive color already disabled")

        time.sleep(1)

        self.driver.close()
        self.createPrepStatusControlFile()


    def tearDown(self):
        core.app_scenario.Scenario.tearDown(self)

        logging.debug("Killing SystemSettings.exe")
        self._kill("SystemSettings")

        logging.debug("Killing WinAppDriver.exe")
        self._kill("WinAppDriver")


    def kill(self):
        try:
            logging.debug("Killing SystemSettings.exe")
            self._kill("SystemSettings.exe")
        except:
            pass

        try:
            logging.debug("Killing WinAppDriver.exe")
            self._kill("WinAppDriver.exe")
        except:
            pass
