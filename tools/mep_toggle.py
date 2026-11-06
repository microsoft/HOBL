# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Toggle on specified AI camera test
#
# Setup instructions:
#   None
##

from builtins import str
from builtins import *
from core.parameters import Params
import logging
import sys
import os
import time
import datetime
import builtins
import logging
import core.app_scenario
from core.parameters import Params
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
import selenium.common.exceptions as exceptions
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException


class Tool(core.app_scenario.Scenario):
    '''
    Enable/disable specified MEP features.

    Before scenario starts specified MEP features will be toggled according to the configured parameters.
    '''
    module = __module__.split('.')[-1]

    #Main toggle state features
    Params.setDefault(module, 'framing', '0', desc="framing feature ('0' for off, '1' for on).")
    Params.setDefault(module, 'eye_gaze', '0', desc="eye gaze feature ('0' for off, '1' for on).")
    Params.setDefault(module, 'blur', '0', desc="blur feature ('0' for off, '1' for on).")
    Params.setDefault(module, 'portraitlight', '0', desc="portrait light feature ('0' for off, '1' for on).")
    Params.setDefault(module, 'creative', '0', desc="creative feature ('0' for off, '1' for on).")

    #Radio button sub sections for features 
    Params.setDefault(module, 'standardframing', '0', desc="standard framing sub-feature ('0' for off, '1' for on).")
    Params.setDefault(module, 'cinematicframing', '0', desc="cinematic framing sub-feature ('0' for off, '1' for on).")
    Params.setDefault(module, 'portraitblur', '0', desc="portrait blur sub-feature ('0' for off, '1' for on).")
    Params.setDefault(module, 'standardblur', '0', desc="standard blur sub-feature ('0' for off, '1' for on).")
    Params.setDefault(module, 'standardeye', '0', desc="standard eye sub-feature ('0' for off, '1' for on).")
    Params.setDefault(module, 'enhancedeye', '0', desc="enhanced eye sub-feature ('0' for off, '1' for on).")
    Params.setDefault(module, 'illustrated', '0', desc="illustrated sub-feature ('0' for off, '1' for on).")
    Params.setDefault(module, 'animated', '0', desc="animated sub-feature ('0' for off, '1' for on).")
    Params.setDefault(module, 'watercolor', '0', desc="watercolor sub-feature ('0' for off, '1' for on).")

    # Get parameters
    dut_architecture = Params.get('global', 'dut_architecture')
    duration = Params.get(module, 'duration')
    platform = Params.get('global', 'platform')
    is_framing = Params.get(module, 'framing')
    is_eye_gaze = Params.get(module, 'eye_gaze')
    is_blur = Params.get(module, 'blur')
    is_plight = Params.get(module, 'portraitlight')
    is_creative = Params.get(module, 'creative')
    is_standardframing = Params.get(module, 'standardframing')
    is_cinematicframing = Params.get(module, 'cinematicframing')
    is_portraitblur = Params.get(module, 'portraitblur')
    is_standardblur = Params.get(module, 'standardblur')
    is_standardeye = Params.get(module, 'standardeye')
    is_enhancedeye = Params.get(module, 'enhancedeye')
    is_illustrated = Params.get(module, 'illustrated')
    is_animated = Params.get(module, 'animated')
    is_watercolor = Params.get(module, 'watercolor')

    already_started = False
    thread = None

    def setAIFeatures(self, id, effect_state):
        # Find the "Toggle Switch" element and check its state
        toggle_switch = self.driver.find_element_by_accessibility_id(id)
        toggle_state = toggle_switch.get_attribute("Toggle.ToggleState")

        # Output the state of the "Toggle Switch"
        if toggle_state != effect_state:
            toggle_switch.click()
            
    # testBeginEarly allows a scenario to init and begin the tool before the normal start time for tools and power recording.
    #   Example is idle_apps, where we want to record video of the launching of the apps, but the test doesn't really begin until
    #   everything is opened.
    def testBeginEarlyCallback(self, scenario):
        self.initCallback(scenario)
        self.testBeginCallback()
        self.already_started = True

    def initCallback(self, scenario):
        if self.already_started:
            return
        self.scenario = scenario
        self.conn_timeout = False
        self.stop_file = self.scenario.result_dir + "\\command_wrapper_stop.txt"

    def testBeginCallback(self):
        if self.already_started:
            return
        # Set up driver
        self._call([(self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"), (self.dut_resolved_ip + " " + self.app_port)], blocking=False)        
        time.sleep(1)
        desired_caps = {}
        desired_caps["app"] = "Root" 
        self.driver = self._launchApp(desired_caps)
        # Launch Bluetooth device settings
        if self.platform.lower() == 'windows':
            self._call(["powershell.exe", 'Start-Process "ms-settings:devices"'])
        time.sleep(3)

        # Click on camera
        self.driver.find_element_by_xpath('//*[contains(@Name, "Cameras")]').click()
        time.sleep(3)

        self.driver.find_element_by_xpath('//*[contains(@Name,"Maximize")]').click()
        time.sleep(3)

        camera_found = 0 
        # Click on Surface Camera Front
        try:
            self.driver.find_element_by_xpath('//*[contains(@Name, "Surface Camera Front")]').click()
            time.sleep(5)
            camera_found = 1
        except:
            logging.info("No Surface Camera Found ")
        if camera_found == 0:
            try: 
                self.driver.find_element_by_xpath('//*[contains(@Name, "QC Front Camera")]').click()
                time.sleep(5)
                camera_found == 1
            except:
                logging.info("No QC Camera Found ")

        try:
            # Check framing toggle state and perform action 
            self.setAIFeatures("SystemSettings_Camera_DigitalWindow_ToggleSwitch", self.is_framing)
            time.sleep(2)
        except:
            logging.error("Autoframing Camera toggle tag has changed")
            self.driver.find_element_by_xpath('//*[contains(@Name, "Close")]').click()
            time.sleep(1)
            self._kill("WinAppDriver.exe")
            self.fail("Framing Tag")
        
        if self.is_standardframing == '1':
            self.driver.find_element_by_xpath('//*[contains(@Name, "Standard framing")]').click()
            time.sleep(2)
        if self.is_cinematicframing == '1':
            self.driver.find_element_by_xpath('//*[contains(@Name, "Cinematic framing")]').click()
            time.sleep(2)

        #Tags have floated between these so nested try statements
        try:
            # Check eye gaze toggle state and perform action
            self.setAIFeatures("SystemSettings_Camera_EyeGazeCorrection_ControlOn_ToggleSwitch", self.is_eye_gaze)
            time.sleep(2)
        except:
            try:
                self.setAIFeatures("SystemSettings_Camera_EyeGazeCorrection_ToggleSwitch", self.is_eye_gaze)
                time.sleep(2)
            except:
                logging.error("Eye Gaze Camera toggle tag has changed")
                self.driver.find_element_by_xpath('//*[contains(@Name, "Close")]').click()
                time.sleep(1)
                self._kill("WinAppDriver.exe")
                self.fail("Eye Gaze Tag")

        if self.is_standardeye == '1':
            self.driver.find_element_by_xpath('//*[contains(@Name, "Standard")]').click()
            time.sleep(2)
        
        if self.is_enhancedeye == '1':
            self.driver.find_element_by_xpath('//*[contains(@Name, "Teleprompter")]').click()
            time.sleep(2)
        
        if self.is_eye_gaze == '1':
            self.driver.find_element_by_xpath('//*[contains(@Name, "Eye contact")]').click()
            time.sleep(2)

        try:
            # Check portrait toggle state and perform action
            self.setAIFeatures("SystemSettings_Camera_Effect1_ToggleSwitch", self.is_plight)
            time.sleep(2)
        except:
            logging.info("Portrait Light Camera toggle tag has changed or not found")

        try:
            # Check Creative toggle state and perform action
            self.setAIFeatures("SystemSettings_Camera_Effect2_ToggleSwitch", self.is_creative)
            time.sleep(2)
        except:
            logging.info("Creative Camera toggle tag has changed or not found")

        if self.is_illustrated == '1':
            self.driver.find_element_by_xpath('//*[contains(@Name, "Illustrated")]').click()
            time.sleep(2)
        if self.is_animated == '1':
            self.driver.find_element_by_xpath('//*[contains(@Name, "Animated")]').click()
            time.sleep(2)
        if self.is_watercolor == '1':
            self.driver.find_element_by_xpath('//*[contains(@Name, "Watercolor")]').click()
            time.sleep(2)
        
        try:
            # Check Creative toggle state and perform action
            self.driver.find_element_by_xpath('//*[contains(@Name, "Creative filters")]').click()
            time.sleep(2)
        except:
            logging.info("Creative Camera toggle tag has changed or not found")


        try:
            # Check blur toggle state and perform action
            self.setAIFeatures("SystemSettings_Camera_BackgroundSegmentation_ToggleSwitch", self.is_blur)
            time.sleep(2)
        except:
            logging.error("Blur Camera toggle tag has changed")
            self.driver.find_element_by_xpath('//*[contains(@Name, "Close")]').click()
            time.sleep(1)
            self._kill("WinAppDriver.exe")
            self.fail("Blur Tag")

        if self.is_portraitblur == '1':
            self.driver.find_element_by_xpath('//*[contains(@Name, "Portrait blur")]').click()
            time.sleep(2)
            

        if self.is_standardblur == '1':
            self.driver.find_element_by_xpath('//*[contains(@Name, "Standard blur")]').click()
            time.sleep(2)

        if self.is_blur == '1':
            self.driver.find_element_by_xpath('//*[contains(@Name, "Background effects")]').click()
            time.sleep(2)

        self.driver.find_element_by_xpath('//*[contains(@Name, "Close")]').click()
        logging.info("AI Features toggled")
        time.sleep(10)
        self._kill("WinAppDriver.exe")

    def testEndCallback(self):
        return
        
    def dataReadyCallback(self):
        #We can revert states back if we want here 
        time.sleep(5)

    def testScenarioFailed(self):
        logging.debug("Test failed, cleaning up.")
        self.dataReadyCallback()

    def testTimeoutCallback(self):
        self.dataReadyCallback()
        self.conn_timeout = True

    def cleanup(self):
        logging.debug("Cleanup")
        self.dataReadyCallback()

