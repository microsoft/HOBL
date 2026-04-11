# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Prep a DUT before testing
#   
##

from core.parameters import Params
import core.app_scenario
import logging
import os
import time
import threading

class SystemPrep(core.app_scenario.Scenario):
    '''
    Preforms various tasks that prepare a device for testing.
    '''
    module = __module__.split('.')[-1]
    Params.setDefault(module, "hibernate_enabled", "1", desc="Enables or disables hibernation on the device", valOptions=["0", "1"])
    Params.setDefault(module, "telemetry_enabled", "0", desc="Enables or disables the gathering of optional diagnostic data in the OS", valOptions=["0", "1"])
    # Params.setDefault(module, "hdr_enabled", "", desc="Enables or disables HDR on the device (if supported by the device)", valOptions=["0", "1"])
    Params.setDefault(module, "theme", "current", desc="Change the Windows theme", valOptions=["current", "light", "dark"])
    Params.setDefault(module, 'wallpaper', 'ColorChecker3000x2000.png', desc="Sets the device's background image.  Uses image files stored in the %SYSTEMDRIVE%\hobl_bin\DesktopImages folder")
    Params.setDefault(module, 'final_reboot', '1', desc="Sets if the device will reboot at the conclusion of daily_prep", valOptions=["0", "1"])
    Params.setDefault(module, 'bpm_pcc_blm_disable', '0', desc="Disable BPM, PCC, and BLM", valOptions=["0", "1"])

    wallpaper = Params.get(module, 'wallpaper')

    hibernate_enabled = int(Params.get(module, 'hibernate_enabled'))
    telemetry_enabled = Params.get(module, 'telemetry_enabled')
    # hdr_enabled = Params.get(module, 'hdr_enabled')
    theme = Params.get(module, 'theme')
    dut_architecture = Params.get('global', 'dut_architecture')
    final_reboot = Params.get(module, 'final_reboot')
    bpm_pcc_blm_disable = Params.get(module, 'bpm_pcc_blm_disable') == '1'
    reboot_complete = False

    # Params.setOverride("global", "collection_enabled", "0")
    Params.setOverride("global", "prep_tools", "")
    is_prep = True


    def runTest(self):
        #logging.info("Setup")
        self._upload("utilities\\open_source\\system_prep.ps1", self.dut_exec_path)
        #logging.info("Initial Thread timeout - " + str(self.timeout / 60) + " min.")
        self._call(["powershell.exe", 'set-executionpolicy unrestricted -Force'], expected_exit_code="", fail_on_exception=False)

        # Enable/Disable HDR if specified
        # if self.hdr_enabled == "1":
        #     self._call(["cmd.exe", '/C reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers\\MonitorDataStore\\SHP1577352326049_24_07E6_69" /v HDREnabled /t REG_DWORD /d 1 /f > null 2>&1'])
        # if self.hdr_enabled == "0":
        #     self._call(["cmd.exe", '/C reg add "HKLM\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers\\MonitorDataStore\\SHP1577352326049_24_07E6_69" /v HDREnabled /t REG_DWORD /d 0 /f > null 2>&1'])
        
        # Enable/Disable dark theme if specified
        if self.theme == "dark":
            self._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v SystemUsesLightTheme /t REG_DWORD /d 0 /f > null 2>&1'])
            self._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v AppsUseLightTheme /t REG_DWORD /d 0 /f > null 2>&1'])
        if self.theme == "light":
            self._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v SystemUsesLightTheme /t REG_DWORD /d 1 /f > null 2>&1'])
            self._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v AppsUseLightTheme /t REG_DWORD /d 1 /f > null 2>&1'])

        # Enable file extensions in File Explorer, just for ease fo use.
        self._call(["cmd.exe", '/C reg add "HKCU\\software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" /v HideFileExt /t REG_DWORD /d 00000000 /f > null 2>&1'])
        # Disable certain notifications that can interfere with execution:
        #    Suggest ways I can finish setting up my device to get the most out of Windows
        #    Get tips, tricks, and suggestions as you use Windows
        #    Show me the Winodws welcome experience after updates and occasionally when I sign in to highlight what's new and suggested
        #    Toast notifications
        self._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\UserProfileEngagement" /v ScoobeSystemSettingEnabled /t REG_DWORD /d 0 /f > null 2>&1'])
        self._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" /v SubscribedContent-338389Enabled /t REG_DWORD /d 0 /f > null 2>&1'])
        self._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" /v SubscribedContent-310093Enabled /t REG_DWORD /d 0 /f > null 2>&1'])
        # This seems to require a reboot to take effect.  Hobl_prep and abl_prep plans should accomodate this.
        self._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\PushNotifications" /v ToastEnabled /t REG_DWORD /d 0 /f > null 2>&1'])

        # Align taskbar icons to the left, so that as tasks come and go the pinned icons don't change their position
        self._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" /v TaskbarAl /t REG_DWORD /d 0 /f > null 2>&1'])
        # Disable expandable taskbar
        self._call(["cmd.exe", '/C reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" /v ExpandableTaskbar /t REG_DWORD /d 0 /f > null 2>&1'])
        # Disable Recall Popup
        self._call(["cmd.exe", '/C reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\CloudExperienceHost\Intent\RecallNotice" /v RecallConsentPageShown /t REG_DWORD /d 1 /f > null 2>&1'])


        # Upload policy editor
        system_path = "System32"
        # if self.dut_architecture == "arm64":
        #     system_path = "Sysnative"
        self._upload("utilities\\third_party\\PolicyFileEditor", "C:\\Program Files\\WindowsPowerShell\\Modules")
        self._upload("utilities\\third_party\\PolicyFileEditor", "C:\\Program Files (x86)\\WindowsPowerShell\\Modules")

        try:
            smonitor_exe = "c:\\tools\\SMonitor\\SMonitorUAP.exe"

            # Disable PCC to prevent being limited to 80% charge
            self._call([smonitor_exe, "/battpccenable 1 0"], fail_on_exception=False, log_output=False, expected_exit_code="")

            if self.bpm_pcc_blm_disable:
                self._call([smonitor_exe, "/clearbpmstatus 1"],   fail_on_exception=False, log_output=False, expected_exit_code="")
                self._call([smonitor_exe, "/battbpmdisable 0 1"], fail_on_exception=False, log_output=False, expected_exit_code="")
                self._call([smonitor_exe, "/battpccenable 0 0"],  fail_on_exception=False, log_output=False, expected_exit_code="")
                self._call([smonitor_exe, "/battblmdisable 1"],   fail_on_exception=False, log_output=False, expected_exit_code="")
        except:
            logging.warning("SMonitor call failed")

        # Set Edge to always play videos
        self._call(["powershell.exe", 'Set-PolicyFileEntry -Path "$env:windir\\' + system_path + '\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Edge -ValueName AutoplayAllowed -Data 1 -Type DWord'])
        result = self._call(["powershell.exe", 'Get-PolicyFileEntry -Path "$env:windir\\' + system_path + '\\GroupPolicy\\Machine\\registry.pol" -All'])
        if "AutoplayAllowed" not in result:
            raise Exception
        self._call(["cmd.exe", '/C gpupdate /wait:1200'])

        if self.telemetry_enabled == "1":
            # Enable telemetry collected by Microsoft servers
            self._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\SQMClient" /v IsTestlab /t REG_DWORD /d 0 /f > null 2>&1'])
            
            # self._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Diagnostics\\DiagTrack" /v ShowedToastAtLevel /t REG_DWORD /d 3 /f > null 2>&1'])
            self._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 3 /f > null 2>&1'])
            self._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" /v MaxTelemetryAllowed /t REG_DWORD /d 3 /f > null 2>&1'])

            self._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 3 /f > null 2>&1'])
            self._call(["powershell.exe", 'Set-PolicyFileEntry -Path "$env:windir\\' + system_path + '\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection -ValueName AllowTelemetry -Data 3 -Type DWord'])
            result = self._call(["powershell.exe", 'Get-PolicyFileEntry -Path "$env:windir\\' + system_path + '\\GroupPolicy\\Machine\\registry.pol" -All'])
            if "AllowTelemetry" not in result:
                raise Exception
            self._call(["cmd.exe", '/C gpupdate /wait:1200'])

        else:
            self._upload("utilities\\open_source\\telemetry.ASM-WindowsDefault.json", self.dut_exec_path)
            self._upload("utilities\\open_source\\utc.app.json", self.dut_exec_path)
            self._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Diagnostics\\DiagTrack\\TestHooks" /v SkipTelemetryServiceRules /t REG_DWORD /d 1 /f > null 2>&1'])   
            self._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Diagnostics\\DiagTrack\\TestHooks" /v SkipDownloadedSettings /t REG_DWORD /d 1 /f > null 2>&1'])   


        if self.hibernate_enabled == 1:
            self._call(["cmd.exe", "/C powercfg.exe /H ON"])
        else:
            # disable hybernate
            self._call(["cmd.exe", "/C powercfg.exe /H OFF"])
            # disable adaptive hibernate
            self._call(["cmd.exe", "/C powercfg.exe /setdcvalueindex scheme_current sub_presence STANDBYRESERVETIME 0"])
            self._call(["cmd.exe", "/C powercfg.exe /setdcvalueindex scheme_current sub_presence STANDBYRESETPERCENT 0"])
            self._call(["cmd.exe", "/C powercfg.exe /setdcvalueindex scheme_current sub_presence NSENINPUTPRETIME 0"])
            self._call(["cmd.exe", "/C powercfg.exe /setdcvalueindex scheme_current sub_presence NSENINPUTPRETIME 0"])
            self._call(["cmd.exe", "/C powercfg.exe /setdcvalueindex scheme_current sub_presence STANDBYBUDGETGRACEPERIOD 0"])
            self._call(["cmd.exe", "/C powercfg.exe /setdcvalueindex scheme_current sub_presence USERPRESENCEPREDICTION 0"])
            self._call(["cmd.exe", "/C powercfg.exe /setdcvalueindex scheme_current sub_presence standbybudgetpercent 0"])
            self._call(["cmd.exe", "/C powercfg.exe /setdcvalueindex scheme_current sub_presence STANDBYRESERVEGRACEPERIOD 0"])

        self._call(["powershell.exe", os.path.join(self.dut_exec_path,"system_prep.ps1") + " -wallpaper " + self.wallpaper + " -telemetry_enabled " + self.telemetry_enabled])

        self.syncClock()
        if self.final_reboot == "1":
            logging.info("Final reboot")
            self._dut_reboot()
        logging.info("system_prep complete")

    def syncClock(self):
        # Ensure DUT and host clocks are synced
        logging.info("Enabling auto time zone")
        self._call(["cmd.exe", '/C reg add "HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\tzautoupdate" /v Start /t REG_DWORD /d 00000003 /f > null 2>&1'])
        logging.info("Checking for clock sync")
        resync_attempts = 0
        while resync_attempts < 3:
            dut_time = int(self._call(["powershell.exe", '[int][double]::Parse((Get-Date (get-date).touniversaltime() -UFormat %s))']))
            host_time = int(time.time())
            if abs(dut_time - host_time) < 4:
                logging.info("DUT clock is within 3 seconds of host")
                break
            else:
                resync_attempts += 1
                logging.info("DUT clock is off by " + str(abs(dut_time - host_time)) + " seconds, syncing")
                # Set registry keys to automatically update time and time zone, start time service and force resync
                self._call(["cmd.exe", '/C reg add "HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\W32Time\\Parameters" /v Type /t REG_SZ /d NTP /f > null 2>&1'])
                # self._call(["cmd.exe", '/C reg add "HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\tzautoupdate" /v Start /t REG_DWORD /d 00000003 /f > null 2>&1'])
                self._call(["cmd.exe", '/C net start w32time'], expected_exit_code="")
                time.sleep(1)
                self._call(["cmd.exe", '/C w32tm /resync'], expected_exit_code="") # /nowait flag doesn't work
                time.sleep(2)
                self._call(["cmd.exe", '/C net stop w32time'], expected_exit_code="")
        else:
            logging.info("Unable to sync clocks")
            self.fail()

    def tearDown(self):
        # Set polling rate for Surface power monitor chips (after all reboots have happened)
        self._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SRUM\\Parameters" /v Tier1Period /t REG_DWORD /d 30 /f > null 2>&1'])   
        self._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SRUM\\Parameters" /v Tier2Period /t REG_DWORD /d 120 /f > null 2>&1'])   
        self._call(["cmd.exe", '/C reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\intelpep\\Parameters" /v ActiveAccountingIntervalInMs /t REG_DWORD /d 0x2710 /f > null 2>&1'])   

        self.createPrepStatusControlFile()
        core.app_scenario.Scenario.tearDown(self)
       