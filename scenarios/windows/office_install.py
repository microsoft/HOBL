# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Install Office 365 using the Office Deployment Tool
# Optionally associate with activated account.
##

import builtins
from email.mime import text
from email.mime import text
import logging
import core.app_scenario
from core.parameters import Params
import os
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import utilities.call_rpc as rpc


class OfficeInstall(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'install', '1')
    Params.setDefault(module, 'activate', '0')
    Params.setDefault(module, 'post_install_call', '')

    # Get parameters
    msa_account = Params.get('global', 'msa_account')
    dut_password = Params.get('global', 'dut_password')
    install = Params.get(module, 'install')
    activate = Params.get(module, 'activate')
    post_install_call = Params.get(module, 'post_install_call')
    local_execution = Params.get('global', 'local_execution')

    # Override collection of config data, traces, and execution of callbacks 
    is_prep = True

    # Local parameters
    
    prep_scenarios = []
    enable_screenshot = '0'


    def setUp(self):
        core.app_scenario.Scenario.setUp(self)

    def runTest(self):
        if self.install == '1':
            # Install
            # 64b version works on all platforms now, so just using that.
            self._upload("utilities\\proprietary\\OfficeDeployment", self.dut_exec_path)

            # Delete productivity prep folder from prep status so it needs to be reran whenever office install removes office to reinstall.
            try:
                logging.info("Deleting productivity prep status folder.")
                self._call(["cmd.exe", "/C rmdir /s /q " + self.dut_exec_path + "\\prep_status" + "\\productivity_prep"], expected_exit_code="")
            except:
                pass

            odt_path = self.dut_exec_path + "\\OfficeDeployment"
            # Remove any existing installations
            logging.info("Removing any existing Office installations")
            self._call([odt_path + "\\setup.exe", "/configure " + odt_path + "\\remove.xml"], expected_exit_code="")
            
            # Disable the activation nag
            self._call(["cmd.exe", "/C reg add HKLM\\SOFTWARE\\Microsoft\\Office\\16.0\\Common\\Licensing /v DisableActivationUI /t REG_DWORD /f /d 00000001"])
            self._call(["cmd.exe", "/C reg add HKLM\\SOFTWARE\\Wow6432Node\\Microsoft\\Office\\16.0\\Common\\Licensing /v DisableActivationUI /t REG_DWORD /f /d 00000001"])

            # Install the new one
            logging.info("Installing Office365")
            self._call([odt_path + "\\setup.exe", "/configure " + odt_path + "\\install_o365.xml"])

            # Close installation complete dialog
            self._kill("OfficeC2RClient.exe")

            # Disable OneNote inking mode
            self._call(["cmd.exe", "/C reg add HKCU\\SOFTWARE\\Microsoft\\Office\\16.0\\OneNote\\Options /v FullPageModeOnPenUndock /t REG_DWORD /f /d 00000000"])

            # Force Fluent UI update
            self._call(["cmd.exe", "/C reg add HKCU\\Software\\Microsoft\\Office\\16.0\\Common\\ExperimentEcs\\Overrides /v Microsoft.Office.UXPlatform.FluentSVRefresh /t REG_SZ /d true /f"])

            # Use System Theme
            self._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Office\\16.0\\Common" /v "UI Theme" /t REG_DWORD /d 6 /f > null 2>&1'])
            regpath = self._call(["cmd.exe", '/C reg query "HKCU\\SOFTWARE\\Microsoft\\Office\\16.0\\Common\\Roaming\\Identities"'], expected_exit_code="")
            regpath = regpath.strip()
            reg_ary = regpath.split()
            if len(reg_ary) > 0:
                regpath = reg_ary[0]
                if "Anonymous" in regpath and len(reg_ary) > 1:
                    regpath = reg_ary[1]
            logging.debug(f"Office identity regpath: {regpath}")
            if regpath != "" and "ERROR" not in regpath:
                regpath = regpath + "\\Settings\\1186\\{00000000-0000-0000-0000-000000000000}"
                self._call(["cmd.exe", '/C reg add "' + regpath + '" /v "Data" /t REG_BINARY /d 06000000 /f > null 2>&1'])
            else:
                logging.warning("No Office identity found in registry.")

            # post_install_call
            if self.post_install_call != '':
                self._call(["cmd.exe", "/C " + self.post_install_call])

            # Disable OneNote full screen on pen undock.
            self._call(["cmd.exe", r"/C reg add HKCU\Software\Microsoft\Office\16.0\OneNote\Options /v FullPageModeOnPenUndock /t REG_DWORD /f /d 00000000"])

            # # Reboot            
            # logging.info("Rebooting and waiting for DUT communication")
            # if self.local_execution == "0":            
            #     self._call(["cmd.exe",  "/C shutdown.exe /r /f /t 5"], blocking=False)
            #     # Poll for simple remote to determine is DUT setup is complete
            #     time.sleep(15)
            #     self._wait_for_dut_comm()
            if self.activate == '0':
                self.createPrepStatusControlFile()
            
        elif self.post_install_call != '':
            self._call(["cmd.exe", "/C " + self.post_install_call])
            self.createPrepStatusControlFile()

        logging.debug("Launching WinAppDriver.exe on DUT.")
        self._call([self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe", self.dut_resolved_ip + " " + self.app_port + " /forcequit"], blocking=False)
        time.sleep(1)

        desired_caps = {}
        desired_caps["app"] = "Root"
        desktop = self._launchApp(desired_caps, track_driver=False)
        desktop.implicitly_wait(30)

        # Activate
        if self.activate == '1':
            self._call(["cmd.exe", "/C reg delete HKLM\\SOFTWARE\\Microsoft\\Office\\16.0\\Common\\Licensing /v DisableActivationUI /f"], expected_exit_code="")
            self._call(["cmd.exe", "/C reg delete HKLM\\SOFTWARE\\Wow6432Node\\Microsoft\\Office\\16.0\\Common\\Licensing /v DisableActivationUI /f"], expected_exit_code="")
 
            logging.info("Activating Office")
            # logging.debug("Launching WinAppDriver.exe on DUT.")
            # self._call([self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe", self.dut_ip + " " + self.app_port + " /forcequit"], blocking=False)
            # time.sleep(1)

            # desired_caps = {}
            # desired_caps["app"] = "Root"
            # desktop = self._launchApp(desired_caps, track_driver=False)
            # desktop.implicitly_wait(30)

            # Inject ESCAPE just in case Start menu was left open
            ActionChains(desktop).send_keys(Keys.ESCAPE).perform()
            # Open Word
            app = "Word"
            self._get_search_button(desktop).click()
            time.sleep(5)        
            # Type slowly in Start menu, send 1 character at a time, otherwise Windows drops characters
            for key in "app:" + app:
                ActionChains(desktop).send_keys(key).perform()
                time.sleep(0.5)        
            time.sleep(10)
            app_item = desktop.find_element_by_name("Results").find_element_by_xpath('//*[contains(@Name,"' + app + ',' + '")]')
            app_item.click()

            # Try to activate
            word_win = desktop.find_element_by_class_name("OpusApp")
            driver = self.getDriverFromWin(word_win)
            driver.implicitly_wait(10)


            try:
                # Try to find Sign in button
                logging.info("Looking for 'Sign in' button")
                driver.find_element_by_xpath('//Button[contains(@Name,"Sign in")]').click()
                logging.info("Found 'Sign in' button")
            except:
                # Already activated
                logging.info("Not found, assuming Office is already activated")
            else:
                # Continue signing in
                # Note that accessibility tags aren't present here, so just type credentials blindly
                time.sleep(10)
                # Enter username
                logging.info("Entering username")
                rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "Type", self.msa_account + Keys.ENTER, 50)
                time.sleep(10)
                # Down and then enter to select "Use your password instead"
                logging.info("Selecting 'Use your password instead'")
                rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "Type", Keys.DOWN + Keys.ENTER, 50)
                time.sleep(5)
                # Enter password
                logging.info("Entering password")
                rpc.plugin_call(self.dut_ip, self.rpc_port, "InputInject", "Type", self.dut_password + Keys.ENTER, 50)
                time.sleep(10)
                
            time.sleep(5)
            try:
                # If "Microsoft respects your privacy" dialog is present, click Next
                logging.info("Looking for privacy dialog")
                driver.find_element_by_xpath('//*[contains(@Name,"privacy")]')
                driver.find_element_by_xpath('//Button[contains(@Name,"Next")]').click()
                time.sleep(5)
            except:
                logging.info("'Microsoft respects your privacy' dialog not found")

            self.createPrepStatusControlFile()



            # try:
            #     logging.info("Looking for 'confirm your account'")
            #     driver.find_element_by_xpath('//*[contains(@Name,"confirm your account")]')
            #     logging.info("Found Confirm dialog")
            #     self.confirmAccount(driver)
            # except:
            #     logging.info("...not found, clicking Account")
            #     driver.find_element_by_name("Account").click()
            #     try:
            #         logging.info("Looking for Activate button")
            #         driver.find_element_by_name("Activate Product").click()
            #         logging.info("Clicked Activate")
            #     except:
            #         # Already activated
            #         logging.info("Office already activated")
            #     else:
            #         # Confirm account
            #         time.sleep(2)
            #         self.confirmAccount(driver)
            # self._page_source(desktop)
            # try:
            #     logging.info("Looking for 'OK'")
            #     desktop.find_element_by_name("OK").click()
            #     logging.info("Clicked 'OK'")
            # except:
            #     logging.info("'OK' not found")
            #     pass
            # try:
            #     logging.info("Looking for 'Get started'")
            #     desktop.find_element_by_name("Get started").click()
            #     logging.info("Clicked 'Get started'")
            # except:
            #     logging.info("'Get started' not found")
            #     pass
            # try:
            #     logging.info("Looking for 'Got it'")
            #     desktop.find_element_by_name("Got it").click()
            #     logging.info("Clicked 'Got it'")
            # except:
            #     logging.info("'Got it' not found")
            #     pass
            # try:
            #     logging.info("Checking for 'cutting edge' pop up")
            #     cutting_edge = desktop.find_element_by_name("You're on the cutting edge")
            # except:
            #     pass
            # else:
            #     logging.info("'Cutting edge' window is present")
            #     cutting_edge.find_element_by_name("Close").click()
            #     time.sleep(1)
            # try:
            #     driver.close()
            #     time.sleep(2)
            # except:
            #     pass
        
        
        # # # Reboot            
        # if self.local_execution == "0":            
        #     logging.info("Rebooting and waiting DUT communication")
        #     self._call(["cmd.exe",  "/C shutdown.exe /r /f /t 5"], blocking=False)
        #     # Poll for simple remote to determine is DUT setup is complete
        #     time.sleep(15)
        #     self._wait_for_dut_comm()
        #     logging.info("Waiting 20 more seconds for startup apps to launch (Teams, OneNote, etc.)")
        #     time.sleep(20)
        
        # Wait for notification to disappear (not able to dismiss it)
        # self._page_source(desktop)
        # time.sleep(30)
        # Commented out above because notication is now disabled in msa_prep

        if self.enable_screenshot == '1':
            # Wait for notification to disappear (not able to dismiss it)
            logging.info("Waiting 45s for notification to disappear")
            time.sleep(45)
            self._screenshot(name="end_screen.png")


    def confirmAccount(self, driver):
        try:
            logging.info("Confirming account")
            driver.find_element_by_xpath('//*[contains(@Name,"confirm your account")]')
            driver.find_element_by_name("Next").click()
            time.sleep(10)
            driver.find_element_by_name("Next").click()
            time.sleep(60)
            driver.close()
        except:
            self.fail("Could not activate Office")
            driver.close()


    def tearDown(self):
        logging.info("Performing teardown.")
        # Stop recording before closing apps
        core.app_scenario.Scenario.tearDown(self)

        # Reboot for improved robustness
        logging.info("Rebooting after Office installation.")
        self._dut_reboot()

        self._kill("Winword.exe WinAppDriver.exe")


    def getWindowHandle(self, win):
        win_handle = int(win.get_attribute("NativeWindowHandle"))
        win_handle = format(win_handle, 'x') # convert to hex string
        return win_handle


    def getDriverFromWin(self, win):
        win_handle = self.getWindowHandle(win)
        # Launch new session attached to the window
        desired_caps = {}
        desired_caps["appTopLevelWindow"] = win_handle
        driver = self._launchApp(desired_caps, track_driver = False)
        logging.info("Connected to window.")
        time.sleep(2)  
        driver.switch_to_window(win_handle)
        # driver.maximize_window()
        return driver


    def kill(self):
        try:
            logging.debug("Killing open drivers")
            self._kill("Winword.exe WinAppDriver.exe officec2rclient.exe OfficeC2RClient")
        except:
            pass
        