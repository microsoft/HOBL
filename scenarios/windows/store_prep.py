# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Update store apps and then disable store updates on RS5 and 19h1 only
# 
##

import os
import logging
import time
from core.parameters import Params
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchWindowException
from selenium.common.exceptions import ElementNotVisibleException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
import core.app_scenario
from appium.webdriver.common.mobileby import MobileBy
from selenium.webdriver.common.action_chains import ActionChains


class StorePrep(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]
    Params.setDefault(module, "store_prep_enabled", "1", desc="Enables or disables store_prep execution.", valOptions=["0", "1"])

    # Override collection of config data, traces, and execution of callbacks 
    is_prep = True

    new_store = True
    store_prep_enabled = Params.get(module, 'store_prep_enabled')

    def get_driver(self):
        logging.info("Launching WinAppDriver.exe on DUT.")
        self._call([(self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"), (self.dut_resolved_ip + " " + self.app_port)], blocking=False)
        time.sleep(1)
        # desired_caps = {}
        # desired_caps["app"] = "Microsoft.WindowsStore_8wekyb3d8bbwe!App"
        # Launch to desktop instead of store app to handle the case when the store updates itself.
        desired_caps = {}
        desired_caps["app"] = "Root"
        driver = self._launchApp(desired_caps)
        return driver

    def navigate_to_store_downloads(self):
        self._call(["cmd.exe", "/C start shell:appsFolder\\Microsoft.WindowsStore_8wekyb3d8bbwe!App"], blocking=False)
        time.sleep(15)
        try:
            self.driver.find_element_by_name("Microsoft Store").find_element_by_name("Maximize Microsoft Store").click()
        except:
            pass

        # Determine if old store or new store app
        try:
            self.driver.find_element_by_accessibility_id("nav_downloadsandupdates").click()
            # logging.info("New store detected.")
        except:
            try:
                # self.driver.find_element_by_accessibility_id("MyLibraryButton").click()
                self.driver.find_element_by_accessibility_id("DownloadsAndUpdatesButton").click()
                # WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.NAME, 'See More'))).click()
                # WebDriverWait(self.driver, 2).until(EC.presence_of_element_located((By.XPATH, '//*[contains(@Name, "Downloads and updates")]'))).click()
                self.new_store = False
                # logging.info("Old store detected.")
            except:
                self.driver.find_element_by_accessibility_id("MyLibraryButton").click()
                self.new_store = False




    def runTest(self):
        if self.store_prep_enabled == "0":
            logging.info("Setting reg key to disable Auto Updates")
            self._call(['cmd.exe', r'/C reg.exe Add "HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\WindowsStore" /v AutoDownload /t REG_DWORD /d 2 /f'], expected_exit_code="")
            logging.info("Store_prep disabled, skipping.")
            self.createPrepStatusControlFile()
            return
        
        if Params.get('global', 'dut_ip') == "127.0.0.1":
            self._status_window(f"Updating Store apps and disabling auto updates.\nClosing UI for this.")
        else:
            self._status_window(f"Updating Store apps and disabling auto updates.")

        logging.info("Uninstalling Microsoft Whiteboard app if installed")
        self._call(["powershell.exe", "Get-AppxPackage *Microsoft.Whiteboard* | Remove-AppxPackage"], expected_exit_code="")

        start_time = time.time()
        self.driver = self.get_driver()
        self.navigate_to_store_downloads()

        last_round = False
        timeout = 60
        
        # Waiting until all the updates are installed
        # We click "Get updates" at each loop and wait for timeout time
        # We click "Resume all" for any app in paused state

        # Try for 15-30 minutes, then give up and PASS
        for i in range(15):
            # If the Store itself updates it will go to the Home page, and we will need to click the Downloads button again.
            try:
                # self.driver.find_element_by_name("Updates & downloads")
                self.driver.find_element_by_accessibility_id("nav_downloadsandupdates").click()
                self.new_store = True
            except:
                try:
                    # Find by Automation ID (accessibility_id) instead of name because sometimes name has additional words, like "Updates available".
                    # Moved to Downloads
                    self.driver.find_element_by_accessibility_id("DownloadsAndUpdatesButton").click()
                    self.new_store = True
                    # logging.info("New store detected.")
                except:
                    self.driver.find_element_by_accessibility_id("MyLibraryButton").click()
                    self.new_store = True

            # Handle a download error that prompts for Retry
            try:
                self.driver.find_element_by_name("Retry").click()
            except:
                pass

            try:
                # WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.NAME, 'Get updates'))).click()
                # logging.info(f"Type of self.driver: {type(self.driver)}")
                # WebDriverWait(self.driver, 10).until(self.element_clickable_by_names(names=["Get updates", "Check for updates"])).click()
                element = WebDriverWait(self.driver, 10).until(
                    lambda driver: self.element_clickable_by_names(driver, ["Get updates", "Check for updates"])
                )
                element.click()

                # if self.new_store:
                if True:
                    time.sleep(2)
                    WebDriverWait(self.driver, timeout, poll_frequency=3.0, ignored_exceptions=(ElementNotVisibleException)).until(
                        lambda driver: self.element_clickable_by_names(driver, ["Get updates", "Check for updates"])
                    )
                    try:
                        WebDriverWait(self.driver, 90).until(EC.presence_of_element_located((By.NAME, "Update all")))
                        self.driver.find_element_by_name('Update all').click()
                    except:
                        break
                    WebDriverWait(self.driver, timeout, poll_frequency=3.0, ignored_exceptions=(NoSuchElementException)).until_not(EC.presence_of_element_located((By.NAME, 'Update all')))
                # else:
                #     try:
                #         WebDriverWait(self.driver, 25).until(EC.element_to_be_clickable((By.XPATH, '//*[@Name="Update all" or @Name="Resume all" or @Name="Update"]'))).click()
                #         time.sleep(5)
                #     except TimeoutException:
                #         WebDriverWait(self.driver, timeout, poll_frequency=3.0, ignored_exceptions=(ElementNotVisibleException)).until(EC.element_to_be_clickable((By.NAME, 'Get updates')))
                #         pass
   
                #     WebDriverWait(self.driver, timeout, poll_frequency=3.0, ignored_exceptions=(ElementNotVisibleException)).until_not(EC.element_to_be_clickable((By.NAME, 'Pause all')))

                #     WebDriverWait(self.driver, 2).until(EC.presence_of_element_located((By.XPATH, '//*[@Name="All your trusted apps and games from Microsoft Store have the latest updates" or @Name="Your apps and games are up to date"]')))
                #     logging.info("All apps are installed")
                #     last_round = True

                # Commenting this out because after several loops it clicks update way too quickly
                # timeout = timeout // 2

            except NoSuchWindowException:
                logging.info("New window opened")
                time.sleep(5)
                self.navigate_to_store_downloads()
                pass
            except TimeoutException:
                logging.debug("Time out exception")
                if last_round:
                    break
                # last_round = False
                pass
            
        # Need to add code to log if errors are observed during the store update
        
        # Navigate to store settings
        # if self.new_store:
        if True:
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.NAME, 'User profile'))).click()
            try:
                WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.NAME, 'Settings'))).click()
            except:
                WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.NAME, 'Store settings'))).click()
        # else:
        #     WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.NAME, 'See More'))).click()
        #     WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.NAME, 'Settings'))).click()
        time.sleep(2)

        # # Disable updates
        # # if self.new_store:
        # if True:
        #     try:
        #         ele = self.driver.find_element_by_class_name("ToggleSwitch").find_element_by_xpath('//*[contains(@Name, "App updates")]')
        #     except:
        #         ele = self.driver.find_element_by_class_name("ToggleSwitch").find_element_by_xpath('//*[contains(@Name, "Update apps automatically")]')
        #     if ele.is_selected():
        #         ele.click()
        #         time.sleep(1)
        # else:
        #     try:
        #         self.driver.find_element_by_name("Update apps automatically On").click()
        #         time.sleep(1)
        #     except:
        #         logging.info("Update apps automatically is off")
        #         pass

        #     try:
        #         self.driver.find_element_by_name("Update apps automatically when I'm on Wi-Fi On").click()
        #         time.sleep(1)
        #     except:
        #         logging.info("Update apps automatically when I'm on Wi-Fi is off")
        #         pass

        logging.info("Setting reg key to disable Auto Updates")
        self._call(['cmd.exe', r'/C reg.exe Add "HKEY_LOCAL_MACHINE\SOFTWARE\Policies\Microsoft\WindowsStore" /v AutoDownload /t REG_DWORD /d 2 /f'], expected_exit_code="")

        # Close store driver
        self.driver.close()
        logging.info("Installing apps took: {0:.1f}s".format(time.time() - start_time))
        self.createPrepStatusControlFile()

    def element_clickable_by_names(self, driver, names):
        # Check for check updates or check for updates
        for name in names:
            try:
                element = driver.find_element(By.NAME, name)
                # Check if element is displayed and enabled (clickable)
                if element.is_displayed() and element.is_enabled():
                    return element
            except NoSuchElementException:
                continue
        return False  # When neither element is found/clickable
    
    def tearDown(self):    
        logging.info("Performing teardown.")
        core.app_scenario.Scenario.tearDown(self)
        time.sleep(2)
        self._kill("WinAppDriver.exe")
        self._kill("WinStore.App.exe")

    def kill(self):
        try:
            self._kill("WinAppDriver.exe")
            self._kill("WinStore.App.exe")
        except:
            pass

