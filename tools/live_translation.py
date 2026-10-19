# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Tool wrapper for audio control

from builtins import str
from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import logging
import time
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

class Tool(Scenario):
    '''
    Setups up the Live Translation feature on the DUT.

    '''
    module = __module__.split('.')[-1]

    def initCallback(self, scenario):

        self.scenario = scenario
        self._call([(self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"), (self.dut_resolved_ip + " " + self.app_port + " /forcequit")], expected_exit_code="", blocking=False)
        time.sleep(1)

        # Connect to desktop to be able to launch apps with Start menu
        desired_caps = {}
        desired_caps["app"] = "Root"
        self.desktop = self._launchApp(desired_caps)
        self.desktop.implicitly_wait(0)

        logging.info("Starting Live Translation Ribbon")

        ActionChains(self.desktop).key_down(Keys.CONTROL).key_down(Keys.META).send_keys("l").key_up(Keys.META).key_up(Keys.CONTROL).perform()
        time.sleep(3)
        # Try to look for downloading of model
        try:
            self.desktop.find_element_by_name("Yes, continue").click()
            time.sleep(180)
        except:
            pass

        try:
            self.desktop.find_element_by_name("Continue").click()
            time.sleep(3)
        except:
            pass

        #live_caption = self.desktop.find_element_by_name("Live Captions")
        self.desktop.find_element_by_name("Settings").click()
        time.sleep(3)
        #self._page_source(self.desktop)
        #self.desktop.find_element_by_name("Postion").click()
        live_caption = self.desktop.find_element_by_name("Live Captions")
        #self.desktop.find_element_by_accessibility_id("DockPositionButton").click()
        live_caption.find_element_by_accessibility_id("DockPositionButton").click()
        time.sleep(3)
        self.desktop.find_element_by_name("Above screen").click()
        time.sleep(3)

        if scenario.training_mode == "0":
            self._kill("WinAppDriver.exe")
        return

    def testBeginCallback(self):
        pass

    def testEndCallback(self):
        self._kill("LiveCaptions.exe")
        return

    def dataReadyCallback(self):
        pass

    def testScenarioFailed(self):
        self.testEndCallback()

    def testTimeoutCallback(self):
        self.testEndCallback()
        self.conn_timeout = True
        
    def cleanup(self):
        self.testEndCallback()


