# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Sign into msa
# 
# Setup instructions:
##

import os
import logging
import time
import core.app_scenario
from core.parameters import Params
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


class msaPrep(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]

    # Set default parameters
    Params.setDefault(module, 'local_admin_password', 'Toast')

    # Get parameters
    msa_account = Params.get('global', 'msa_account')
    dut_password = Params.get('global', 'dut_password')
    local_admin_password = Params.get(module, 'local_admin_password')
    local_execution = (Params.get('global', 'local_execution'))

    is_prep = True


    def runTest(self):
        # If MSA account is not specified, skip this prep
        if self.msa_account == "" or self.dut_password == "":
            logging.info("MSA account or password not specified, skipping msa_prep.")
            self.createPrepStatusControlFile()
            return
        
        # Delete entries created for Local Account
        self._call(["cmd.exe", '/C reg delete "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon" /v DefaultUserName /f > null 2>&1'], expected_exit_code="")
        self._call(["cmd.exe", '/C reg delete "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon" /v AutoAdminlogon /f > null 2>&1'], expected_exit_code="")

        logging.info("Launching WinAppDriver.exe on DUT.")
        self._call([(self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"), (self.dut_resolved_ip + " " + self.app_port)], blocking=False)
        desired_caps = {}
        desired_caps["app"] = "Root"
        self.driver = self._launchApp(desired_caps)
        time.sleep(1)
        self._call(["cmd.exe", '/C start ms-settings:'])
        time.sleep(3)
        # Maximize to make sure that "Accounts" will be visible
        try:
            self.driver.find_element_by_name("Maximize Settings").click()
            time.sleep(2)
        except:
            pass
        self.driver.find_element_by_name("Accounts").click()
        time.sleep(3)
        try:
            self.driver.find_element_by_name("Your info").click()
            time.sleep(2)
            self.driver.find_element_by_name("Sign in with a Microsoft account instead").click()
        except:
            # Set auto login MSA Account
            self._call(["cmd.exe", '/C reg add "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon" /v DefaultUserName /t REG_SZ /d ' + self.msa_account + ' /f > null 2>&1'])
            self._call(["cmd.exe", '/C reg add "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon" /v DefaultPassword /t REG_SZ /d ' + self.dut_password + ' /f > null 2>&1'])
            self._call(["cmd.exe", '/C reg add "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon" /v AutoAdminlogon /t REG_SZ /d 1 /f > null 2>&1'])

            # Turn off Surface notifications
            self._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings\\Microsoft.SurfaceHub_8wekyb3d8bbwe!App" /v Enabled /t REG_DWORD /d 0 /f > null 2>&1'])
            self.createPrepStatusControlFile()
            return
        time.sleep(3)
        email = WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.NAME, 'Enter your email, phone, or Skype.')))
        email.click()
        email.send_keys(self.msa_account)
        time.sleep(3)
        self.driver.find_element_by_name("Next").click()
        time.sleep(3)

        # Handle pop-ups: "Use your password instead" and "Use my password"
        try:
            for popup_name in ["Use your password instead", "Use my password"]:
                popups = self.driver.find_elements_by_name(popup_name)
                if popups:
                    popups[0].click()
                    time.sleep(2)
        except Exception as e:
            logging.info(f"No password pop-up found: {e}")

        password = self.driver.find_element_by_xpath('//*[contains(@Name,"' + "Enter the password" + '")]')
        password.click()
        password.send_keys(self.dut_password)
        time.sleep(3)
        self.driver.find_element_by_name("Sign in").click()
        time.sleep(20)
        self.driver.find_element_by_name("Next").click()
        time.sleep(20)
        # if self.local_admin_password != "":
        try:
            localpassword = self.driver.find_element_by_xpath('//*[contains(@Name,"' + "Current Windows password" + '")]')
            localpassword.click()
            localpassword.send_keys(self.local_admin_password)
            self.driver.find_element_by_name("Next").click()
            time.sleep(2)
        except:
            pass

        try:
            skip = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.NAME, 'Skip for now')))
            skip.click()
        except:
            logging.info("Skip for now not found.")
            pass
        time.sleep(1)

        # Verify account was set properly
        found_account = ""
        try:
            found_account = self._call(["powershell.exe", r"(get-childitem hkcu:\Software\Microsoft\IdentityCRL\UserExtendedProperties\ | select pschildname).pschildname"], expected_exit_code="", fail_on_exception=False)
        except:
            pass
        if self.msa_account.lower() != found_account.strip().lower():
            logging.error(f"MSA account verification failed. Expected: {self.msa_account}, Found: {found_account.strip()}")
            self.fail("MSA account verification failed.")

        # Set auto login MSA Account
        self._call(["cmd.exe", '/C reg add "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon" /v DefaultUserName /t REG_SZ /d ' + self.msa_account + ' /f > null 2>&1'])
        self._call(["cmd.exe", '/C reg add "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon" /v DefaultPassword /t REG_SZ /d ' + self.dut_password + ' /f > null 2>&1'])
        self._call(["cmd.exe", '/C reg add "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon" /v AutoAdminlogon /t REG_SZ /d 1 /f > null 2>&1'])

        # Turn off Surface notifications
        self._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings\\Microsoft.SurfaceHub_8wekyb3d8bbwe!App" /v Enabled /t REG_DWORD /d 0 /f > null 2>&1'])

        # Set user password to never expire
        if Params.get("global", "local_execution") == "0":
            userprofile = self._call(["powershell.exe", "$env:UserName"])
        else:
            userprofile = os.getlogin()
        self._call(["powershell.exe", 'Set-LocalUser -Name ' + userprofile + ' -PasswordNeverExpires 1'])
        
        self.createPrepStatusControlFile()

    def tearDown(self):
        core.app_scenario.Scenario.tearDown(self)
        self._kill("SystemSettings")
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