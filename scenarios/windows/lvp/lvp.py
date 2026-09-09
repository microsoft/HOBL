# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Play a local video
#
# Setup instructions:
#   Copy Tears of Steel to default Video folder
##

from builtins import str
import logging
import os
import core.app_scenario
from core.parameters import Params
import time
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import selenium.common.exceptions as exceptions
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

class LVP(core.app_scenario.Scenario):
    """
    Plays a video on full screen for a specified amount of time.  
    """

    module = __module__.split('.')[-1]

    # Set default parameters
    Params.setDefault(module, 'title', 'ToS-4k-1920', desc="The file name of the video") # Just has to be unique substring of title
    Params.setDefault(module, 'duration', '300', desc="Time to play the video in seconds") # Seconds
    Params.setDefault(module, 'airplane_mode', '0', desc="Enable airplane mode during video playback", valOptions=["0", "1"])
    Params.setDefault(module, 'radio_enable', '1', desc="Enable or disable radio during video playback if airplane_mode parameter is set to 1", valOptions=["0", "1"])

    # Local parameters
    enable_screenshot = '1'

    prep_scenarios = ["lvp_prep"]


    def setUp(self):
        # Get parameters
        self.title = Params.get(self.module, 'title')
        self.duration = Params.get(self.module, 'duration')
        self.airplane_mode = Params.get(self.module, 'airplane_mode')
        self.platform = Params.get('global', 'platform')
        self.training_mode = Params.get('global', 'training_mode')
        self.radio_enable = Params.get(self.module, 'radio_enable')

        # If training mode, just 1 fast loop
        if self.training_mode == "1":
            self.duration = '10'
        
        self.airplane_enabled_duration = int(self.duration) + 15

        # Call tool early callbacks, particularly to get video recording of the setup
        self.toolCallBacks("testBeginEarlyCallback")

        logging.info("Launching WinAppDriver.exe on DUT.")

        self._call([(self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"), (self.dut_resolved_ip + " " + self.app_port)], blocking=False)
        time.sleep(1)

        logging.info("Starting App")
        self.driver = self.launchApp()
        self.driver.maximize_window()
        self.playMovie()

        if self.airplane_mode != '1':
            # match the timing of the airplane mode case.
            time.sleep(10)

        # Call base class setUp() to dump config, and start tools
        core.app_scenario.Scenario.setUp(self, callback_test_begin="")

        if self.airplane_mode == '1':
            try:
                # Set up 2nd config -Prerun command string for lvp_wrapper.cmd
                override_str = '[{\'Scenario\': \'' + self.module + '\'}]'
                config_str = os.path.join(self.dut_exec_path, "config_check.ps1 -Prerun -LogFile " + self.dut_data_path, self.testname + "_ConfigPre") + " -OverrideString " + '\\\"' + override_str + '\\\""'
                logging.info("CONFIG_STR: " + config_str)
                logging.info("Enabling airplane mode for " + str(self.airplane_enabled_duration) + " seconds.")
                if self.radio_enable == '0':
                    logging.info("cmd.exe /C " + os.path.join(self.dut_exec_path + "lvp_resources" + "lvp_wrapper.cmd") + ' ' + str(self.airplane_enabled_duration) + ' ' + self.dut_exec_path + ' ' + "APM " + config_str)
                    self._call(["cmd.exe", "/C " + os.path.join(self.dut_exec_path, "lvp_resources", "lvp_wrapper.cmd") + ' ' + str(self.airplane_enabled_duration) + ' ' + self.dut_exec_path + ' ' + "APM " + config_str], blocking = False)
                else:
                    logging.info("cmd.exe /C " + os.path.join(self.dut_exec_path + "lvp_resources" + "lvp_wrapper.cmd") + ' ' + str(self.airplane_enabled_duration) + ' ' + self.dut_exec_path + ' ' + "RadioEnable " + config_str)
                    self._call(["cmd.exe", "/C " + os.path.join(self.dut_exec_path, "lvp_resources", "lvp_wrapper.cmd") + ' ' + str(self.airplane_enabled_duration) + ' ' + self.dut_exec_path + ' ' + "RadioEnable " + config_str], blocking = False)
            except:
                pass

            # Delay to let airplane mode enable
            time.sleep(10)

        # Start recording power
        self._callback(Params.get('global', 'callback_test_begin'))


    def runTest(self):
        logging.info("Duration: " + self.duration + " sec.")

        # Let play for specified duration
        time.sleep(float(self.duration))


    def launchApp(self):
        logging.info("Launching LVP")
        desired_caps = {}

        try:
            # Try to launch new Media Player
            desired_caps["app"] = "Microsoft.ZuneMusic_8wekyb3d8bbwe!microsoft.ZuneMusic"
            driver = self._launchApp(desired_caps)
            time.sleep(5)
            driver.find_element_by_name("Video library")
        except:
            # Close ZuneMusic if it was opened
            try:
                logging.debug("Killing Music.UI.exe")
                self._kill("Music.UI.exe")
            except:
                pass
            try:
                logging.debug("Killing Media.Player.exe")
                self._kill("Microsoft.Media.Player.exe")
            except:
                pass

            # Launch Movies and TV
            desired_caps["app"] = "Microsoft.ZuneVideo_8wekyb3d8bbwe!microsoft.ZuneVideo"
            driver = self._launchApp(desired_caps)

            if self.training_mode == "1":
                time.sleep(5)
                # Look to see if video library access pop-up exists
                try:
                    driver.find_element_by_name("Yes").click()
                    time.sleep(2)
                except NoSuchElementException as EX:
                    pass
                # Look to see if Got it pop-up exists
                try:
                    logging.info("Click Got it pop-up")
                    driver.find_element_by_name("What's new popup got it").click()
                    time.sleep(2)
                except NoSuchElementException as EX:
                    pass

        return driver


    def playMovie(self):
        logging.info("Playing " + self.title)

        try:
            # Navigate to Video library
            self.driver.find_element_by_name("Video library").click()
            time.sleep(1)

            # Find specified movie title
            self.driver.find_element_by_xpath(f"//*[contains(@Name, '{self.title}')]").click()
            time.sleep(2)

            # Inject space to pause video using ActionChains
            ActionChains(self.driver).send_keys(Keys.SPACE).perform()
            
            # ActionChains(self.driver).move_to_element(
            #     self.driver.find_element_by_class_name("LandmarkTarget")
            # ).perform()

            time.sleep(2)

            logging.info("Selecting repeat button on DUT.")

            for _ in range(2):
                app_bar_button = self.driver.find_element_by_xpath(
                    f"//*[contains(@Name, 'Repeat: ') and @ClassName = 'AppBarButton']"
                )

                if app_bar_button.get_attribute("Name") == "Repeat: All":
                    break
                else:
                    app_bar_button.click()

            logging.info("Setting to full screen.")

            self.driver.find_element_by_xpath(
                f"//*[contains(@Name, 'Full screen') and @ClassName = 'AppBarButton']"
            ).click()

            # Inject space to resume
            ActionChains(self.driver).send_keys(Keys.SPACE).perform()

            ActionChains(self.driver).move_by_offset(-200, -200).perform()
        except:
            # Navigate to Personal menu
            self.driver.find_element_by_name("Personal").click()

            # Find specified movie title
            self.driver.find_element_by_xpath('//*[contains(@Name,"' + self.title + '")]').click()
            time.sleep(4)

            try:
                logging.info("Selecting repeat button on DUT.")
                self.driver.find_element_by_name("More").click()
                time.sleep(1.3)

                self.driver.find_element_by_name("Turn repeat on").click()
                time.sleep(2)
            except NoSuchElementException as EX:
                logging.info("Repeat button not found.")
                time.sleep(2)
                pass

            # set to full screen
            try:
                self.driver.find_element_by_name("Full Screen").click()
            except:
                logging.info("Did not find the button for full screen.")

            # Move mouse away from the menu
            time.sleep(5)
            ActionChains(self.driver).move_by_offset(150, -150).perform()

    def tearDown(self):
        logging.info("Performing teardown.")

       # Stop recording power
        self._callback(Params.get('global', 'callback_test_end'))

        # Take screenshot at end of loop to make sure everything was closed properly
        if self.enable_screenshot == '1' and Params.get("global", "local_execution") == "1":
            self._screenshot(name="end_screen.png")

        # Allow time for lvp_wrapper to turn radios back on
        time.sleep(10)
        if self.airplane_mode =='1':
            try:
                if self.radio_enable == '0':
                    logging.info("cmd.exe /C " + os.path.join(self.dut_exec_path, "lvp_resources\\AirplaneMode.exe -Disable"))
                    self._call(["cmd.exe", "/C " + os.path.join(self.dut_exec_path, "lvp_resources", "AirplaneMode.exe") + " -Disable"], blocking = False)
                else:
                    logging.info("cmd.exe /C " + os.path.join(self.dut_exec_path, "lvp_resources\\RadioEnable.exe -Enable"))
                    self._call(["cmd.exe", "/C " + os.path.join(self.dut_exec_path, "lvp_resources", "radioenable.exe") + " -Enable"], blocking = False)
            except:
                pass

        # Allow plenty of time for wifi to come back up
        time.sleep(30)
        core.app_scenario.Scenario.tearDown(self, callback_test_end="")

        self._kill("WinAppDriver.exe")


    def kill(self):
        try:
            logging.debug("Killing Music.UI.exe")
            self._kill("Music.UI.exe")
        except:
            pass

        try:
            logging.debug("Killing Video.UI.exe")
            self._kill("Video.UI.exe")
        except:
            pass

        try:
            logging.debug("Killing Media.Player.exe")
            self._kill("Microsoft.Media.Player.exe")
        except:
            pass
