# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Download and install the New Teams App
##

import logging
import core.app_scenario
from core.parameters import Params
import os
import time
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


class TeamsInstall(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]

    # Params.setDefault(module, 'teams_version', '1.4.00.16575')
    # Params.setDefault(module, 'teams_version', '1.4.00.19572')
    # Params.setDefault(module, 'teams_version', '1.4.00.26376')
    # Params.setDefault(module, 'teams_version', '1.4.00.35564')
    # Params.setDefault(module, 'teams_version', '1.5.00.5967')
    # Params.setDefault(module, 'teams_version', '1.5.00.6271')
    # Params.setDefault(module, 'teams_version', '1.5.00.21668')
    # Params.setDefault(module, 'teams_version', '1.5.00.33362')
    # Params.setDefault(module, 'teams_version', '1.5.00.36367')
    # Params.setDefault(module, 'teams_version', '1.6.00.1381')
    # Params.setDefault(module, 'teams_version', '1.6.00.6754')
    # Params.setDefault(module, 'teams_version', '1.6.00.12455')
    # Params.setDefault(module, 'teams_version', '1.6.00.22378')
    Params.setDefault(module, 'teams_version', '1.6.00.27573')
    Params.setDefault(module, 'teams_msa_account', "")
    Params.setDefault(module, 'teams_msa_password', "")
    Params.setDefault(module, 'launch_after_install', "1")
    Params.setDefault(module, 'install_teams', "1")
    Params.setDefault(module, 'sign_in_teams', "1")
    Params.setDefault(module, 'set_teams_settings', "1")
    Params.setDefault(module, 'update_teams', "0")
    Params.setDefault(module, 'teams_theme', "Default")

    msa_account = Params.get('global', 'msa_account')
    teams_version = Params.get(module, 'teams_version')
    dut_architecture = Params.get('global', 'dut_architecture')
    # Added to enable the use of a different MSA when logging into teams instead of the account that is currently associated with the DUT.
    teams_msa_account = Params.get(module, 'teams_msa_account')
    teams_msa_password = Params.get(module, 'teams_msa_password')
    launch_after_install = Params.get(module, 'launch_after_install')
    install_teams = Params.get(module, 'install_teams')
    sign_in_teams = Params.get(module, 'sign_in_teams')
    set_teams_settings = Params.get(module, 'set_teams_settings')
    update_teams = Params.get(module, 'update_teams')
    teams_theme = Params.get(module, 'teams_theme')

    
    successful_install = False
    is_prep = True

    def runTest(self):
        # Checks to see if an MSA has been specified for use with Teams.  If not, test will default to using the MSA that the DUT is logged into
        self.msa_password = self.password

        # Upload Teams resources
        self.userprofile = self._call(["cmd.exe", "/C echo %USERPROFILE%"])
        source = os.path.join("scenarios", "windows", "teams", "ppt.mp4")
        dest = os.path.join(self.dut_exec_path, "teams_resources")
        dest_file = os.path.join(dest, "ppt.mp4")
        # Check if video file already exists on DUT
        if self._check_remote_file_exists(dest_file, False):
            logging.info("Movie file " + "ppt.mp4" + " already found on DUT.  Skipping upload")
        else:
            logging.info("Uploading movie file " + "ppt.mp4" + " to " + dest)
            self._upload(source, dest)

        # Get desktop driver
        logging.debug("Launching WinAppDriver.exe on DUT.")
        self._call([self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe", self.dut_resolved_ip + " " + self.app_port + " /forcequit"], blocking=False)
        logging.info("Creating Desktop Driver")
        desired_caps = {}
        desired_caps["app"] = "Root"
        desktop = self._launchApp(desired_caps, track_driver=False)
        desktop.implicitly_wait(10)

        # Run Install if install_teams is set to 1
        if self.install_teams == "1":
            # Kill any running Teams processes
            try:
                self._kill("ms-teams.exe Teams.exe")
            except:
                pass
            time.sleep(10)
            # Specify version to install
            self._call(["cmd.exe", " /c mkdir %APPDATA%\\Microsoft\\Teams\\"], expected_exit_code="")
            self._call(["cmd.exe", ' /c echo|set /P="' + self.teams_version + '"> %APPDATA%\\Microsoft\\Teams\\TargetAppVersion.txt'], expected_exit_code="")

            installer_path = os.path.join(self.dut_exec_path, "TeamsInstaller.msix")
            logging.info("Downloading the Teams installer to the DUT.")

            # Download the Teams installer
            if self.dut_architecture == "arm64":
                self._call(["powershell.exe", "wget \\\"https://go.microsoft.com/fwlink/?linkid=2196207&clcid=0x409&culture=en-us&country=us\\\" -outfile " + installer_path])
            else:
                self._call(["powershell.exe", "wget \\\"https://go.microsoft.com/fwlink/?linkid=2196106&clcid=0x409&culture=en-us&country=us\\\" -outfile " + installer_path])            

            # Run the installer silently
            logging.info("Running the installer")
            # self._call(["powershell.exe", 'Add-AppProvisionedPackage -Online -PackagePath "' + installer_path + '" -SkipLicense'])
            # self._call(["powershell.exe", 'Add-AppxPackage -Path "' + installer_path + '"'])
            install_response = self._call(
                ["powershell.exe", 'Add-AppxPackage -Path "' + installer_path + '"'],
                expected_exit_code="", fail_on_exception=False
            )
            # Check and ignore if newer version of teams is already installed on DUT. Dont let this be a failure reason. 
            if "0x80073d06" in install_response.lower():
                logging.info("A newer Teams version is already installed; continuing with the scenario.")
            elif str(Params.getCalculated('last_call_exit_code')) != "0":
                self.fail("Teams installation failed: " + install_response)
            logging.info("Wait for Teams Installer run")
            time.sleep(10)

            logging.info("Writting config to prevent Teams Update and reduce timeout time")
            self._call(["cmd.exe", " /c del %APPDATA%\\..\\Local\\Packages\\MSTeams_8wekyb3d8bbwe\\LocalCache\\Microsoft\\MSTeams\\configuration.json"], expected_exit_code="")
            time.sleep(1)
            self._call(["cmd.exe", " /c mkdir %APPDATA%\\..\\Local\\Packages\\MSTeams_8wekyb3d8bbwe\\LocalCache\\Microsoft\\MSTeams"], expected_exit_code="")
            time.sleep(1)
            # if self.dut_architecture == "arm64":
            #     self._call(["cmd.exe", " /c echo|set /P=" + '{ "arm64/buildLink": "", "arm64/latestVersion": "", "core/startPage": "https://teams.microsoft.com/v2/?config.core.appIdleTimeoutInMs=240000&config.core.appLongIdleTimeoutInMs=30000" }' + "> %APPDATA%\\..\\Local\\Packages\\MSTeams_8wekyb3d8bbwe\\LocalCache\\Microsoft\\MSTeams\\configuration.json"], expected_exit_code="")
            # else:
            #     self._call(["cmd.exe", " /c echo|set /P=" + '{ "x64/buildLink": "", "x64/latestVersion": "", "core/startPage": "https://teams.microsoft.com/v2/?config.core.appIdleTimeoutInMs=240000&config.core.appLongIdleTimeoutInMs=30000" }' + "> %APPDATA%\\..\\Local\\Packages\\MSTeams_8wekyb3d8bbwe\\LocalCache\\Microsoft\\MSTeams\\configuration.json"], expected_exit_code="")
            if self.dut_architecture == "arm64":
                self._call(["cmd.exe", " /c echo|set /P=" + '{ "arm64/buildLink": "", "arm64/latestVersion": "" }' + "> %APPDATA%\\..\\Local\\Packages\\MSTeams_8wekyb3d8bbwe\\LocalCache\\Microsoft\\MSTeams\\configuration.json"], expected_exit_code="")
            else:
                self._call(["cmd.exe", " /c echo|set /P=" + '{ "x64/buildLink": "", "x64/latestVersion": "" }' + "> %APPDATA%\\..\\Local\\Packages\\MSTeams_8wekyb3d8bbwe\\LocalCache\\Microsoft\\MSTeams\\configuration.json"], expected_exit_code="")
            time.sleep(1)

            # Add reg keys to allow access to location/mic/camera
            self._call(['cmd.exe', r'/C reg.exe Add "HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location\MSTeams_8wekyb3d8bbwe" /v Value /t REG_SZ /d Allow /f'], expected_exit_code="")
            self._call(['cmd.exe', r'/C reg.exe Add "HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone\MSTeams_8wekyb3d8bbwe" /v Value /t REG_SZ /d Allow /f'], expected_exit_code="")
            self._call(['cmd.exe', r'/C reg.exe Add "HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam\MSTeams_8wekyb3d8bbwe" /v Value /t REG_SZ /d Allow /f'], expected_exit_code="")

        # Try to finish setup for built in teams.
        else:
            # First confirm the MSTeams Appx package is actually installed before
            # checking the taskbar / search bar. Without this check, typing
            # "Microsoft Teams" into search on a device where Teams isn't installed
            # could launch Edge search.
            teams_pkg = self._call(
                ["powershell.exe", "(Get-AppxPackage -Name MSTeams).PackageFullName"],
                expected_exit_code=""
            ).strip()

            if not teams_pkg:
                logging.info("MSTeams Appx package not installed on DUT, skipping built-in Teams launch.")
            else:
                logging.info(f"Found MSTeams Appx package: {teams_pkg}")
                try:
                    self.active_driver = desktop
                    apps_elem = self._get_app_tray(desktop)

                    id = "MSTeams"
                    # Match any element whose AutomationId contains "MSTeams" so we
                    # don't have to track the exact (and long/changing) full id.
                    app_button = apps_elem.find_element_by_xpath(f"//*[contains(@AutomationId, '{id}')]")
                    app_button.click()
                    logging.info("Waiting for 'Finish setup' button...")
                    finish_setup_btn = WebDriverWait(desktop, 60).until(EC.presence_of_element_located((By.XPATH, "//Button[contains(@Name, 'Finish setup')]")))
                    finish_setup_btn.click()
                    logging.info("Clicked 'Finish setup'.")
                    time.sleep(420)
                    ActionChains(desktop).send_keys(Keys.ENTER).perform() # Incase canera permissions pop up need to dismiss it.
                except:
                    logging.info("Teams not found in taskbar, trying to launch via start menu search.")
                    try:
                        # Press Windows key, type "Microsoft Teams", and hit Enter to launch.
                        # Safe to do here because we've already confirmed the package is installed,
                        # so search will surface the app rather than a Bing/Store web suggestion.
                        ActionChains(desktop).key_down(Keys.META).key_up(Keys.META).perform()
                        time.sleep(2)
                        ActionChains(desktop).send_keys("Microsoft Teams").perform()
                        time.sleep(2)
                        ActionChains(desktop).send_keys(Keys.ENTER).perform()
                        logging.info("Waiting for 'Finish setup' button...")
                        finish_setup_btn = WebDriverWait(desktop, 60).until(EC.presence_of_element_located((By.XPATH, "//Button[contains(@Name, 'Finish setup')]")))
                        finish_setup_btn.click()
                        logging.info("Clicked 'Finish setup'.")
                        time.sleep(420)
                        ActionChains(desktop).send_keys(Keys.ENTER).perform() # Incase canera permissions pop up need to dismiss it.
                    except:
                        try:
                            logging.debug("Killing msedge in case it was launched because teams isn't installed.")
                            self._kill("msedge.exe")
                        except:
                            pass
                        logging.info("Failed to see 'Finish setup' button after launching Teams. Built in teams is already set up or needs to be installed. Will try to proceed with setup.")

        # Launch Settings to microphone/camera/location set permissions to teams true
        logging.info("Setting Permissions for Teams")
        for x in ['microphone', 'location', 'webcam']:
            logging.info("Launching Settings for " + x)
            self._call(["cmd.exe", f'/C start ms-settings:privacy-{x}'])
            win = WebDriverWait(desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Settings")]')))
            settings_driver = self.getDriverFromWin(win)
            settings_driver.maximize_window()
            time.sleep(2)
            microsoft_teams = settings_driver.find_element_by_xpath('//Button[contains(@Name, "Microsoft Teams")]')
            if not microsoft_teams.is_selected():
                microsoft_teams.click()
            time.sleep(3)
        settings_driver.close()


        # Launch Teams
        if self.launch_after_install == "1":
            # Kill any running Teams processes
            try:
                self._kill("ms-teams.exe Teams.exe")
            except:
                pass
            time.sleep(10)
            logging.info("Launching Teams")
            self._call(["powershell.exe", "start ms-teams"], blocking=False)
            time.sleep(45)

        # # Get desktop driver
        # logging.debug("Launching WinAppDriver.exe on DUT.")
        # self._call([self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe", self.dut_resolved_ip + " " + self.app_port + " /forcequit"], blocking=False)
        # logging.info("Creating Desktop Driver")
        # desired_caps = {}
        # desired_caps["app"] = "Root"
        # desktop = self._launchApp(desired_caps, track_driver=False)
        # desktop.implicitly_wait(10)

        # # Launch Settings to microphone/camera/location set permissions to teams true
        # self._call(["cmd.exe", '/C start ms-settings:privacy-microphone'])
        # microsoft_teams = self.driver.find_element_by_xpath('//Button[contains(@Name, "Save snapshots")]')
        # if not microsoft_teams.is_selected():
        #     microsoft_teams.click()

        # Get Teams window driver
        logging.info("Creating Teams Driver")
        win = WebDriverWait(desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Microsoft Teams")]')))
        teams_driver = self.getDriverFromWin(win)
        logging.info("Found Teams window")
        time.sleep(5)

        # Sign in and activate Teams
        if self.sign_in_teams == "1":
            logging.info("Trying to sign in to Teams")

            # Reduce Teams Idle entry time
            logging.info("Lowering idle timout times")
            # self._call(["cmd.exe", " /c mkdir %APPDATA%\\..\\Local\\Packages\\MSTeams_8wekyb3d8bbwe\\LocalCache\\Microsoft\\MSTeams"], expected_exit_code="")
            self._call(["cmd.exe", " /c mkdir %APPDATA%\\..\\Local\\Packages\\MicrosoftTeams_8wekyb3d8bbwe\\LocalCache\\Microsoft\\MSTeams"], expected_exit_code="")

            # self._call(["cmd.exe", " /c echo|set /P=" + '{ "core/startPage": "https://teams.microsoft.com/v2/?config.core.appIdleTimeoutInMs=240000&config.core.appLongIdleTimeoutInMs=30000" }' + "> %APPDATA%\\..\\Local\\Packages\\MSTeams_8wekyb3d8bbwe\\LocalCache\\Microsoft\\MSTeams\\configuration.json"], expected_exit_code="")
            self._call(["cmd.exe", " /c echo|set /P=" + '{ "core/startPage": "https://teams.microsoft.com/v2/?config.core.appIdleTimeoutInMs=240000&config.core.appLongIdleTimeoutInMs=30000" }' + "> %APPDATA%\\..\\Local\\Packages\\MicrosoftTeams_8wekyb3d8bbwe\\LocalCache\\Microsoft\\MSTeams\\configuration.json"], expected_exit_code="")
            time.sleep(5)
            
            # Determine what account to use for Teams
            if self.teams_msa_account != "":
                logging.debug("There is a Teams MSA account specified in the profile, using that.")
                self.msa_account = self.teams_msa_account
                if self.teams_msa_password != "":
                    self.msa_password = self.teams_msa_password
                    logging.debug("Teams MSA password found.  msa_apassword set to: " + self.msa_password)
                else:
                    self.fail("An MSA account was specified for Teams, but no password was provided.  Please note that when using the teams_msa_account parameter a valid password must be specified with the teams_msa_password paramter.")

            # Check for primary use for teams & best role describes you popup
            try:
                logging.info("Checking for which best role describes you popup")
                teams_driver.find_element_by_name("None of these").click()
                time.sleep(3)
                self._page_source(teams_driver, "Best_Role_Check")
                teams_driver.find_element_by_class_name("fui-Button r1f29ykk").click()
                time.sleep(1)
                ActionChains(desktop).send_keys(Keys.ENTER).perform()
            except:
                logging.info("Best role popup not found")

            # Check for Skype profile popup
            try:
                logging.info("Checking for Skype profile popup")
                teams_driver.find_element_by_xpath("//*[contains(@Name, 'Continue')]").click()
                time.sleep(2)
                teams_driver.find_element_by_xpath("//*[contains(@Name, 'Current profile')]").click()
                time.sleep(2)
                # Some dialogs show a Confirm button after selecting the current profile
                teams_driver.find_element_by_xpath("//*[contains(@Name, 'Confirm')]").click()
            except:
                logging.info("Skype profile popup not found")
            time.sleep(15)

            # Check for "Stay in Touch" popup
            try:
                logging.info("Checking for Stay in Touch popup")
                # self._page_source(teams_driver, "Stay_In_Touch_Check")
                teams_driver.find_element_by_xpath("//*[contains(@Name, 'Stay in touch wherever you are')]").find_element_by_name("Close").click()
                logging.info("Closed Stay in Touch popup")
                time.sleep(2)
            except:
                logging.info("Stay in Touch popup not found")

            # Check if already logged in
            # Log out if already logged in
            try:
                # Close pop up for "help others connect with you" if there
                ActionChains(desktop).send_keys(Keys.ESCAPE).perform()
                time.sleep(2)
                teams_driver.find_element_by_xpath("//*[contains(@Name, 'Your profile') or contains(@Name, 'get you started') or contains(@Name, 'Account Manager for')]").click()
                logging.info("Found profile, logging out.")
                time.sleep(2)
                teams_driver.find_element_by_xpath("//*[contains(@Name, 'Sign out')]").click()
                time.sleep(2)
                teams_driver.find_element_by_xpath("//Button[contains(@Name, 'Sign out')]").click()
                time.sleep(30)

                # # Seems to open multiple Teams windows on logout, close them all
                # # Relaible way to close extra windows is to kill teams process, twice
                # logging.info("Killing Teams process")
                # self._kill("ms-teams.exe Teams.exe")
                # time.sleep(10)
                # self._kill("ms-teams.exe Teams.exe")
                # time.sleep(15)

                # # Relaunch Teams
                # logging.info("Relaunching Teams")
                # self._call(["powershell.exe", "start ms-teams"], blocking=False)
                # time.sleep(15)

                ## not needed anymore as the next time it checks for using another account handles signing in. 
                # try:
                #     logging.info("Checking for Use another account or sign up")
                #     desktop.find_element_by_xpath("//*[contains(@Name, 'another account')]").click()
                #     logging.info("Clicked Use another account or sign up.")
                #     time.sleep(5)

                #     try:
                #         # Look for Use another account or sign up a seconed time since sometimes in other window
                #         logging.info("Checking for Use another account or sign up")
                #         desktop.find_element_by_xpath("//*[contains(@Name, 'another account')]").click()
                #         logging.info("Clicked Use another account or sign up.")
                #         time.sleep(5)
                #     except:
                #         logging.info("Did not see 'Use another account or sign up a second time.'")

                # except:
                #     logging.info("Did not see 'Use another account or sign up the first time.'")

                # Get a new Teams window driver
                logging.info("Creating Teams Driver")
                win = WebDriverWait(desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Microsoft Teams")]')))
                teams_driver = self.getDriverFromWin(win)
                logging.info("Found Teams window")
                time.sleep(5)
            except:
                logging.info("Not already logged in.")

            # Check for sign in button this is for 1st time login. Screen with just sign in or join a meeting button
            try:
                logging.info("Checking for sign in/join a meeting button screen.")
                # find sign in button by button element
                sign_in_button = desktop.find_element_by_xpath("//Button[contains(@Name, 'Sign in')]")
                logging.info("Sign in button found")
                time.sleep(1)
                sign_in_button.click()
                time.sleep(1)
            except:
                logging.info("Did not find 1st time sign in button")

            # tries to resolve "pick an account"
            try:
                logging.info("Checking for Use another account or sign up")
                teams_driver.find_element_by_xpath("//*[contains(@Name, 'another account')]").click()
                logging.info("Clicked Use another account or sign up.")
                #Attempts to enter credentials
                time.sleep(20)
                ActionChains(desktop).send_keys(self.msa_account + Keys.RETURN).perform()
                logging.info("Signing in.")
                time.sleep(10)

            except:
                logging.debug("Did not see 'Use another account or sign up.'")

            # Look for sign in window
            try:
                logging.info("Checking for sign in window...")
                email_box = WebDriverWait(desktop, 30).until(EC.presence_of_element_located((By.XPATH, "//*[contains(@Name, 'Email or phone')]")))
                time.sleep(1)
                email_box.click()
                time.sleep(1)
                ActionChains(desktop).send_keys(self.msa_account + Keys.RETURN).perform()
                logging.info("Signing in.")
                time.sleep(15)
            except:
                # self._page_source(desktop)
                logging.info("Did not find sign in field")

            # Look for Password field
            try:
                logging.info("Checking for Password field...")
                # Password is not part of the Teams app, so need to use desktop driver
                WebDriverWait(desktop, 30).until(EC.presence_of_element_located((By.XPATH,"//*[contains(@Name, 'Password') or contains(@Name, 'the password for')]")))
                try:
                    desktop.find_element_by_xpath("//*[contains(@Name, 'Password') or contains(@Name, 'the password for')]").click()
                    time.sleep(5)
                    ActionChains(desktop).send_keys(self.msa_password + Keys.RETURN).perform()
                    time.sleep(5)

                    # Look for the prompt to Sign in Everywhere with this account
                    try:
                        # desktop.find_element_by_xpath("//HyperLink[@Name = 'No, sign in to this app only']").click()
                        desktop.find_element_by_xpath("//Button[contains(@Name, 'No,')]").click()
                        logging.debug("Found Stay Signed In Prompt")
                    except:
                        logging.debug("Didn't find Stay Signed In Prompt")
                        pass
                    time.sleep(10)

                except:
                    logging.info("Password field not found, previously logged in?")
            except:
                logging.info("Did not find Password field or Continue button! Possible Exception?")

            time.sleep(5)
            
            # Check for Get started button
            try:
                logging.info("Checking for Get started button...")
                teams_driver.find_element_by_name("Get started").click()
                logging.info("Clicked Get started.")
                time.sleep(10)
            except:
                logging.info("Get started button not found.")

            # Check for Continue button
            try:
                logging.info("Checking for Continue button...")
                teams_driver.find_element_by_name("Continue").click()
                logging.info("Clicked Continue.")
                time.sleep(5)
            except:
                logging.info("Continue button not found.")

            # Check for 'Continue as' pane
            try:
                logging.info("Checking for 'Continue as' pane.")
                teams_driver.find_element_by_accessibility_id("firstAccount").click()
                logging.info("Found 'Continue as' pane.")
                time.sleep(5)
            except:
                logging.info("Did not find 'Continue as' pane.")

            # Check for 'Where would you like to start?' pane
            try:
                logging.info("Checking for 'Where would you like to start?' pane.")
                teams_driver.find_element_by_accessibility_id("firstItem").click()
                logging.info("Found 'Where would you like to start?' pane.")
                time.sleep(5)
            except:
                logging.info("Did not find 'Where would you like to start?' pane.")

            # Check for 'Welcome to Teams' pane
            try:
                logging.info("Checking for Sign in button")
                teams_driver.find_element_by_name("Sign in to Microsoft Teams").click()
                logging.info("Clicked Sign in")
                time.sleep(5)
            except:
                logging.info("Sign in button not found.")

            # Check for 'Sign in to your account' pane
            try:
                logging.info("Checking for sign in field...")
                email_box = desktop.find_element_by_xpath("//*[contains(@Name, 'mail, phone, or Skype') or contains(@Name, 'Email address') or contains(@Name, 'Sign-in address')]")
                # Click twice just in case (needed with some versions)
                time.sleep(1)
                email_box.click()
                time.sleep(1)
                email_box.click()
                time.sleep(1)
                ActionChains(desktop).send_keys(self.msa_account + Keys.RETURN).perform()
                logging.info("Signing in.")
                time.sleep(5)
            except:
                # self._page_source(desktop)
                logging.info("Did not find sign in field")
                # self.fail("Did not see login")

            # Look for Password field again
            try:
                logging.info("Checking for Password field...")
                try:
                    desktop.find_element_by_xpath("//*[contains(@Name, 'Enter the password')  or contains(@Name, 'the password for')]").click()
                    time.sleep(2)
                    ActionChains(desktop).send_keys(self.msa_password + Keys.RETURN).perform()
                    time.sleep(5)
                except:
                    logging.info("Password field not found, previously logged in?")

                # Look for the prompt to Sign in Everywhere with this account
                try:
                    # desktop.find_element_by_xpath("//HyperLink[@Name = 'No, sign in to this app only']").click()
                    desktop.find_element_by_xpath("//Button[contains(@Name, 'No,')]").click()
                    logging.debug("Found Stay Signed In Prompt")
                except:
                    logging.debug("Didn't find Stay Signed In Prompt")
                    pass
                time.sleep(20)

            except Exception as e:
                logging.info("Did not find Password field or Continue button! Possible Exception?")
            time.sleep(5)

        # Check for Connect Teams to Office
        try:
            logging.info("Looking for Office popup")
            WebDriverWait(teams_driver, 30).until(EC.presence_of_element_located((By.XPATH,"//*[contains(@Name, 'Teams with Office')]")))
            teams_driver.find_element_by_xpath("//Button[contains(@Name, 'do it')]").click()
        except:
            logging.debug("Didn't find connect Teams to Office popup")

        # logging.info("Closing Teams")
        # self._kill("ms-teams.exe")
        # time.sleep(5)
        # logging.info("Relaunching Teams with accessibility on to continue and adjust settings.")
        # # Launch Teams via command line with argument to force accessibility tags for automation
        # self._call([self.userprofile + "\\appdata\\local\\Microsoft\\Teams\\Current\\teams.exe", "--force-renderer-accessibility"], blocking=False)
        # time.sleep(20)

        # Check again for Password dialog
        try:
            logging.info("Checking for Password field...")
            # Password is not part of the Teams app, so need to use desktop driver
            # WebDriverWait(desktop, 60).until(EC.presence_of_element_located((By.XPATH,"//*[contains(@Name, 'Enter the password for ') or contains(@Name, 'Continue')]")))
            try:
                desktop.find_element_by_xpath("//*[contains(@Name, 'Enter the password for ')  or contains(@Name, 'the password for')]").click()
                time.sleep(2)
                # ActionChains(desktop).send_keys(self.password + Keys.RETURN).perform()
                ActionChains(desktop).send_keys(self.msa_password + Keys.RETURN).perform()
                time.sleep(5)
            except:
                logging.info("Password field not found, previously logged in?")

            # Look for the prompt to Sign in Everywhere with this account
            try:
                # desktop.find_element_by_xpath("//HyperLink[@Name = 'No, sign in to this app only']").click()
                desktop.find_element_by_xpath("//Button[contains(@Name, 'No,')]").click()
                logging.debug("Found Stay Signed In Prompt")
            except:
                logging.debug("Didn't find Stay Signed In Prompt")
                pass
            time.sleep(20)

        except Exception as e:
            logging.info("Did not find Password field or Continue button! Possible Exception?")

        # Get driver to window
        # teams_driver = self.getDriverFromWin(WebDriverWait(desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Pane[@ClassName="Chrome_WidgetWin_1"]'))))

        # Get Teams window driver for new window
        logging.info("Creating Teams Driver")
        win = WebDriverWait(desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "| Microsoft Teams")]')))
        teams_driver = self.getDriverFromWin(win)
        logging.info("Found Teams window")

        # time.sleep(10)

        # Check for Connect Teams to Office (Sometimes opens on second launch)
        try:
            logging.info("Looking for Office popup")
            WebDriverWait(teams_driver, 30).until(EC.presence_of_element_located((By.XPATH,"//*[contains(@Name, 'Teams with Office')]")))
            teams_driver.find_element_by_xpath("//Button[contains(@Name, 'do it')]").click()
        except:
            logging.debug("Didn't find connect Teams to Office popup")
        
        # Check for new Teams prompt
        try:
            logging.info("Checking for New Teams prompt...")
            WebDriverWait(teams_driver, 10).until(EC.presence_of_element_located((By.XPATH,"//*[contains(@Name, 'updates to the new Teams')]")))
            teams_driver.find_element_by_xpath("//*[contains(@Name, 'Later')]").click()
            logging.info("Got New Teams prompt, clicked 'Later'")
        except:
            logging.debug("Didn't see New Teams prompt")

        # Maximize the window
        try:
            logging.info("Maximizing window")
            ActionChains(teams_driver).key_down(Keys.LEFT_ALT).key_down(Keys.SPACE).key_up(Keys.SPACE).key_up(Keys.LEFT_ALT).perform()
            time.sleep(3)
            ActionChains(teams_driver).key_down("x").key_up("x").perform()
            time.sleep(3)
        except:
            pass

        # Wait for the Teams window and click Continue
        try:
            logging.info("Checking for Continue button...")
            WebDriverWait(teams_driver, 30).until(EC.presence_of_element_located((By.XPATH,"//*[contains(@Name, 'Continue')]")))
            desktop.find_element_by_xpath("//*[contains(@Name, 'Continue')]").click()
            logging.info("Clicked Continue.")
            time.sleep(15)
        except Exception as e:
            logging.info("Couldn't find Continue button.  Could be already activated.  If not, is your MSA account registered with an organization?")

        # Check for "Try it now" popup
        try:
            logging.info("Checking for 'Try it now' button...")
            desktop.find_element_by_xpath("//*[contains(@Name, 'Try it now')]").click()
            logging.info("Clicked 'Try it now'.")
            time.sleep(10)
        except:
            logging.info("'Try it now' button not found.")

        # Check for "Next" popup
        try:
            logging.info("Checking for 'Next' button...")
            desktop.find_element_by_xpath("//*[contains(@Name, 'Next')]").click()
            logging.info("Clicked 'Next'.")
            time.sleep(10)
        except:
            logging.info("'Next' button not found.")


        # Check for "Got it" popup
        try:
            logging.info("Checking for 'Got it' button...")
            desktop.find_element_by_name('Got it').click()
            logging.info("Clicked 'Got it'.")
            time.sleep(10)
        except:
            logging.info("'Got it' button not found.")

        # Escape out of any other popups
        ActionChains(desktop).send_keys(Keys.ESCAPE).perform()

        # Close the "Get the Teams mobile app" popup
        ActionChains(desktop).send_keys(Keys.ENTER).perform()

        # Set Teams Settings
        if self.set_teams_settings == "1":
            try:
                # Modify settings
                logging.info("Modifying settings to not auto start")
                WebDriverWait(teams_driver, 20).until(EC.presence_of_element_located((By.XPATH,"//*[contains(@Name, 'Settings and more')]")))
                elmt = teams_driver.find_element_by_xpath("//*[contains(@Name, 'Settings and more')]")
                self.clickCenter(teams_driver, elmt)

                time.sleep(5)
                try:
                    settings_button = teams_driver.find_element_by_xpath("//MenuItem[@Name='Settings']")
                    settings_button.click()
                    time.sleep(2)
                except:
                    # A popup might have dismissed the menu, so try again
                    elmt = teams_driver.find_element_by_xpath("//*[contains(@Name, 'Settings and more')]")
                    self.clickCenter(teams_driver, elmt)
                    time.sleep(5)
                    settings_button = teams_driver.find_element_by_xpath("//MenuItem[@Name='Settings']")
                    settings_button.click()
                    time.sleep(2)
                


                # General settings (Default)
                teams_driver.find_element_by_name("General").click()
                time.sleep(2)
                # Uncheck settings to auto-start and keep running on close.
                settings = teams_driver.find_elements_by_xpath("//CheckBox")
                # settings_to_check = [4, 9, 10] # None
                settings_to_check = [4] # None
                settings_to_skip = [5, 6, 8, 9, 10, 11] # Skip these settings, not checkboxes
                setting_num = 0

                for setting in settings:
                    setting_num += 1
                    ActionChains(teams_driver).send_keys(Keys.TAB).perform()
                    time.sleep(2)

                    while setting_num in settings_to_skip:
                        ActionChains(teams_driver).send_keys(Keys.TAB).perform()
                        time.sleep(2)
                        setting_num += 1

                    setting_state = setting.is_selected()
                    setting_name = setting.get_attribute("Name")

                    logging.debug(setting_name + " checked state: " + str(setting_state))
                    time.sleep(2)

                    # Turn off everything
                    if setting_num in settings_to_check and setting_state == False:
                        logging.debug("Setting " + setting_name + " is unchecked, checking it.")
                        ActionChains(teams_driver).send_keys(Keys.SPACE).perform()
                        time.sleep(2)

                    elif setting_num not in settings_to_check and setting_state == True:
                        logging.debug("Setting " + setting_name + " is checked, unchecking it.")
                        ActionChains(teams_driver).send_keys(Keys.SPACE).perform()
                        time.sleep(2)

                    if setting_num >= 10:
                        break

                time.sleep(2)
                # Acounts and orgs
                # Privacy
                # Notifications and activity
                # Appearance and accessibility
                # Files and links
                # App permissions
                # Calls
                # Captions and transcripts
                # Devices
                # Recognition

            except Exception as e:
                self._page_source(teams_driver)
                raise e

        if self.update_teams == "1":
            # Force updates to specified version
            logging.info("Updating to specified version...")
            try:
                elmt = teams_driver.find_element_by_xpath("//*[contains(@Name, 'Settings and more')]")
                self.clickCenter(teams_driver, elmt)
            except:
                teams_driver.find_element_by_xpath("//*[contains(@Name, 'Profile, app settings, and more')]").click()
            time.sleep(5)

            try:
                elmt = teams_driver.find_element_by_name("Settings")
                self.clickCenter(teams_driver, elmt)
            except:
                elmt = teams_driver.find_element_by_xpath("//*[contains(@Name, 'Settings and more')]")
                self.clickCenter(teams_driver, elmt)
                time.sleep(5)
                elmt = teams_driver.find_element_by_name("Settings")
                self.clickCenter(teams_driver, elmt)
            
            teams_driver.find_element_by_name("About Teams").click()
            time.sleep(2)

            # While waiting for updates, pin Teams to Task Bar
            logging.info("Pinning Teams to task bar...")
            try:
                error = "Can't find Microsoft Teams icon"
                try:
                    app_elem = self._get_app_tray(desktop).find_element_by_name("Microsoft Teams (work or school) - 1 running window")
                except:
                    app_elem = self._get_app_tray(desktop).find_element_by_name("Microsoft Teams - 1 running window")
                error = "Can't context click Microsoft Teams icon"
                ActionChains(desktop).context_click(app_elem).perform()
                time.sleep(1)
                error = "Can't find Pin to taskbar"

                try:
                    desktop.find_element_by_name("Unpin from taskbar")
                    logging.info("Microsoft Teams already pinned.")
                except:
                    pinbutton = desktop.find_element_by_name("Pin to taskbar")
                    error = "Can't click Pin to taskbar"
                    pinbutton.click()
                    logging.info("Microsoft Teams now pinned.")
            except:
                logging.info(error)

            # Finish waiting for update
            logging.info("Finish waiting for update...")
            try:
                WebDriverWait(teams_driver, 360).until(EC.presence_of_element_located((By.XPATH,"//*[contains(@Name, 'Update now') or contains(@Name, 'got the latest version')]")))
            except:
                logging.info("Did not see client update, verify Teams Version")
            else:
                try:
                    teams_driver.find_element_by_xpath("//*[contains(@Name, 'Update now')]").click()
                    logging.info("Updating Teams and waiting 30s...")
                    time.sleep(30)
                except:
                    logging.info("No refresh indicated.")
                # Sometimes after refreshing, refresh prompt is still there, so try again
                try:
                    teams_driver.find_element_by_xpath("//*[contains(@Name, 'Update now')]").click()
                    logging.info("Updating Teams again and waiting 30s...")
                    time.sleep(30)
                except:
                    pass

                # Get Teams window driver
                logging.info("Creating Teams Driver")
                win = WebDriverWait(desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Microsoft Teams")]')))
                teams_driver = self.getDriverFromWin(win)
                logging.info("Found Teams window")
                time.sleep(5)

                # Wait for the Teams window and click Continue
                try:
                    logging.info("Checking for Continue button...")
                    WebDriverWait(teams_driver, 15).until(EC.presence_of_element_located((By.XPATH,"//*[contains(@Name, 'Continue')]")))
                    desktop.find_element_by_xpath("//*[contains(@Name, 'Continue')]").click()
                    logging.info("Clicked Continue.")
                    time.sleep(15)
                except Exception as e:
                    logging.info("Couldn't find Continue button.  Could be already activated.  If not, is your MSA account registered with an organization?")

                # Check for "Try it now" popup
                try:
                    logging.info("Checking for 'Try it now' button...")
                    WebDriverWait(teams_driver, 60).until(EC.presence_of_element_located((By.XPATH,"//*[contains(@Name, 'Try it now')]")))
                    desktop.find_element_by_xpath("//*[contains(@Name, 'Try it now')]").click()
                    logging.info("Clicked 'Try it now'.")
                    time.sleep(10)
                except:
                    logging.info("'Try it now' button not found.")


        # Delete reg key to run Teams update so that updater doesn't open teams app on reboot
        self._call(['cmd.exe', r'/C reg.exe DELETE "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /f /v com.squirrel.Teams.Teams'], expected_exit_code="")

        # Close teams
        # self._kill("ms-teams.exe")
        self.closeTeams(desktop)
        time.sleep(5)

        # Relaunch teams to check for finish setup
        # Launch teams
        logging.info("Relaunching Teams to finish setup, wait 10s")
        self._call(["powershell", "start msteams:"])
        time.sleep(10)

        # self._page_source(desktop)

        # Again select 'use other account'.  Then it should automatically sign in.
        try:
            logging.info("Checking for Use another account or sign up")
            WebDriverWait(desktop, 30).until(EC.presence_of_element_located((By.XPATH,"//*[contains(@Name, 'another account')]")))
            desktop.find_element_by_xpath("//*[contains(@Name, 'another account')]").click()
            logging.info("Clicked Use another account or sign up.")
            #Attempts to enter credentials
            logging.info("Wait 30s to sign in")
            time.sleep(30)
        except:
            logging.debug("Did not see 'Use another account or sign up.'")

        try:
            WebDriverWait(desktop, 30).until(EC.presence_of_element_located((By.XPATH,"//Button[contains(@Name, 'Finish setup')]")))
            desktop.find_element_by_xpath("//Button[contains(@Name, 'Finish setup')]").click()

        except:
            # self._kill("ms-teams.exe")
            self.closeTeams(desktop)
            self.successful_install = True
            self.createPrepStatusControlFile()
            return

        # This takes FOREVER to finish setup sometimes...
        WebDriverWait(desktop, 900).until(EC.presence_of_element_located((By.XPATH,"//Button[contains(@Name, 'Sign in') or contains(@Name, 'another account')]")))
        desktop.find_element_by_xpath("//Button[contains(@Name, 'Sign in') or contains(@Name, 'another account')]").click()
        time.sleep(2)
        
        # Sign in again
        try:
            logging.info("Checking for sign in field...")
            email_box = WebDriverWait(desktop, 30).until(EC.presence_of_element_located((By.XPATH, "//*[contains(@Name, 'mail, phone, or Skype')]")))
            time.sleep(1)
            email_box.click()
            time.sleep(1)
            email_box.click()
            time.sleep(1)
            ActionChains(desktop).send_keys(self.msa_account + Keys.RETURN).perform()
            logging.info("Signing in.")
            time.sleep(15)
        except:
            # self._page_source(desktop)
            logging.info("Did not find sign in field")

        # self._kill("ms-teams.exe")
        self.closeTeams(desktop)
        self.successful_install = True
        self.createPrepStatusControlFile()

    def closeTeams(self, driver):
            self._kill("ms-teams.exe")
            return
            # ActionChains(driver).key_down(Keys.LEFT_ALT).key_down(Keys.F4).key_up(Keys.LEFT_ALT).perform()
            # time.sleep(1)
            # ActionChains(driver).key_down(Keys.ESCAPE).perform()
            # time.sleep(1)
            # ActionChains(driver).key_down(Keys.LEFT_ALT).key_down(Keys.F4).key_up(Keys.LEFT_ALT).perform()
            # time.sleep(1)
            # ActionChains(driver).key_down(Keys.ESCAPE).perform()

    def tearDown(self):
        core.app_scenario.Scenario.tearDown(self)

        # Close teams
        self._kill("ms-teams.exe")


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
        return driver


    def clickCenter(self, driver, elem):
        # elem_coords = elem.location
        # elem_size = elem.size
        # x = elem_coords["x"] + (elem_size["width"] / 2)
        # y = elem_coords["y"] + (elem_size["height"] / 2)
        # logging.debug("COORDS: x={0}, y={1}, w={2}, h={3}, cx={4}, cy={5}".format(elem_coords['x'], elem_coords['y'], elem_size['width'], elem_size['height'], x, y))
        # ActionChains(driver).move_by_offset(x, y).click().perform()
        ActionChains(driver).move_to_element(elem).click().perform()


    def kill(self):
        try:
            logging.debug("Killing open drivers")
            self._kill("WinAppDriver.exe Teams.exe ms-teams.exe SystemSettings.exe")
        except:
            pass
        
