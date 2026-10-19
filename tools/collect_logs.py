# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from core.app_scenario import Scenario
import logging
import sys
import os


class Tool(Scenario):
    '''
    Collect various system logs in the case of scenario failure.

    Will collect various logs such as sleep study reports, battery reports, system event logs, and power shell logs.
    '''
    module = __module__.split('.')[-1]
    # Set default parameters


    def initCallback(self, scenario):
        # Initialization code
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        self.scenario_failed = False
        self.output_path = self.scenario.dut_data_path + f"\\{self.module}"
        logging.debug("initCallback(self, scenario): self.scenario_failed set to: " + str(self.scenario_failed))

    def testBeginCallback(self):
        pass
    
    def testEndCallback(self):
        self._call(["cmd.exe", '/c if not exist "' + self.output_path + '" mkdir "' + self.output_path + '"']) # Make dir for output from collect logs

        logging.debug("testEndCallback(self): self.scenario_failed set to: " + str(self.scenario_failed))
        if not self.scenario_failed:
            return

        # cmd = "(Get-Date) - (New-TimeSpan -Day 3)"
        # self._call(["powershell.exe", "Get-WinEvent | Where-Object { $_.TimeCreated -ge " + cmd + " } | Out-File -FilePath " + self.dut_data_path + "\\event_log"])

        # Sleepstudy failes when using powershell on ARM devices.  Using CMD instead.
        # self._call(["powershell.exe", "powercfg.exe /SLEEPSTUDY /VERBOSE /DURATION 14 /OUTPUT " + self.dut_data_path + "\\sleepstudy.xml /XML"])
        # self._call(["powershell.exe", "powercfg.exe /BATTERYREPORT /DURATION 14 /OUTPUT " + self.dut_data_path + "\\batteryreport.xml /XML"])
        # self._call(["cmd.exe", "/C powercfg.exe /SLEEPSTUDY /VERBOSE /DURATION 5 /OUTPUT " + self.dut_data_path + "\\sleepstudy.xml /XML"], blocking = False)
        # self._call(["cmd.exe", "/C powercfg.exe /BATTERYREPORT /DURATION 5 /OUTPUT " + self.dut_data_path + "\\batteryreport.xml /XML"], blocking = False)
        # self._call(["cmd.exe", "/C powercfg.exe /SLEEPSTUDY /VERBOSE /DURATION 5 /OUTPUT " + self.dut_data_path + "\\sleepstudy.html"], blocking = False)
        # self._call(["cmd.exe", "/C powercfg.exe /BATTERYREPORT /DURATION 5 /OUTPUT " + self.dut_data_path + "\\batteryreport.html"], blocking = False)
        self._call(["cmd.exe", "/C powercfg.exe /SLEEPSTUDY /VERBOSE /DURATION 5 /OUTPUT " + self.output_path + "\\sleepstudy_verbose.xml /XML"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C powercfg.exe /BATTERYREPORT /DURATION 5 /OUTPUT " + self.output_path + "\\batteryreport.xml /XML"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C powercfg.exe /SLEEPSTUDY /VERBOSE /DURATION 5 /OUTPUT " + self.output_path + "\\sleepstudy_verbose.html"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C powercfg.exe /BATTERYREPORT /DURATION 5 /OUTPUT " + self.output_path + "\\batteryreport.html"], blocking = True, fail_on_exception=False, expected_exit_code="")
        
        self._call(["cmd.exe", "/C xcopy C:\\Windows\\Minidump\\*.* " + self.output_path], expected_exit_code="")
        
        self._call(["cmd.exe", "/C netsh wlan sh wlanreport duration=\"14\""], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C xcopy C:\\ProgramData\\Microsoft\\Windows\\WlanReport\\wlan-report-latest.html " + self.output_path], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C netsh wlan sh i >> " + self.output_path + "\\wlan_status.txt"], blocking = True, fail_on_exception=False, expected_exit_code="")
        logging.debug("Gathering system event logs")
        self._call(["cmd.exe", "/C wevtutil epl System " + self.output_path + "\\System_Event_Log.evtx"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C wevtutil epl Application " + self.output_path + "\\Application_Event_Log.evtx"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C wevtutil epl HardwareEvents " + self.output_path + "\\HardwareEvents_Event_Log.evtx"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C wevtutil epl OAlerts " + self.output_path + "\\Office_Alerts_Event_Log.evtx"], blocking = True, fail_on_exception=False, expected_exit_code="")
        logging.debug("Getting system Powershell logs")
        self._call(["cmd.exe", "/C wevtutil epl \"Windows Powershell\" " + self.output_path + "\\Windows_Powershell.evtx"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C wevtutil epl \"Microsoft-Windows-WLAN-AutoConfig/Operational\" " + self.output_path + "\\Microsoft-Windows-WLAN-AutoConfig-Operational.evtx"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C wevtutil epl \"Microsoft-Windows-WWAN-CFE/Diagnostic\" " + self.output_path + "\\Microsoft-Windows-WWAN-CFE-Diagnostic.evtx"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C wevtutil epl \"Microsoft-Windows-WWAN-MM-Events/Diagnostic\" " + self.output_path + "\\Microsoft-Windows-WWAN-MM-Events-Diagnostic.evtx"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C wevtutil epl \"Microsoft-Windows-WWAN-MediaManager/Diagnostic\" " + self.output_path + "\\Microsoft-Windows-WWAN-MediaManager-Diagnostic.evtx"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C wevtutil epl \"Microsoft-Windows-WWAN-NDISUIO-EVENTS/Diagnostic\" " + self.output_path + "\\Microsoft-Windows-WWAN-NDISUIO-EVENTS-Diagnostic.evtx"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C wevtutil epl \"Microsoft-Windows-WWAN-SVC-Events/Diagnostic\" " + self.output_path + "\\Microsoft-Windows-WWAN-SVC-Events-Diagnostic.evtx"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C wevtutil epl \"Microsoft-Windows-WWAN-SVC-Events/Operational\" " + self.output_path + "\\Microsoft-Windows-WWAN-SVC-Events-Operational.evtx"], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C xcopy C:\\Windows\\System32\\LogFiles\\WMI\\Wifi.etl " + self.output_path], blocking = True, fail_on_exception=False, expected_exit_code="")
        self._call(["cmd.exe", "/C bcdedit >> " + self.output_path + "\\bcdedit.txt"], blocking = True, fail_on_exception=False, expected_exit_code="")


    def dataReadyCallback(self):
        # You can do any post processing of data here.
        pass

    def testScenarioFailed(self):
        self.scenario_failed = True
        logging.debug("testScenarioFailed(self): self.scenario_failed set to " + str(self.scenario_failed))