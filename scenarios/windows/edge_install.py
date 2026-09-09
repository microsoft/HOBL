# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Download and install the new Microsoft Edge
##

import logging
import core.app_scenario
from core.parameters import Params
import os
import time
from appium import webdriver
import selenium.common.exceptions as exceptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.touch_actions import TouchActions
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


class EdgeInstall(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]
    Params.setDefault(module, 'install', '1')

    is_prep = True

    def runTest(self):
        self.browser = Params.get("global", 'browser')
        self.install = Params.get(self.module, 'install')

        # If the environment variable:EDGE_FEATURE_OVERRIDES_SOURCE is set to server_default (value is case-insensitive), then official builds will get only 100% allocated configurations from the server.
        self._call(['cmd.exe', '/C setx /m EDGE_FEATURE_OVERRIDES_SOURCE server_default'])
        
        logging.debug("browser = " + self.browser)
        installer_path = os.path.join(self.dut_exec_path, "MicrosoftEdgeSetup.exe")
        edge_version = 'Stable'

        if self.browser.lower() in ["edgedev", "edgebeta", "edgecanary"]:
            edge_version = self.browser[4].upper() + self.browser[5:]
            # installer_path = os.path.join(self.dut_exec_path, "MicrosoftEdgeSetup" + edge_version +".exe")

        if self.install == "1":
            if Params.get('global', 'dut_ip') == "127.0.0.1":
                self._status_window(f"Downloading latest {self.browser} browser.\nClosing UI for this.")
            else:
                self._status_window(f"Downloading latest {self.browser} browser.")
            logging.info("Downloading the new Microsoft Edge " + edge_version + " installer to host")
            # self._call(["powershell.exe", "wget \\\"https://go.microsoft.com/fwlink/?linkid=2108834&Channel=" + edge_version + "&language=en\\\" -outfile " + installer_path])
            self._call(["powershell.exe", "wget \\\"https://go.microsoft.com/fwlink/?linkid=2109047&Channel=" + edge_version + "&language=en\\\" -outfile " + installer_path])

            if Params.get('global', 'dut_ip') == "127.0.0.1":
                self._status_window(f"Installing latest {self.browser} browser.\nClosing UI for this.")
            else:
                self._status_window(f"Installing latest {self.browser} browser.")
            logging.info("Running the installer")
            self._call([installer_path,"/silent /install"], expected_exit_code="")
                
            time.sleep(20)

        self._status_window(f"Adjusting Edge settings for automation.")
        # Install administrative templates to be able to control settings
        self._upload("utilities\\open_source\\MicrosoftEdgePolicyTemplates\\windows\\admx\\msedge.admx", "c:\\Windows\\PolicyDefinitions")
        self._upload("utilities\\open_source\\MicrosoftEdgePolicyTemplates\\windows\\admx\\msedgeupdate.admx", "c:\\Windows\\PolicyDefinitions")
        self._upload("utilities\\open_source\\MicrosoftEdgePolicyTemplates\\windows\\admx\\msedgewebview2.admx", "c:\\Windows\\PolicyDefinitions")
        self._upload("utilities\\open_source\\MicrosoftEdgePolicyTemplates\\windows\\admx\\en-US\\msedge.adml", "c:\\Windows\\PolicyDefinitions\\en-US")
        self._upload("utilities\\open_source\\MicrosoftEdgePolicyTemplates\\windows\\admx\\en-US\\msedgeupdate.adml", "c:\\Windows\\PolicyDefinitions\\en-US")
        self._upload("utilities\\open_source\\MicrosoftEdgePolicyTemplates\\windows\\admx\\en-US\\msedgewebview2.adml", "c:\\Windows\\PolicyDefinitions\\en-US")
        # Change Edge policies
        self._call(["powershell.exe", 'Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Edge -ValueName AutoplayAllowed -Data 1 -Type DWord'])
        self._call(["powershell.exe", 'Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Edge -ValueName ShowRecommendationsEnabled -Data 0 -Type DWord'])
        self._call(["powershell.exe", 'Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Edge -ValueName HideFirstRunExperience -Data 1 -Type DWord'])
        self._call(["powershell.exe", 'Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Edge -ValueName HideRestoreDialogEnabled -Data 1 -Type DWord'])
        self._call(["powershell.exe", 'Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Edge -ValueName EdgeWorkspacesEnabled -Data 0 -Type DWord'])
        self._call(["powershell.exe", 'Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Edge -ValueName DefaultGeolocationSetting -Data 2 -Type DWord'])
        self._call(["powershell.exe", 'Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\EdgeUpdate -ValueName AutoUpdateCheckPeriodMinutes -Data 0 -Type DWord'])
        # This one prevents even manual updates, so commenting out
        # self._call(["powershell.exe", 'Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\EdgeUpdate -ValueName InstallDefault -Data 0 -Type DWord'])
        self._call(["powershell.exe", 'Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\EdgeUpdate -ValueName UpdateDefault -Data 0 -Type DWord'])
        result = self._call(["powershell.exe", 'Get-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -All'])
        self._call(["cmd.exe", '/C gpupdate /wait:1200'])

        # set same keys in registry for currnet user to support Windows Home
        self._call(["powershell.exe", 'New-Item -Path "HKCU:\\Software\\Policies\\Microsoft" -Name "Edge" -Force'])
        self._call(["powershell.exe", 'New-Item -Path "HKCU:\\Software\\Policies\\Microsoft" -Name "EdgeUpdate" -Force'])
        self._call(["powershell.exe", 'Set-ItemProperty -Path "HKCU:\\Software\\Policies\\Microsoft\\Edge" -Name AutoplayAllowed -Value 1 -Type DWord'])
        self._call(["powershell.exe", 'Set-ItemProperty -Path "HKCU:\\Software\\Policies\\Microsoft\\Edge" -Name ShowRecommendationsEnabled -Value 0 -Type DWord'])
        self._call(["powershell.exe", 'Set-ItemProperty -Path "HKCU:\\Software\\Policies\\Microsoft\\Edge" -Name HideFirstRunExperience -Value 1 -Type DWord'])
        self._call(["powershell.exe", 'Set-ItemProperty -Path "HKCU:\\Software\\Policies\\Microsoft\\Edge" -Name HideRestoreDialogEnabled -Value 1 -Type DWord'])
        self._call(["powershell.exe", 'Set-ItemProperty -Path "HKCU:\\Software\\Policies\\Microsoft\\Edge" -Name EdgeWorkspacesEnabled -Value 0 -Type DWord'])
        self._call(["powershell.exe", 'Set-ItemProperty -Path "HKCU:\\Software\\Policies\\Microsoft\\Edge" -Name DefaultGeolocationSetting -Value 2 -Type DWord'])
        self._call(["powershell.exe", 'Set-ItemProperty -Path "HKCU:\\Software\\Policies\\Microsoft\\EdgeUpdate" -Name AutoUpdateCheckPeriodMinutes -Value 0 -Type DWord'])
        self._call(["powershell.exe", 'Set-ItemProperty -Path "HKCU:\\Software\\Policies\\Microsoft\\EdgeUpdate" -Name UpdateDefault -Value 0 -Type DWord'])

        # Set reg key to not disable popups and disable offer to save passwrods popup
        logging.info('Setting reg keys.')
        regkey_path = 'HKCU\\SOFTWARE\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Storage\\microsoft.microsoftedge'
        if edge_version.lower() in ["canary", "dev", "stable", "beta"]:
            regkey_path = regkey_path + '.' + edge_version.lower()
        regkey_path = regkey_path + '_8wekyb3d8bbwe\\MicrosoftEdge\\'
        
        self._call(["cmd.exe", '/C reg add "' + regkey_path + 'New Windows" /v PopupMgr /t REG_SZ /d no /f'])
        self._call(["cmd.exe", '/C reg add "' + regkey_path + 'Main" /v "FormSuggest passwords" /t REG_SZ /d no /f'])
        
        # Set reg key to prevent full screen notification
        self._call(["cmd.exe", '/C reg add "' + regkey_path + 'FullScreen\\AllowDomains" /v netflix.com /t REG_DWORD /d 1 /f'])   
        self._call(["cmd.exe", '/C reg add "' + regkey_path + 'FullScreen\\AllowDomains" /v youtube.com /t REG_DWORD /d 1 /f'])   
        
        # Set reg key to turn off opening apps for certain sites, such as Facebook
        self._call(["cmd.exe", '/C reg add "' + regkey_path + 'AppLinks" /v Enabled /d 0 /f '])

        # Work around to prevent extensions popup when upgrading from RS3 to RS4
        # self._call(["cmd.exe", '/C reg delete "HKEY_CURRENT_USER\\Software\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Storage\\microsoft.microsoftedge_8wekyb3d8bbwe\\EdgeExtensions" /f'], expected_exit_code="")
        # self._call(["cmd.exe", '/C reg delete "HKEY_CURRENT_USER\\Software\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Storage\\microsoft.microsoftedge_8wekyb3d8bbwe\\EdgeExtensions_WebDriver" /f'], expected_exit_code="")

        # Disable auto updating of Chrome and Edge with Chromium
        self._call(["cmd.exe", '/C reg add "HKLM\\Software\\Policies\\Microsoft\\EdgeUpdateDev" /v AutoUpdateCheckPeriodMinutes /d 0 /f'])
        self._call(["cmd.exe", '/C reg add "HKLM\\Software\\WOW6432Node\\Microsoft\\EdgeUpdateDev" /v AutoUpdateCheckPeriodMinutes /t REG_DWORD /d 0 /f'])
        self._call(["cmd.exe", '/C reg add "HKLM\\Software\\WOW6432Node\\Microsoft\\EdgeUpdateDev" /v IsEnrolledToDomain /t REG_DWORD /d 1 /f'])

        # If the environment variable:EDGE_FEATURE_OVERRIDES_SOURCE is set to server_default (value is case-insensitive), then official builds will get only 100% allocated configurations from the server.
        self._call(["cmd.exe", '/C setx /m EDGE_FEATURE_OVERRIDES_SOURCE server_default'])


        # Launch Edge to clear first run stuff
        self._call([(self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"), (self.dut_resolved_ip + " " + self.app_port + " /forcequit")], blocking=False)
        time.sleep(1)
        # Connect to desktop to be able to launch apps with Start menu
        desired_caps = {}
        desired_caps["app"] = "Root"
        self.desktop = self._launchApp(desired_caps)
        self.desktop.implicitly_wait(0)

        logging.info("Launching Microsoft Edge " + edge_version)
        if edge_version.lower() == "canary":
            userprofile = self._call(["cmd.exe", "/C echo %USERPROFILE%"])
            exe_path = os.path.join(userprofile, "AppData", "Local", "Microsoft", "Edge SxS", "Application", "msedge.exe")
        elif edge_version.lower() in ["beta", "dev"]:
            exe_path = "c:\\Program Files (x86)\\Microsoft\\Edge " + edge_version + "\\Application\\msedge.exe"
        else:
            exe_path = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
        self._call(["powershell.exe", "& '"+ exe_path + "'"], blocking="False")
        time.sleep(15)

        # Pin Edge icon to taskbar
        # if edge_version.lower() in ["canary", "dev", "beta"]:
        error = "Can't find Edge icon"
        icon_version = edge_version + " "
        if edge_version.lower() == "stable":
            icon_version = ""
        try:
            app_elem = self._get_app_tray(self.desktop).find_element_by_name("Microsoft Edge " + icon_version + "- 1 running window")
            # app_elem = self._get_app_tray(self.desktop).find_element_by_xpath('//Button[contains(@Name, "Edge ' + edge_version + '")]')
            error = "Can't context click Microsoft Edge icon"
            ActionChains(self.desktop).context_click(app_elem).perform()
            time.sleep(1)
            error = "Can't find Pin to taskbar"
            pinbutton = self.desktop.find_element_by_name("Pin to taskbar")
            error = "Can't click Pin to taskbar"
            pinbutton.click()
            logging.info("Microsoft Edge now pinned.")
        except:
            logging.info(error)

        elem = None
        total_wait = 60
        interval = 5
        start = time.time()
        while time.time() - start < total_wait:
            try:
                try:
                    popup_btn = self.desktop.find_element_by_name('Got it')
                    try:
                        popup_btn.click()
                    except Exception:
                        ActionChains(self.desktop).move_to_element(popup_btn).click().perform()
                except Exception:
                    pass

                elem = WebDriverWait(self.desktop, interval).until(EC.presence_of_element_located((By.XPATH,'//Window[@ClassName="Chrome_WidgetWin_1"]')))
                break
            except Exception:
                pass

        if elem is None:
            e = Exception("Edge window not found within initial wait")
            try:
                self._call(["powershell.exe", "Get-Process | Where-Object { $_.ProcessName -like '*edge*' } | ForEach-Object { $_.Kill() }"], expected_exit_code="")
            except Exception:
                pass
            try:
                self._kill("msedge.exe")
            except Exception:
                pass
            try:
                self._call(["powershell.exe", "& '" + exe_path + "'"], blocking="False")
            except Exception:
                try:
                    self._call(["powershell.exe", "start msedge"], blocking="False")
                except Exception:
                    pass
            time.sleep(10)
            try:
                popup_btn = self.desktop.find_element_by_name('Got it')
                try:
                    popup_btn.click()
                except Exception:
                    ActionChains(self.desktop).move_to_element(popup_btn).click().perform()
            except Exception:
                pass

            try:
                elem = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[@ClassName="Chrome_WidgetWin_1"]')))
            except Exception as e2:
                raise

        self.browser_driver = self.getDriverFromWin(elem)
        self.browser_driver.implicitly_wait(0)
        try:
            self.browser_driver.find_element_by_name('Sync Confirmation Dialog').find_element_by_name('No, thanks').click()
        except:
            pass
        try:
            self.browser_driver.find_element_by_xpath('//*[contains(@Name, "Start without your data")]').click()
            time.sleep(5)
        except:
            pass
        try:
            self.browser_driver.find_element_by_xpath('//*[contains(@Name, "Confirm")]').click()
            time.sleep(5)
        except:
            pass
        try:
            maximize_elem = self.browser_driver.find_element_by_xpath('//Pane/Button[@Name="Maximize"]')
            if (maximize_elem.size["height"] != 0):
                ActionChains(self.browser_driver).move_to_element_with_offset(maximize_elem, 30, 30).click().perform()
                time.sleep(3)
        except:
            try:
                self.browser_driver.maximize_window()
            except:
                pass

        logging.info("Closing Edge " + edge_version)
        self._kill("msedge.exe")
        time.sleep(2)

        # Clear crash state to prevent restore popup
        self.clearEdgeCrashState()

        logging.info("Opening Edge a second time to clear first run page")
        self._call(["powershell.exe", 'start msedge'], blocking=False)
        time.sleep(15)
        logging.info("Closing Edge")
        self._kill("msedge.exe")
        time.sleep(2)

        # Clear crash state to prevent restore popup
        self.clearEdgeCrashState()
        
        self.createPrepStatusControlFile()

    def kill(self):
        logging.info("Killing open applications")
        try:
            logging.debug("Killing MicrosoftEdgeSetup.exe")
            self._kill("MicrosoftEdgeSetup.exe")
        except:
            pass
        
        # Clear crash state to prevent restore popup
        self.clearEdgeCrashState()


    def clearEdgeCrashState(self):
        local_path = "Edge"
        if len(self.browser) > 4 and self.browser[4:].lower() in ["dev", "beta"]:
            local_path = local_path + " " + self.browser[4].upper() + self.browser[5:].lower()
        elif self.browser.lower() == "edgecanary":
            local_path = local_path + " SxS"

        preferences_file = os.path.join("$env:userprofile", "AppData", "local", "Microsoft", local_path, "User Data", "Default", "Preferences")

        if Params.get("global", "local_execution") == "1":
            self._call(["powershell.exe", '\"((Get-Content -path \'' + preferences_file + '\' -Raw) -replace \'Crashed\', \'Normal\') | Set-Content -path \'' + preferences_file + '\'\"'], expected_exit_code="")
        else:
            self._call(["powershell.exe", '((Get-Content -path """' + preferences_file + '""" -Raw) -replace """Crashed""","""Normal""") | Set-Content -Path """' + preferences_file + '"""'], expected_exit_code="")