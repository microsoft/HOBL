# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Prepare the Productivity Powershell test
#
# Setup instructions:
##

import builtins
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

class ProductivityPrep(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'email_account', Params.get('global', 'msa_account'))
    Params.setDefault(module, 'email_password', Params.get('global', 'dut_password'))
    Params.setDefault(module, 'fast_mode', '0')

    # Get parameters
    email_account = Params.get(module, 'email_account')
    email_password = Params.get(module, 'email_password')
    fast_mode = Params.get(module, 'fast_mode')

    is_prep = True

    excel_doc = "FamilyBudget.xlsx"
    word_long_doc = "test_long_doc.docx"
    word_untrusted_doc = "Test-Scrolling-3d.docx"
    ppt_doc = "sample.pptx"

    outlook_driver = None
    onenote_driver = None
    word_driver = None
    excel_driver = None
    ppt_driver = None

    def runTest(self):
        if Params.get("global", "local_execution") == "0":
            self.userprofile = self._call(["cmd.exe", "/C echo %USERPROFILE%"])
        else:
            self.userprofile = os.environ['USERPROFILE']
        # Flag to indicate if prep passed successfully
        self.success = False

        # Kill MSOsync to prevent handles to open files
        try:
            self._kill("msosync.exe") # msosync can keep file handles open from time to time, preventing re-upload
        except:
            # Try again
            logging.debug("Killing msosync failed, trying again.")
            self._kill("msosync.exe") # msosync can keep file handles open from time to time, preventing re-upload
        time.sleep(5)

        # self.userprofile = self._call(["cmd", "/C echo %USERPROFILE%"])
        # Delete outlook *.ost file to prevent errors trying to load .pst already in use
        # self._call(["cmd.exe", "/c del %localappdata%\\microsoft\\outlook\\*.ost"], expected_exit_code="")

        # Delete folders uploaded OneDrive in prior versions of HOBL, so that they don't continue to sync.
        self._call(["cmd.exe", "/C rmdir /s /q " + self.userprofile + "\\OneDrive\\productivity_content"], expected_exit_code="")
        self._call(["cmd.exe", "/C rmdir /s /q " + self.userprofile + "\\OneDrive\\abl_resources"], expected_exit_code="")

        # Upload documents used by Office apps
        self.onedrive_path = self.userprofile + "\\OneDrive\\abl_docs\\"
        try:
            self._upload("scenarios\\windows\\_library\\productivity\\prod_setup\\abl_docs", self.userprofile + "\\OneDrive")
        except:
            logging.debug("Could not copy productivity content to onedrive.")
        # # Upload .pst file used to import emails into Outlook.  Don't upload to OneDrive as it can cause excessive syncing.
        # try:
        #     self._upload(os.path.join("scenarios", "abl_resources", "HOBLTest.pst"), self.dut_exec_path)
        # except:
        #     logging.debug("Could not copy HOBLTest.pst file to c:\hobl_bin on DUT.")

        # Show file extensions (necessary for scripts to match certain window titles properly, like Word)
        self._call(["cmd.exe", r"/C reg add HKCU\software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v HideFileExt /t REG_DWORD /f /d 00000000"])

        try:
            # Hide Windows Search box to make sure there is room for all the taskbar icons we want to add
            self._call(["cmd.exe", r"/C reg add HKCU\software\Microsoft\Windows\CurrentVersion\Search /v SearchboxTaskbarMode /t REG_DWORD /f /d 00000000"])
        except:
            pass

        # Disable auto-recover on Office apps.  This is necessary to be able to recover from a mishap (lost keys or mouse clicks) in a subsequent loop.
        self._call(["cmd.exe", r"/C reg add HKCU\Software\Microsoft\office\16.0\excel\options /v AutoRecoverEnabled /t REG_DWORD /f /d 00000000"])
        self._call(["cmd.exe", r"/C reg add HKCU\Software\Microsoft\office\16.0\PowerPoint\options /v SaveAutoRecoveryInfo /t REG_DWORD /f /d 00000000"])
        self._call(["cmd.exe", r"/C reg add HKCU\Software\Microsoft\office\16.0\Word\options /v KeepUnsavedChanges /t REG_DWORD /f /d 00000000"])

        # Disable Design Ideas suggestions in PowerPoint because of it's indeterminant behavior causing wild power variations.
        self._call(["cmd.exe", r"/C reg add HKCU\Software\Microsoft\office\16.0\PowerPoint\options /v EnableSuggestionServiceUserSetting /t REG_DWORD /f /d 00000000"])

        # Show powerpoint ribbon.
        self._call(["cmd.exe", r"/C reg add HKCU\Software\Microsoft\Office\16.0\Common\Toolbars\PowerPoint /v QuickAccessToolbarStyle /t REG_DWORD /f /d 00000016"])

        # Disable OneNote full screen on pen undock.
        self._call(["cmd.exe", r"/C reg add HKCU\Software\Microsoft\Office\16.0\OneNote\Options /v FullPageModeOnPenUndock /t REG_DWORD /f /d 00000000"])

        # Force "mouse mode" in Office, so that the UI doesn't change when blade is attached/detached.
        self._call(["cmd.exe", r"/C reg add HKCU\Software\Microsoft\Office\16.0\Common /v OverridePointerMode /t REG_DWORD /f /d 00000001"])
        self._call(["cmd.exe", r"/C reg add HKCU\Software\Microsoft\Office\16.0\Common /v OverrideTabletMode /t REG_DWORD /f /d 00000001"])
        self._call(["cmd.exe", r"/C reg add HKCU\Software\Microsoft\Office\16.0\Common /v PointerModeInitVersion /t REG_DWORD /f /d 00000001"])

        # Set TeachCallouts to indicate they'be been completed
        key = 'HKCU\\SOFTWARE\\Microsoft\\Office\\16.0\\Common\\TeachingCallouts'
        self._call(["cmd.exe", f'/C reg add "{key}" /v "AccCheckerStatusBarTeachingCallout" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "AutoSaveFirstSaveExcel" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "AutoSaveFirstSavePPT" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "AutoSaveFirstSaveWord" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "AutoSaveToggleOnExcel" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "AutoSaveToggleOnPPT" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "AutoSaveToggleOnWord" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "CloudSettingsSyncTeachingCallout" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "FocusedInboxTeachingCallout_2" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "HubBarTeachingCallout" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "MessageExtensionsTeachingCallout" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "Olk_SearchBoxTitleBar_SLR_Sequence" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "OneNoteFullPageViewButtonCallout" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "OneNoteInkCalloutId" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "OneNoteModernLayoutVerticalCollapsedStateSequence" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "OneNoteModernLayoutVerticalExpandedStateSequence" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "PPT_InsertCameo_Callout" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "PPT_RecordVideoPresentation_Callout" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "RibbonOverflowTeachingCalloutID" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "RoamingSigTeachingCallout" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "SLRToggleReplaceTeachingCalloutID" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "TryNewOutlookToggle" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "UseTighterSpacingTeachingCallout" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "UseToDoAppTeachingCallout" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "VersionHistoryRenameCalloutExcel" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "VersionHistoryRenameCalloutPPT" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "VersionHistoryRenameCalloutWord" /t REG_DWORD /d 2 /f > null 2>&1'])
        self._call(["cmd.exe", f'/C reg add "{key}" /v "Word_Paste_MergeFormatByDefault" /t REG_DWORD /d 2 /f > null 2>&1'])

        logging.info("Launching WinAppDriver.exe on DUT.")
        self._call([(self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"), (self.dut_resolved_ip + " " + self.app_port + " /forcequit")], blocking=False)
        time.sleep(1)

        desired_caps = {}
        desired_caps["app"] = "Root"
        self.desktop = self._launchApp(desired_caps)
        self.desktop.implicitly_wait(0)

        # Dismiss secruity popup
        try:
            logging.info("Checking for system notification")
            self.desktop.find_element_by_name('Move notification to notification center').click()
            time.sleep(3)
        except:
            pass

        # Pin toastabl
        # if Params.get("global", "local_execution") == "1":
            # # Pin ABL Toast if in ABL Phase 1 (this uses toastABL icon window)
            # try:
            #     logging.info("Pinning ToastABL icon to task bar.")
            #     error = "Can't find ABL TOAST2020 - 1 running window"
            #     app_elem = self._get_app_tray(self.desktop).find_element_by_name("ABL TOAST2020 - 1 running window")
            #     error = "Can't context click ABL TOAST2020"
            #     ActionChains(self.desktop).context_click(app_elem).perform()
            #     time.sleep(1)
            #     error = "Can't find Pin to taskbar"
            #     pinbutton = self.desktop.find_element_by_name("Pin to taskbar")
            #     error = "Can't click Pin to taskbar"
            #     pinbutton.click()
            #     logging.info("ABL TOAST2020 now pinned.")
            # except Exception as e :
            #     logging.info(error)

            # # Now try to Pin Powershell to taskbar
            # try:
            #     logging.info("Selecting Start.")
            #     start_button = self._get_search_button(self.desktop)
            #     start_button.click()
            #     time.sleep(3)
            #     logging.info("Pinning Windows Powershell to task bar.")
            #     app = "Windows PowerShell"
            #     self.slow_send_keys("app:" + app).perform()
            #     time.sleep(2)
            #     app_item = self.desktop.find_element_by_name("Results").find_element_by_name("Windows PowerShell, App, Press right to switch preview")
            #     ActionChains(self.desktop).context_click(app_item).perform()
            #     time.sleep(1)
            #     error = "Can't find Pin to taskbar"
            #     pinbutton = self.desktop.find_element_by_name("Pin to taskbar")
            #     error = "Can't click Pin to taskbar"
            #     pinbutton.click()
            #     logging.info("Windows Powershell now pinned.")
            # except Exception as e :
            #     logging.info(error)
            # time.sleep(1)

        # Pin Powershell to taskbar
        try:
            error = "Can't find Windows PowerShell - 1 running window"
            app_elem = self._get_app_tray(self.desktop).find_element_by_name("Windows PowerShell - 1 running window")
            error = "Can't context click Powershell"
            ActionChains(self.desktop).context_click(app_elem).perform()
            time.sleep(1)
            error = "Can't find Pin to taskbar"
            pinbutton = self.desktop.find_element_by_name("Pin to taskbar")
            error = "Can't click Pin to taskbar"
            pinbutton.click()
            logging.info("Powershell now pinned.")
        except Exception as e :
            logging.info(error)

        # Pin simple remote console
        try:
            error = "Can't find SimpleRemoteConsole_Admin - 1 running window"
            app_elem = self._get_app_tray(self.desktop).find_element_by_name("SimpleRemoteConsole_Admin - 1 running window")
            error = "Can't context click SRC"
            ActionChains(self.desktop).context_click(app_elem).perform()
            time.sleep(1)
            error = "Can't find Pin to taskbar"
            pinbutton = self.desktop.find_element_by_name("Pin to taskbar")
            error = "Can't click Pin to taskbar"
            pinbutton.click()
            logging.info("SimpleRemoteConsole now pinned.")
        except Exception as e :
            logging.info(error)

        # Dismiss context menu with ESCAPE (needed for early Win11 bug)
        ActionChains(self.desktop).send_keys(Keys.ESCAPE).perform()
        time.sleep(2)

        # Unpin the new Outlook, if it exists
        try:
            logging.info("Checking for 'Outlook (new)'.")
            icon = self._get_app_tray(self.desktop).find_element_by_name("Outlook (new)")
        except Exception as e1:
            try:
                logging.info("Name not found, checking for Outlook by AutomationId")
                icon = self._get_app_tray(self.desktop).find_element_by_accessibility_id("Appid: Microsoft.OutlookForWindows_8wekyb3d8bbwe!Microsoft.OutlookforWindows")
            except Exception as e2:
                logging.info("Neither Outlook (New) not AutomationId variant found")
                icon = None
        if icon:
            try:
                time.sleep(3)
                ActionChains(self.desktop).move_to_element(icon).context_click().perform()
                time.sleep(3)
                logging.info("Unpinning Outlook.")
                self.desktop.find_element_by_name("Unpin from taskbar").click()
                time.sleep(1)
            except Exception as e3:
                logging.warning("Failed to unpin Outlook: %s", str(e3))
        pass
        # New method, avoiding use of unreliable Start menu
        # Check for pinned apps
        for app in ["Outlook (classic)", "Word", "OneNote", "PowerPoint", "Excel"]:
            try:
                app_elem = self._get_app_tray(self.desktop).find_element_by_name(app)
                logging.info(app + " already pinned.")
            except:
                try:
                    app_cmd = app.upper()
                    if app == "Word":
                        app_cmd = "WINWORD"
                    elif app == "PowerPoint":
                        app_cmd = "POWERPNT"
                    elif app == "Outlook (classic)":
                        app_cmd = "OUTLOOK"
                    app_cmd = app_cmd + ".EXE" 
                    try:
                        app_elem = self.desktop.find_element_by_accessibility_id("Appid: Microsoft.Office." + app_cmd + ".15")
                    except:
                        app_elem = self.desktop.find_element_by_accessibility_id("Microsoft.Office." + app_cmd + ".15")
                except:
                    app_elem = None
            if app_elem:
                logging.info(app + " already pinned.")
                continue

            self._call(["cmd.exe", "/C start " + app_cmd], blocking=False)
            time.sleep(10)
            if app == "OneNote":
                time.sleep(10)

            try:
                icon = self.desktop.find_element_by_accessibility_id("Appid: Microsoft.Office." + app_cmd + ".15")
            except:
                icon = self.desktop.find_element_by_accessibility_id("Microsoft.Office." + app_cmd + ".15")

            ActionChains(self.desktop).move_to_element(icon).context_click().perform()
            time.sleep(3)
            self.desktop.find_element_by_name("Pin to taskbar").click()

            # Unpin and repin to work around Windows bug
            time.sleep(3)
            ActionChains(self.desktop).move_to_element(icon).context_click().perform()
            time.sleep(3)
            self.desktop.find_element_by_name("Unpin from taskbar").click()
            time.sleep(3)
            ActionChains(self.desktop).move_to_element(icon).context_click().perform()
            time.sleep(3)
            self.desktop.find_element_by_name("Pin to taskbar").click()

                # Pin it
                # Launch from command line
                # app_cmd = app.upper()
                # if app == "Word":
                #     app_cmd = "WINWORD"
                # if app == "PowerPoint":
                #     app_cmd = "POWERPNT"
                # if app == "Outlook (classic)":
                #     app_cmd = "OUTLOOK"
                # app_cmd = app_cmd + ".EXE"
                # self._call(["cmd.exe", "/C start " + app_cmd], blocking=False)
                # time.sleep(10)
                # if app == "OneNote":
                #     time.sleep(10) # wait 10 more seconds for OneNote to update app if necessary
                # try:
                #     icon = self.desktop.find_element_by_accessibility_id("Appid: Microsoft.Office." + app_cmd + ".15")
                # except:
                #     icon = self.desktop.find_element_by_accessibility_id("Microsoft.Office." + app_cmd + ".15")
                # ActionChains(self.desktop).move_to_element(icon).context_click().perform()
                # time.sleep(3)
                # self.desktop.find_element_by_name("Pin to taskbar").click()
                # # Unpin and repin to work around Windows bug that results in blank icons
                # time.sleep(3)
                # ActionChains(self.desktop).move_to_element(icon).context_click().perform()
                # time.sleep(3)
                # self.desktop.find_element_by_name("Unpin from taskbar").click()
                # time.sleep(3)
                # ActionChains(self.desktop).move_to_element(icon).context_click().perform()
                # time.sleep(3)
                # self.desktop.find_element_by_name("Pin to taskbar").click()

        # Kill all the apps because the popups are too hard to deal with when all apps are open
        self._kill("Outlook.exe OneNote.exe Excel.exe Powerpnt.exe Winword.exe")


        ##############################
        # Outlook
        ##############################

        self.launchOrSwitchApp(self.desktop, "Outlook")
        logging.info("Waiting 20s for Outlook to fully open.")
        time.sleep(20)
        self.desktop = self._launchApp(desired_caps)
        # self.desktop.implicitly_wait(5)

        
        if self.fast_mode == '0':
            max_loops = 30
            for x in range(max_loops):
                open_windows = 0

                try:
                    logging.info("Checking reopen item prompt")
                    self.desktop.find_element_by_name('No').click()
                    time.sleep(3)
                except:
                    pass

                try:
                    logging.info("Checking for Theme popup")
                    self.desktop.find_element_by_xpath('//*[contains(@Name, "Choose a theme")]')
                    self.desktop.find_element_by_name('OK').click()
                    logging.info("Clicked OK on Theme popup.")
                    time.sleep(3)
                except:
                    pass

                try:
                    logging.info("Checking for Got it")
                    self.desktop.find_element_by_name('Got it').click()
                    time.sleep(3)
                except:
                    pass

                try:
                    logging.info("Checking for 'Microsoft respects your privacy'")
                    win = self.desktop.find_element_by_name('Microsoft respects your privacy')
                    win.find_element_by_name("Next").click()
                    time.sleep(3)
                except:
                    pass

                try:
                    logging.info("Checking for privacy pop up")
                    self.desktop.find_element_by_name('Getting better together')
                except:
                    pass
                else:
                    # Click "Don't send optional data"
                    # self.desktop.find_element_by_name("Don't send").click()
                    self.desktop.find_element_by_xpath('//Button[contains(@Name, "t send")]').click()
                    time.sleep(2)

                try:
                    logging.info("Checking for 'Powering your experiences'")
                    self.desktop.find_element_by_name('Powering your experiences')
                except:
                    pass
                else:
                    self.desktop.find_element_by_name("Done").click()
                    time.sleep(2)


                try:
                    logging.info("Checking for Privacy option")
                    win = self.desktop.find_element_by_name('Your privacy option')
                    win.find_element_by_name("Close").click()
                    time.sleep(3)
                except:
                    pass

                try:
                    logging.info("Checking for Privacy matters")
                    win = self.desktop.find_element_by_name('Your privacy matters')
                    win.find_element_by_name("Close").click()
                    time.sleep(3)
                except:
                    pass

                try:
                    logging.info("Checking for Privacy Settings Applied")
                    win = self.desktop.find_element_by_name('Privacy Settings Applied')
                    win.find_element_by_name("OK").click()
                except:
                    pass

                try:
                    logging.info("Checking for safe mode pop up")
                    self.desktop.find_element_by_xpath('//*[contains(@Name, "safe mode")]')
                except:
                    pass
                else:
                    logging.info("Safe mode window is present")
                    open_windows += 1
                    self.desktop.find_element_by_name("No").click()
                    time.sleep(3)

                try:
                    logging.info("Checking for 'Don't personalize' button")
                    self.desktop.find_element_by_name("Don't personalize").click()
                    time.sleep(3)
                except:
                    pass

                try:
                    logging.info("Checking for 'cutting edge' pop up")
                    cutting_edge = self.desktop.find_element_by_name("You're on the cutting edge")
                except:
                    pass
                else:
                    logging.info("'Cutting edge' window is present")
                    open_windows += 1
                    cutting_edge.find_element_by_name("Close").click()
                    time.sleep(3)

                try:
                    logging.info("Checking for 'Get started' pop up")
                    get_started = self.desktop.find_element_by_name("Get started")
                except:
                    pass
                else:
                    logging.info("'Get started' window is present")
                    open_windows += 1
                    get_started.find_element_by_name("Get started").click()
                    time.sleep(3)

                try:
                    logging.info("Checking if we need to setup the account")
                    self.desktop.find_element_by_name("Outlook")
                    self.desktop.find_element_by_name("Advanced options collapsed")
                    self.desktop.find_element_by_name("Connect")
                except:
                    pass
                else:
                    logging.info("Account setup window is present")
                    open_windows += 1
                    ActionChains(self.desktop).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(self.email_account).perform()
                    # ActionChains(self.desktop).send_keys(Keys.TAB).send_keys(Keys.TAB).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(self.email_account).perform()
                    self.desktop.find_element_by_name("Connect").click()
                    time.sleep(10)
                    ActionChains(self.desktop).send_keys(self.password).send_keys(Keys.ENTER).perform()
                    time.sleep(5)
                    ActionChains(self.desktop).send_keys(Keys.ENTER).perform()
                    time.sleep(10)
                
                try:
                    logging.info("Checking problem with account")
                    self.desktop.find_element_by_name("Retry").click()
                    logging.info("Problem with account is present")
                    time.sleep(10)
                except:
                    pass

                try:
                    # If Retry, probably need to enter email again
                    logging.info("Checking Sign in")
                    self.desktop.find_element_by_name("Sign in")
                except:
                    pass
                else:
                    logging.info("Sign in window is present")
                    open_windows += 1
                    ActionChains(self.desktop).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(self.email_account).perform()
                    # ActionChains(self.desktop).send_keys(Keys.TAB).send_keys(Keys.TAB).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(self.email_account).perform()
                    self.desktop.find_element_by_name("Next").click()
                    time.sleep(7)
                    ActionChains(self.desktop).send_keys(self.password).send_keys(Keys.ENTER).perform()
                    time.sleep(5)
                    ActionChains(self.desktop).send_keys(Keys.ENTER).perform()
                    time.sleep(10)

                try:
                    logging.info("Checking for Windows Security")
                    self.desktop.find_element_by_name('Windows Security')
                except:
                    pass
                else:
                    logging.info("Security window is present")
                    open_windows += 1
                    password_field = self.desktop.find_element_by_name("Password")
                    password_field.click()
                    password_field.send_keys(self.email_password)
                    time.sleep(1)
                    self.desktop.find_element_by_name("Remember my credentials").click()
                    time.sleep(1)
                    self.desktop.find_element_by_name("OK").click()
                    time.sleep(1)

                try:
                    logging.info("Checking for Enter Password")
                    self.desktop.find_element_by_name('Enter Password')
                except:
                    pass
                else:
                    logging.info("Password window is present")
                    open_windows += 1
                    password_field = self.desktop.find_element_by_name("Password")
                    password_field.click()
                    password_field.send_keys(self.email_password)
                    time.sleep(1)
                    self.desktop.find_element_by_name("Remember my credentials").click()
                    time.sleep(1)
                    self.desktop.find_element_by_name("OK").click()
                    time.sleep(1)

                try:
                    logging.info("Checking for Advanced Setup")
                    WebDriverWait(self.desktop, 20).until(EC.presence_of_element_located((By.NAME,'Advanced setup')))
                except:
                    pass
                else:
                    logging.info("Advanced setup is present")
                    open_windows += 1
                    self.desktop.find_element_by_name("Microsoft 365").click()
                    time.sleep(5)

                try:
                    logging.info("Checking for Account is added window")
                    # Uncheck setup outlook mobile
                    phone_elem = WebDriverWait(self.desktop, 20).until(EC.presence_of_element_located((By.NAME,"Set up Outlook Mobile on my phone, too")))
                    if phone_elem.is_selected():
                        phone_elem.click()
                        time.sleep(1)
                    else:
                        logging.info("Set up Outlook Mobile is already unchecked")
                except:
                    pass
                else:
                    logging.info("Account is added window is present")
                    open_windows += 1
                    self.desktop.find_element_by_name("Done").click()
                
                # Check for Theme popup
                try:
                    logging.info("Checking for Theme popup")
                    self.desktop.find_element_by_xpath('//*[contains(@Name, "Choose a theme")]')
                    self.desktop.find_element_by_name('OK').click()
                    logging.info("Clicked OK on Theme popup.")
                    time.sleep(3)
                except:
                    pass
                else:
                    open_windows += 1

                if open_windows == 0:
                    break
                
            # fail the test if it gets to the end of the last iteration without meeting the conditions to break out
            if x >= max_loops-1:
                logging.error(f"Unable to dismiss all popups in {max_loops} iterations.  Check video or failedscreen.png for something that needs to be manually dismissed.")
                self.fail()
        
        win = WebDriverWait(self.desktop, 120).until(EC.presence_of_element_located((By.CLASS_NAME,'rctrl_renwnd32')))
        self.outlook_driver = self.getDriverFromWin(win)
        # self.outlook_driver.maximize_window()
        # Restore window first to handle the case we accidentally went into Zen mode
        ActionChains(self.desktop).key_down(Keys.ALT).send_keys(" r").key_up(Keys.ALT).perform()
        time.sleep(1)
        # Maximize window
        ActionChains(self.desktop).key_down(Keys.ALT).send_keys(" x").key_up(Keys.ALT).perform()
        time.sleep(2)

        if self.fast_mode == '0':
            try:
                # Dismiss metered connection warning
                warning = self.outlook_driver.find_element_by_name("Connect Anyway")
                warning.click()
                time.sleep(1)
            except:
                pass

            try:
                self.outlook_driver.find_element_by_name("Got it").click()
            except:
                pass

        try:
            # Pin ribbon
            ribbon = self.outlook_driver.find_element_by_name("Ribbon")
            try:
                ribbon.find_element_by_name("Archive...")
                # If successful, then ribbon already pinned.
            except:
                # Do ctrl-F1 to pin ribbon
                ActionChains(self.outlook_driver).key_down(Keys.CONTROL).send_keys(Keys.F1).key_up(Keys.CONTROL).perform()
                time.sleep(2)

        except Exception as e :
            self._page_source(self.outlook_driver)
            raise e

        # Set ribbon to Simplified
        ActionChains(self.outlook_driver).key_down(Keys.ALT).perform()
        time.sleep(0.5)
        ActionChains(self.outlook_driver).key_up(Keys.ALT).perform()
        time.sleep(0.5)
        ActionChains(self.outlook_driver).send_keys("z").perform()
        time.sleep(0.5)
        ActionChains(self.outlook_driver).send_keys("r").perform()
        time.sleep(0.5)
        ActionChains(self.outlook_driver).send_keys("i").perform()
        time.sleep(3)

        ribbon = self.outlook_driver.find_element_by_name("Ribbon")
        ribbon.find_element_by_name("New Email").click()
        time.sleep(3)

        # Maximize new email window
        ActionChains(self.desktop).key_down(Keys.ALT).send_keys(" x").key_up(Keys.ALT).perform()
        time.sleep(2)

        # Discard instead of send
        reply_win = self.desktop.find_element_by_name('Untitled - Message (HTML) ')
        reply_win.find_element_by_name("Ribbon").find_element_by_name("Close").click()
        time.sleep(1)
        reply_win.find_element_by_name("No").click()
        time.sleep(3)


        ##############################
        # OneNote
        ##############################

        # Launch OneNote
        # "To sync this notebook, sign in to OneNote."
        self.launchOrSwitchApp(self.desktop, "OneNote")        
        time.sleep(10)
        
        try:
            logging.info("Checking for 'Start Normally'")
            self.desktop.find_element_by_xpath('//Button[@Name="Start Normally"]').click()
            logging.info("Clicked 'Start Normally', waiting 20s")
            time.sleep(20)
        except:
            pass

        # See if the "Sign in" popup is there.
        try:
            logging.info("Checking for 'Sign In' pop up")
            cutting_onenote = self.desktop.find_element_by_name("Sign In").click()
            time.sleep(5)
            # Check for email prompt
            self.desktop.find_element_by_xpath("//*[contains(@Name, 'Email, phone')]")
            ActionChains(self.desktop).send_keys(self.email_account).send_keys(Keys.ENTER).perform()
            time.sleep(10)
            # check for password prompt
            self.desktop.find_element_by_xpath("//*[contains(@Name, 'assword')]")
            ActionChains(self.desktop).send_keys(self.password).send_keys(Keys.ENTER).perform()
            time.sleep(10)
        except:
            pass

        win = WebDriverWait(self.desktop, 120).until(EC.presence_of_element_located((By.CLASS_NAME,'Framework::CFrame')))
        self.onenote_driver = self.getDriverFromWin(win)
        # self.onenote_driver.implicitly_wait(5)
        time.sleep(3)

        try:
            logging.info("Checking for 'cutting edge' pop up")
            cutting_onenote = self.desktop.find_element_by_name("You're on the cutting edge")
        except:
            pass
        else:
            logging.info("'Cutting edge' window is present")
            cutting_onenote.find_element_by_name("Close").click()
            time.sleep(3)

        # Check for Got it popup
        try:
            logging.info("Checking for Got it")
            self.desktop.find_element_by_name('Got it').click()
            logging.info("Clicked Got it popup.")
            time.sleep(3)
        except:
            pass

        # Check for Your privacy matters popup
        try:
            logging.info("Checking for Privacy matters")
            win = self.desktop.find_element_by_name('Your privacy matters')
            win.find_element_by_name("Close").click()
            time.sleep(3)
        except:
            pass

        # Check for Got it! popup
        try:
            logging.info("Checking for Got it!")
            self.desktop.find_element_by_name('Got it!').click()
            logging.info("Clicked Got it! popup.")
            time.sleep(3)
        except:
            pass

        # Check for Theme popup
        try:
            logging.info("Checking for Theme popup")
            self.desktop.find_element_by_xpath('//*[contains(@Name, "Choose a theme")]')
            self.desktop.find_element_by_name('OK').click()
            logging.info("Clicked OK on Theme popup.")
            time.sleep(3)
        except:
            pass

        # Maximize window
        ActionChains(self.desktop).key_down(Keys.ALT).send_keys(" x").key_up(Keys.ALT).perform()
        time.sleep(2)

        # Pin ribbon
        ribbon = self.onenote_driver.find_element_by_name("Ribbon")
        try:
            ribbon.find_element_by_name("Email Page")
            # If successful, then ribbon already pinned.
        except:
            # Do ctrl-F1 to pin ribbon
            logging.info("Pin ribbon")
            ActionChains(self.onenote_driver).key_down(Keys.CONTROL).send_keys(Keys.F1).key_up(Keys.CONTROL).perform()
            time.sleep(1)

        # Set ribbon to Simplified
        ActionChains(self.onenote_driver).key_down(Keys.ALT).perform()
        time.sleep(0.5)
        ActionChains(self.onenote_driver).key_up(Keys.ALT).perform()
        time.sleep(0.5)
        ActionChains(self.onenote_driver).send_keys("z").perform()
        time.sleep(0.5)
        ActionChains(self.onenote_driver).send_keys("r").perform()
        time.sleep(0.5)
        ActionChains(self.onenote_driver).send_keys("i").perform()

        # Check whether a notebook is already open.
        # The Pages list element exists even when no notebook is open (just empty),
        # so we must confirm it contains at least one ListItem.
        notebook_open = False
        logging.info("Checking to make sure a notebook is open")
        try:
            pages_list = self.onenote_driver.find_element_by_xpath('//List[@Name="Pages"]')
            pages_list.find_element_by_xpath('.//ListItem')
            notebook_open = True
            logging.info("Notebook is already open.")
        except:
            logging.info("Pages list is empty or not found - no notebook open.")

        if not notebook_open:
            opened_prompt = False
            # Try selectors in priority order.
            # "Click here" is the hyperlink OneNote shows in its "no open notebooks" state.
            for selector_type, selector in [
                ("onenote_xpath", '//*[contains(@Name, "Click here")]'),
                ("accessibility_id", "903749698"),  # Legacy UIA id (pre-2026 OneNote).
                ("name", "Open Notebook"),
                ("name", "Open notebook"),
                ("name", "Open"),
            ]:
                try:
                    if selector_type == "onenote_xpath":
                        self.onenote_driver.find_element_by_xpath(selector).click()
                    elif selector_type == "accessibility_id":
                        self.desktop.find_element_by_accessibility_id(selector).click()
                    else:
                        self.desktop.find_element_by_name(selector).click()
                    opened_prompt = True
                    logging.info("Opened OneNote notebook prompt using %s: %s", selector_type, selector)
                    break
                except:
                    pass

            if opened_prompt:
                time.sleep(4)
                logging.info("Opening notebook.")
                # down - Open
                ActionChains(self.onenote_driver).send_keys(Keys.DOWN).perform()
                # pause 5s for list of notebooks to populate
                time.sleep(5)
                # right, down, down - select top notebook
                ActionChains(self.onenote_driver).send_keys(Keys.RIGHT).send_keys(Keys.DOWN).send_keys(Keys.DOWN).perform()
                # enter to open
                ActionChains(self.onenote_driver).send_keys(Keys.ENTER).perform()
                # wait 10s for notebook to load
                time.sleep(25)
            else:
                logging.info("Could not find open-notebook prompt; continuing.")
        logging.info("Notebook is open")

        # Force sync
        ActionChains(self.onenote_driver).key_down(Keys.SHIFT).send_keys(Keys.F9).key_up(Keys.SHIFT).perform()
        logging.info("Waiting 10s for sync.")
        time.sleep(10)
        self.onenote_driver.implicitly_wait(5)

        # Check again for Got it popup that is blocking delete page
        try:
            logging.info("Checking for Got it again")
            self.desktop.find_element_by_name('Got it').click()
            logging.info("Clicked Got it popup.")
            time.sleep(3)
        except:
            pass

        try:
            # Delete existing pages
            while (True):
                pages_list = self.onenote_driver.find_element_by_xpath('//List[@Name="Pages"]')
                try:
                    page = pages_list.find_element_by_xpath("//ListItem")
                except:
                    break
                name = page.get_attribute("Name")
                logging.info("Deleting page " + name)
                page.click()
                time.sleep(1)
                ActionChains(self.onenote_driver).key_down(Keys.CONTROL).key_down(Keys.SHIFT).send_keys("a").key_up(Keys.SHIFT).key_up(Keys.CONTROL).perform()
                time.sleep(1)
                ActionChains(self.onenote_driver).send_keys(Keys.DELETE).perform()
                # page.send_keys(Keys.DELETE)
                time.sleep(2)
                try:
                    self.onenote_driver.find_element_by_name("Cannot Send to Deleted Notes")
                    self.onenote_driver.find_element_by_name("OK").click()
                except:
                    continue

            # Populate default page
            time.sleep(1)
            self.onenote_driver.find_element_by_name("Add Page").click()
            time.sleep(1)
            page = self.onenote_driver.find_element_by_xpath('//ListItem[contains(@Name, "Untitled")]')
            page.click()
            time.sleep(1)
            page.click()

            ActionChains(self.onenote_driver).send_keys("Default Page" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).key_down(Keys.ALT).send_keys("npf").key_up(Keys.ALT).perform()
            time.sleep(2)

            # file_elem = self.onenote_driver.find_element_by_xpath('//Edit[@Name="File name:"]')  # This is not being found reliably even thought he tag is in the source.
            file_elem = self.onenote_driver.find_element_by_accessibility_id("1148")
            time.sleep(3)
            file_elem.click()
            time.sleep(0.5)
            ActionChains(self.onenote_driver).send_keys(self.onedrive_path).perform()
            logging.info("Onedrive Path: " + self.onedrive_path)
            ActionChains(self.onenote_driver).send_keys("Manarola1.png" + Keys.ENTER).perform()
            time.sleep(10)

            try:
                win = WebDriverWait(self.desktop, 120).until(EC.presence_of_element_located((By.CLASS_NAME,'Framework::CFrame')))
                self.onenote_driver = self.getDriverFromWin(win)
            except:
                pass

            ActionChains(self.onenote_driver).send_keys(Keys.ENTER).perform()
            ActionChains(self.onenote_driver).key_down(Keys.CONTROL).send_keys("b").key_up(Keys.CONTROL).perform()
            ActionChains(self.onenote_driver).send_keys("Packing List" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).key_down(Keys.CONTROL).send_keys("b").key_up(Keys.CONTROL).perform()
            ActionChains(self.onenote_driver).key_down(Keys.CONTROL).send_keys("1").key_up(Keys.CONTROL).perform()
            ActionChains(self.onenote_driver).send_keys(Keys.TAB).perform()
            ActionChains(self.onenote_driver).send_keys("D5 2x" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Spare charger" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("50 Prime" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Passport" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Light Box" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Transmitter & receiver" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Gaffer tape" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Lens hood" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Headphones" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Batteries" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Lighting rig" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Models" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Location reservations" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Motorcycles 6x" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Trail jacket 4x" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Radios 10x" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("MB Jeep 2x" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys("Boat 2x" + Keys.ENTER).perform()
            ActionChains(self.onenote_driver).send_keys(Keys.PAGE_UP).perform()

            logging.info("Syncing for 10s.")
            time.sleep(10)

            try:
                # Empty Deleted Pages.  If there aren't any deleted pages, then elements won't be found, just pass.
                self.onenote_driver.find_element_by_name("History").click()
                time.sleep(2)
                self.onenote_driver.find_element_by_name("Notebook Recycle Bin").find_element_by_name("More Options").click()
                time.sleep(1)
                self.onenote_driver.find_element_by_xpath('//MenuItem[@Name="Empty Recycle Bin"]').click()
                time.sleep(0.5)
                self.onenote_driver.find_element_by_xpath('//Button[@Name="Delete"]').click()
                time.sleep(2)

                # Wait for Delete dialog to finish, by checking for presence of Cancel button.
                while(True):
                    try:
                        self.onenote_driver.find_element_by_name("Cancel")
                        logging.info("Waiting 10 more seconds for Delete to finish.")
                        time.sleep(10)
                    except:
                        break
                time.sleep(2)
            except:
                logging.info("Could not empty recycle bin.")
                pass

        except Exception as e :
            self._page_source(self.onenote_driver)
            raise e


        ##############################
        # Word
        ##############################

        # Open a docuemnt in each app to let feature gates update and dismiss popups

        # Launch Word and open long doc
        self.word_driver = self.launchWord(self.desktop)
        time.sleep(3)
        self.recoverUnsavedDocuments(self.word_driver)
        time.sleep(3)
        self.word_driver = self.launchWord(self.desktop)

        try:
            # Open Word doc
            try:
                self.word_driver.find_element_by_name("Open Other Documents").click()
            except:
                self.word_driver.find_element_by_name("Open").click()
            time.sleep(0.5)
            self.word_driver.find_element_by_name("Browse").click()
            time.sleep(0.5)
            file_elem = self.word_driver.find_element_by_xpath('//Edit[@Name="File name:"]')
            file_elem.click()
            time.sleep(0.5)
            file_elem.send_keys(self.onedrive_path)
            file_elem.send_keys(self.word_long_doc)
            time.sleep(0.5)
            self.word_driver.find_element_by_xpath('//SplitButton[@Name="Open"]').click()
            # time.sleep(5)
            # self.word_driver.find_element_by_name("Ribbon").find_element_by_name("Ribbon").find_element_by_name("Close").click()
            time.sleep(5)
        except Exception as e :
            self._page_source(self.word_driver)
            raise e

        ribbon = self.word_driver.find_element_by_name("Ribbon")
        try:
            # If "Ribbon Display Options" is present, then ribbon is visible
            ribbon.find_element_by_name("Ribbon Display Options")
        except:
            # If not, send ctrl-F1 to pin it.
            ribbon.send_keys(Keys.CONTROL + Keys.F1)
            time.sleep(2)


        ##############################
        # Excel
        ##############################

        # Launch Excel
        self.excel_driver = self.launchExcel(self.desktop)
        time.sleep(8)

        try:
            logging.info("Checking for Privacy Settings Applied")
            win = self.desktop.find_element_by_name('Privacy Settings Applied')
            win.find_element_by_name("OK").click()
        except:
            pass

        time.sleep(1)
        self.recoverUnsavedDocuments(self.excel_driver)
        time.sleep(3)
        self.excel_driver = self.launchExcel(self.desktop)

        try:
            # Open Excel doc
            try:
                self.excel_driver.find_element_by_name("Open Other Workbooks").click()
            except:
                self.excel_driver.find_element_by_name("File").find_element_by_name("Open").click()
            time.sleep(0.5)
            self.excel_driver.find_element_by_name("Browse").click()
            time.sleep(0.5)
            file_elem = self.excel_driver.find_element_by_xpath('//Edit[@Name="File name:"]')
            file_elem.click()
            time.sleep(0.5)
            file_elem.send_keys(self.onedrive_path)
            file_elem.send_keys(self.excel_doc)
            time.sleep(0.5)
            self.excel_driver.find_element_by_xpath('//SplitButton[@Name="Open"]').click()
            # time.sleep(5)
            # self.excel_driver.find_element_by_name("Ribbon").find_element_by_name("Ribbon").find_element_by_name("Close").click()
            time.sleep(5)
        except Exception as e :
            self._page_source(self.excel_driver)
            raise e

        ribbon = self.excel_driver.find_element_by_name("Ribbon")
        try:
            # If "Ribbon Display Options" is present, then ribbon is visible
            ribbon.find_element_by_name("Ribbon Display Options")
        except:
            # If not, send ctrl-F1 to pin it.
            ribbon.send_keys(Keys.CONTROL + Keys.F1)
            time.sleep(2)

        try:
            # Click Insert button on ribbon to initiate plugin download
            ribbon.find_element_by_name("Home").click()
            time.sleep(1)

            ribbon.find_element_by_name("Insert").click()
            time.sleep(5)
        except Exception as e :
            self._page_source(self.excel_driver)
            raise e


        ##############################
        # PowerPoint
        ##############################

        # Launch PowerPoint
        self.ppt_driver = self.launchPowerPoint(self.desktop)
        time.sleep(3)
        self.recoverUnsavedDocuments(self.ppt_driver)
        time.sleep(3)
        self.ppt_driver = self.launchPowerPoint(self.desktop)

        try:
            # Open PowerPoint doc
            try:
                self.ppt_driver.find_element_by_name("Open Other Presentations").click()
            except:
                self.ppt_driver.find_element_by_name("Open").click()
            time.sleep(0.5)
            self.ppt_driver.find_element_by_name("Browse").click()
            time.sleep(0.5)
            file_elem = self.ppt_driver.find_element_by_xpath('//Edit[@Name="File name:"]')
            file_elem.click()
            time.sleep(0.5)
            file_elem.send_keys(self.onedrive_path)
            file_elem.send_keys(self.ppt_doc)
            time.sleep(0.5)
            self.ppt_driver.find_element_by_xpath('//SplitButton[@Name="Open"]').click()
            # time.sleep(5)
            # self.ppt_driver.find_element_by_name("Ribbon").find_element_by_name("Ribbon").find_element_by_name("Close").click()
            time.sleep(2)
        except Exception as e :
            self._page_source(self.ppt_driver)
            raise e

        ribbon = self.ppt_driver.find_element_by_name("Ribbon")
        try:
            # If "Ribbon Display Options" is present, then ribbon is visible
            ribbon.find_element_by_name("Ribbon Display Options")
        except:
            # If not, send ctrl-F1 to pin it.
            ribbon.send_keys(Keys.CONTROL + Keys.F1)
            time.sleep(2)


        self.launchOrSwitchApp(self.desktop, "Outlook")
        # time.sleep(10)

        # # Switch back to inbox.  This helps update the status, which sometimes gets stuck.
        # logging.info("Switching to inbox.")
        # time.sleep(2)
        # ActionChains(self.outlook_driver).key_down(Keys.CONTROL).send_keys("y").key_up(Keys.CONTROL).perform()        
        # time.sleep(2)
        # ActionChains(self.outlook_driver).send_keys("inbox").perform()
        # time.sleep(2)
        # ActionChains(self.outlook_driver).send_keys(Keys.ENTER).perform()
        # time.sleep(5)

        # try:
        #     logging.info("Outlook - Checking for online mode")
        #     self.outlook_driver.find_element_by_name("Connectivity to your server. Online with: Microsoft Exchange")
        #     logging.info("All folders are up to date")
        # except:
        #     try:
        #         logging.info("Outlook - Waiting for all folders to be up to date...")
        #         #self.outlook_driver.implicitly_wait(0)
        #         WebDriverWait(self.outlook_driver, 1200).until(EC.presence_of_element_located((By.NAME, 'Progress All folders are up to date.')))
        #         logging.info("All folders are up to date")
        #     except Exception as e :
        #         self._page_source(self.outlook_driver)
        #         raise e
        
        self.success = True

    def tearDown(self):
        logging.info("Performing teardown.")
        # Close all apps
        try:
            if self.word_driver:
                time.sleep(2)
                self.launchOrSwitchApp(self.desktop, "Word")
                try:
                    self.word_driver.find_element_by_name("Got it").click()
                except:
                    pass
                self.word_driver.find_element_by_name("Ribbon").find_element_by_name("Close").click()
        except:
            logging.error("Unable to close Word.")
            pass

        try:
            if self.excel_driver:
                time.sleep(2)
                self.launchOrSwitchApp(self.desktop, "Excel")
                try:
                    self.excel_driver.find_element_by_name("Got it").click()
                except:
                    pass
                self.excel_driver.find_element_by_name("Ribbon").find_element_by_name("Close").click()
        except:
            logging.error("Unable to close Excel.")
            pass

        try:
            if self.ppt_driver:
                time.sleep(2)
                self.launchOrSwitchApp(self.desktop, "PowerPoint")
                try:
                    self.ppt_driver.find_element_by_name("Got it").click()
                except:
                    pass
                self.ppt_driver.find_element_by_name("Ribbon").find_element_by_name("Close").click()
        except:
            logging.error("Unable to close PowerPoint.")
            pass
        
        try:
            if self.onenote_driver:
                time.sleep(2)
                self.launchOrSwitchApp(self.desktop, "OneNote")
                self.onenote_driver.find_element_by_name("Ribbon").find_element_by_name("Close").click()
        except:
            logging.error("Unable to close OneNote.")
            pass

        try:
            if self.outlook_driver:
                time.sleep(2)
                self.outlook_driver.implicitly_wait(5)
                self.launchOrSwitchApp(self.desktop, "Outlook")
                try:
                    self.outlook_driver.find_element_by_name("Got it").click()
                except:
                    pass
                try:
                    self._page_source(self.desktop)
                except:
                    pass
                self.outlook_driver.find_element_by_name("Ribbon").find_element_by_name("Close").click()
                time.sleep(2)
        except:
            logging.error("Unable to close Outlook.")
            pass

        core.app_scenario.Scenario.tearDown(self)
        self._call(["taskkill.exe", "/F /IM WinAppDriver.exe"])

        # try:
        #     # Upload outlook_rule for deleting new emails.
        #     self._upload("utilities\\outlook_rule.ps1", self.dut_exec_path)
        #     cmd = '-ExecutionPolicy Unrestricted -Command "' + os.path.join(self.dut_exec_path, "outlook_rule.ps1") + '"'
        #     self._call(["powershell.exe", cmd], timeout=60)
        #     time.sleep(10) # give time for Outlook to close gracefully
        # except:
        #     logging.warning("Could not install Outlook rule to delete incoming email.")
        #     pass

        if self.success:
            self.createPrepStatusControlFile()


    def slow_send_keys(self, keys):
        for key in keys:
            ActionChains(self.desktop).send_keys(key).perform()

    def launchWord(self, desktop_driver):
        self.launchOrSwitchApp(desktop_driver, "Word")
        win = WebDriverWait(desktop_driver, 40).until(EC.presence_of_element_located((By.CLASS_NAME,'OpusApp')))
        word_driver = self.getDriverFromWin(win)
        word_driver.implicitly_wait(2)
        try:
            # Dismiss any popups
            dialog = word_driver.find_element_by_class_name("NUIDialog")
            dialog.find_element_by_name("Close").click()
            time.sleep(1)
        except:
            pass
        word_driver.maximize_window()
        return word_driver

    def launchExcel(self, desktop_driver):
        self.launchOrSwitchApp(desktop_driver, "Excel")
        win = WebDriverWait(desktop_driver, 40).until(EC.presence_of_element_located((By.CLASS_NAME,'XLMAIN')))
        excel_driver = self.getDriverFromWin(win)
        excel_driver.implicitly_wait(2)
        try:
            # Dismiss any popups
            dialog = excel_driver.find_element_by_class_name("NUIDialog")
            dialog.find_element_by_name("Close").click()
            time.sleep(1)
        except:
            pass
        excel_driver.maximize_window()
        return excel_driver

    def launchPowerPoint(self, desktop_driver):
        self.launchOrSwitchApp(desktop_driver, "PowerPoint")
        win = WebDriverWait(desktop_driver, 40).until(EC.presence_of_element_located((By.CLASS_NAME,'PPTFrameClass')))
        ppt_driver = self.getDriverFromWin(win)
        ppt_driver.implicitly_wait(2)
        try:
            # Dismiss any popups
            dialog = ppt_driver.find_element_by_class_name("NUIDialog")
            dialog.find_element_by_name("Close").click()
            time.sleep(1)
        except:
            pass
        ppt_driver.maximize_window()
        return ppt_driver

    def recoverUnsavedDocuments(self, app_driver):
        try:
            app_driver.find_element_by_xpath('//*[contains(@Name, "Blank")]')
        except:
            try:
                app_driver.find_element_by_name("Collapsible Group").click()
            except:
                app_driver.find_element_by_name("Hide or show region").click()
        time.sleep(1)
        app_driver.find_element_by_xpath('//*[contains(@Name, "Blank")]').click()
        time.sleep(1)
        app_driver.find_element_by_name("File Tab").click()
        time.sleep(1)
        app_driver.find_element_by_name("Info").click()
        time.sleep(3)
        app_driver.find_elements_by_xpath('//*[contains(@Name, "Manage")]')[1].click()
        time.sleep(1)
        try:
            app_driver.find_element_by_xpath('//*[contains(@Name, "Delete All Unsaved")]').click()
            time.sleep(1)
            app_driver.find_element_by_name("Yes").click()
            time.sleep(1)
        except:
            pass
        # self._page_source(app_driver)
        app_driver.find_element_by_class_name("NetUIFullpageUIWindow").find_element_by_name("Close").click()
        time.sleep(1)
        try:
            app_driver.find_element_by_xpath('//Button[contains(@Name, "OK")]').click()
        except:
            pass

    def launchOrSwitchApp(self, driver, app):
        # app argument should be one of: Outlook, Word, Excel, PowerPoint, OneNote
        logging.info("Launching " + app)
        self._get_start_button(driver).click()
        time.sleep(1.5)

        apps_elem = self._get_app_tray(driver)

        app_button = None
        try:
            # Try finding by Name via XPath
            app_button = apps_elem.find_element_by_xpath(f'//Button[contains(@Name,"{app}")]')
        except:
            # If not found, try fallback to accessibility ID
            app_cmd = app.upper()
            if app == "Word":
                app_cmd = "WINWORD"
            elif app == "PowerPoint":
                app_cmd = "POWERPNT"
            elif app == "Outlook":
                app_cmd = "OUTLOOK"
            app_cmd += ".EXE"
            # Try both known accessibility ID formats
            try:
                app_button = apps_elem.find_element_by_accessibility_id(f"Appid: Microsoft.Office.{app_cmd}.15")
            except:
                try:
                    app_button = apps_elem.find_element_by_accessibility_id(f"Microsoft.Office.{app_cmd}.15")
                except:
                    logging.error(f"Could not locate taskbar icon for {app}")
        app_button.click()

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
        time.sleep(2)  
        driver.switch_to_window(win_handle)
        # driver.maximize_window()
        return driver

    def kill(self):
        self._call([(self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"), (self.dut_resolved_ip + " " + self.app_port + " /forcequit")], blocking=False)
        time.sleep(1)

        desired_caps = {}
        desired_caps["app"] = "Root"
        desktop_driver = self._launchApp(desired_caps)

        result = self._call(["tasklist.exe", '/fi "imagename eq outlook.exe"'])
        if "No tasks are running" not in result:
            try:
                self.outlook_driver = self.getDriverFromWin(WebDriverWait(desktop_driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME,'rctrl_renwnd32'))))
                self.outlook_driver.maximize_window()
                self.outlook_driver.find_element_by_name("Close").click()
            except:
                pass

        result = self._call(["tasklist.exe", '/fi "imagename eq onenote.exe"'])
        if "No tasks are running" not in result:
            try:
                self.onenote_driver = self.getDriverFromWin(WebDriverWait(desktop_driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME,'Framework::CFrame'))))
                self.onenote_driver.maximize_window()
                self.onenote_driver.find_element_by_class_name("NetUIFullpageUIWindow").find_element_by_name("Close").click()
            except:
                pass

        result = self._call(["tasklist.exe", '/fi "imagename eq WINWORD.exe"'])
        if "No tasks are running" not in result:
            try:
                word_driver = self.getDriverFromWin(WebDriverWait(desktop_driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME,'OpusApp'))))
                word_driver.maximize_window()
                word_driver.find_element_by_class_name("NetUIFullpageUIWindow").find_element_by_name("Close").click()
                try:
                    word_driver.find_element_by_name("Don't Save").click()
                except:
                    pass
            except:
                pass
        
        result = self._call(["tasklist.exe", '/fi "imagename eq EXCEL.exe"'])
        if "No tasks are running" not in result:
            try:
                excel_driver = self.getDriverFromWin(WebDriverWait(desktop_driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME,'XLMAIN'))))
                excel_driver.maximize_window()
                excel_driver.find_element_by_class_name("NetUIFullpageUIWindow").find_element_by_name("Close").click()
                try:
                    excel_driver.find_element_by_name("Don't Save").click()
                except:
                    pass
            except:
                pass

        result = self._call(["tasklist.exe", '/fi "imagename eq POWERPNT.exe"'])
        if "No tasks are running" not in result:
            try:
                powerpoint_driver = self.getDriverFromWin(WebDriverWait(desktop_driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME,'PPTFrameClass'))))
                powerpoint_driver.maximize_window()
                powerpoint_driver.find_element_by_class_name("NetUIFullpageUIWindow").find_element_by_name("Close").click()
                try:
                    powerpoint_driver.find_element_by_name("Don't Save").click()
                except:
                    pass
            except:
                pass

        try:
            logging.debug("Killing Outlook.exe OneNote.exe Excel.exe Powerpnt.exe Winword.exe WinAppDriver.exe")
            self._kill("Outlook.exe OneNote.exe Excel.exe Powerpnt.exe Winword.exe WinAppDriver.exe")
        except:
            pass