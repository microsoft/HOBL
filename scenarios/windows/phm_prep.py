# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import core.app_scenario
from core.parameters import Params
import os
import sys
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


class PhmPrep(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]
    # Override collection of config data, traces, and execution of callbacks 
    # Params.setOverride("global", "collection_enabled", "0")

    # Set default parameters
    Params.setDefault(module, 'host_path', "C:\\phm")
    Params.setDefault(module, 'phm_installer', "phm_nda_V4.22.6_B26.08.28.01_H.exe")
    Params.setDefault(module, 'phm', "PowerhouseMountain.exe")
    Params.setDefault(module, 'phm_base_path', 'C:\\Program Files\\PowerhouseMountain')

    # Get parameters
    host_path = Params.get(module, 'host_path')
    phm_installer = Params.get(module, 'phm_installer')
    phm = Params.get(module, 'phm')
    phm_base_path = Params.get(module, 'phm_base_path')

    is_prep = True

    def runTest(self):
        trace_path = self.phm_base_path + "\\traces"
        phm_dut_path = self.dut_exec_path + '\\' + self.phm_installer
        if os.path.exists(trace_path):
            if os.path.exists(phm_dut_path):
                logging.info("The PHM version you requested is already installed.")
                return
        else:
            
            # Delete PHM installer on DUT
            if os.path.exists(phm_dut_path):
                self._call(["cmd.exe", "/C erase" + self.dut_exec_path + "\\" + self.phm_installer])
            else:
                pass

            # Upload PHM installer to DUT
            phm_path = self.host_path + '\\' + self.phm_installer
            if os.path.exists(phm_path):
                logging.info("Uploading PHM installer -- " + self.dut_exec_path)
                try:
                    self._upload(phm_path, self.dut_exec_path)
                    logging.info("PHM installer sucessfully uploaded -- " + self.dut_exec_path)
                except Exception as e:
                    logging.error("Unable to upload PHM Installer.")
                    raise e
            else:
                logging.error("PHM installer has not been located at the source.")
                self.fail("PHM installer has not been located at the source.")

            time.sleep(5)

            logging.info("Launching WinAppDriver.exe on DUT.")
            self._call([(self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"), (self.dut_resolved_ip + " " + self.app_port + " /forcequit")], blocking=False)
            time.sleep(1)
            desired_caps = {}
            desired_caps["app"] = "Root"
            self.desktop = self._launchApp(desired_caps)
            self.desktop.implicitly_wait(0)

            # Install PHM on DUT
            logging.info("PHM is being installed on the DUT.")
            # self._call(["cmd.exe", "/C" + " " + self.dut_exec_path + "\\" + self.phm_installer + " /SILENT"], blocking=False)
            self._call(["cmd.exe", "/C" + " " + self.dut_exec_path + "\\" + self.phm_installer + " /SILENT"], blocking=True)
            # for x in range(2):
            #     WebDriverWait(self.desktop, 300).until(EC.presence_of_element_located((By.XPATH,"//*[contains(@Name, 'Node.js Setup') or contains(@Name, 'PowerMax -')]")))
            #     # Node js installer
            #     try:
            #         self.desktop.find_element_by_xpath('//*[contains(@Name, "Node.js")]')
            #         WebDriverWait(self.desktop, 30).until(EC.element_to_be_clickable((By.NAME, "Next"))).click()
            #         WebDriverWait(self.desktop, 30).until(EC.element_to_be_clickable((By.NAME, "I accept the terms in the License Agreement"))).click()
            #         for y in range(4):
            #             WebDriverWait(self.desktop, 30).until(EC.element_to_be_clickable((By.NAME, "Next"))).click()
            #         WebDriverWait(self.desktop, 30).until(EC.element_to_be_clickable((By.NAME, "Install"))).click()
            #         WebDriverWait(self.desktop, 60).until(EC.element_to_be_clickable((By.NAME, 'Finish'))).click()
            #     except:
            #         self._page_source(self.desktop)
            #         pass
            #     # PowerMax installer
            #     try:
            #         self.desktop.find_element_by_xpath('//*[contains(@Name, "PowerMax -")]')
            #         try:
            #             WebDriverWait(self.desktop, 5).until(EC.element_to_be_clickable((By.NAME, 'Finish'))).click()
            #         except:
            #             for y in range(3):
            #                 WebDriverWait(self.desktop, 30).until(EC.element_to_be_clickable((By.NAME, "Next >"))).click()
            #         WebDriverWait(self.desktop, 60).until(EC.element_to_be_clickable((By.XPATH,"//Button[@Name='Close' and @ClassName='Button']"))).click()
            #         break
            #     except:
            #         self._page_source(self.desktop)
            #         pass
            time.sleep(10)
            logging.info("PHM installation complete.")
            
            # Create exception for Node.js in Windows Defender
            self._call(["cmd.exe", """/C netsh.exe advfirewall firewall add rule name="NodeJs TCP" program="C:\\Program Files\\nodejs\\node.exe" dir=in action=allow enable=yes localport=any protocol=TCP profile=public,private,domain"""])
            self._call(["cmd.exe", """/C netsh.exe advfirewall firewall add rule name="NodeJs UDP" program="C:\\Program Files\\nodejs\\node.exe" dir=in action=allow enable=yes localport=any protocol=UDP profile=public,private,domain"""])
            
            # Launching PowerhouseMountain app on the DUT then start/stop first trace
            logging.info("Starting PowerhouseMountain...")
            self._call(["cmd.exe", '/C cd "' + self.phm_base_path + '" & .\\' + self.phm], blocking=False)
            
            phm_win = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.CLASS_NAME,'Chrome_WidgetWin_1')))
            self.phm_driver = self.getDriverFromWin(phm_win)
            self.phm_driver.implicitly_wait(0)

            # Dismiss popup "Sync your profile"
            try:
                WebDriverWait(self.phm_driver, 10).until(EC.element_to_be_clickable((By.XPATH,"//Button[contains(@Name, 'No, thanks')]"))).click()
            except:
                pass

            # Dismiss popup "Signed in"
            try:
                WebDriverWait(self.phm_driver, 10).until(EC.element_to_be_clickable((By.XPATH,"//Button[contains(@Name, 'Got it')]"))).click()
            except:
                pass

            WebDriverWait(self.phm_driver, 60).until(EC.element_to_be_clickable((By.XPATH,"//Button[contains(@Name, 'Collector')]"))).click()
            logging.info("Starting PHM trace...")
            WebDriverWait(self.phm_driver, 30).until(EC.element_to_be_clickable((By.XPATH,"//Button[contains(@Name, 'Start')]"))).click()
            WebDriverWait(self.phm_driver, 300).until(EC.presence_of_element_located((By.XPATH,"//Text[contains(@Name, 'when complete press the Stop button')]")))
            logging.info("Stoping PHM trace...")
            WebDriverWait(self.phm_driver, 30).until(EC.element_to_be_clickable((By.XPATH,"//Button[contains(@Name, 'Stop')]"))).click()
            WebDriverWait(self.phm_driver, 300).until(EC.presence_of_element_located((By.XPATH,"//Text[contains(@Name, 'Scenario traces saved')]")))
            
            # System is now configured to capture power states, reboot to run trace. 
            logging.info("Rebooting DUT to finish PHM setup")
            self._call(["shutdown.exe", "/r /f /t 5"])
            time.sleep(15)
            self._wait_for_dut_comm()


    def tearDown(self):
        # Prevent teardown routine from running
        return 0


    def kill(self):
        # Prevent base kill routine from running
        return 0