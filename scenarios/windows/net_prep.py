# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Set Local Group Policy to disable windows update
#   
##

import builtins
import os
import logging
import core.app_scenario
from core.parameters import Params
import shutil

class NetPrep(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]

    # Override collection of config data, traces, and execution of callbacks 
    # Params.setOverride('global', 'collection_enabled', '0')
    Params.setOverride('global', 'prep_tools', '')

    # Set default parameters
    Params.setDefault(module, 'connection', 'Wi-Fi')  # Wi-Fi, Cellular, or Ethernet

    # Get parameters
    connection = Params.get(module, 'connection')
    host_ip = Params.get('global', 'host_ip')
    dut_architecture = Params.get('global', 'dut_architecture')
    local_execution = Params.get('global', 'local_execution')
    is_prep = True

    def runTest(self):

        # cmd logic:
        #       Local       Remote
        # x64   sysnative   cmd (sysnative for local execution because 32b Python on 64b OS)
        # arm64 sysnative   cmd (cmd is a 64b program on ARM)
        #
        # system path logic:
        #       Local       Remote
        # x64   sysnative   system32
        # arm64 sysnative   sysnative (because powerhsell is 32b program on 64b OS)

        system_path = "System32"
        cmd = "cmd.exe"

        # Set route priorities
        if self.connection.lower() == "wi-fi":
            # See if connection minimize policy is already 0, to save us from having to set it.
            try:
                logging.info("Checking if connection minimize policy is already set to 1.")
                response = self._call(["powershell.exe", '(Get-PolicyFileEntry -Path "$env:windir\\' + system_path + '\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Windows\\WcmSvc\\GroupPolicy -ValueName fMinimizeConnections).Data'])
            except:
                response = "0" # fail
            if (response != "1"):
                logging.info("Uploading PolicyFileEditor.")

                self._upload("utilities\\third_party\\PolicyFileEditor", "C:\\Program Files\\WindowsPowerShell\\Modules")
                self._upload("utilities\\third_party\\PolicyFileEditor", "C:\\Program Files (x86)\\WindowsPowerShell\\Modules")

                # Set MinimizeConnections policy to 0, so that Wi=Fi and Cellular can be active at same time
                logging.debug("Setting MinimizeConnections policy to 1.")
                self._call(["powershell.exe", 'set-executionpolicy unrestricted -Force'])
                self._call(["powershell.exe", 'Set-PolicyFileEntry -Path "$env:windir\\' + system_path + '\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Windows\\WcmSvc\\GroupPolicy -ValueName fMinimizeConnections -Data 1 -Type DWord'])
                self._call(["powershell.exe", 'Get-PolicyFileEntry -Path "$env:windir\\' + system_path + '\\GroupPolicy\\Machine\\registry.pol" -All'])
                self._call([cmd, '/C gpupdate'])

            # Add route to host
            logging.info("Setting route to host for Wi-Fi.")
            self._call(["powershell.exe", 'New-NetRoute -DestinationPrefix "' + self.host_ip + '/32" -InterfaceAlias "Wi-Fi*" -ErrorAction SilentlyContinue'], expected_exit_code="")
            logging.info("Setting route to host for Ethernet.")
            self._call(["powershell.exe", 'New-NetRoute -DestinationPrefix "' + self.host_ip + '/32" -InterfaceAlias "Ethernet*" -ErrorAction SilentlyContinue'], expected_exit_code="")

            # Prioritize default route on Wi-Fi (but below Ethernet at 25)
            logging.info("Enabling Wi-Fi default route to the internet, with high priority.")
            self._call(["powershell.exe", 'Set-NetIpInterface -InterfaceAlias Wi-Fi* -IgnoreDefaultRoutes Disabled -InterfaceMetric 30'])
            self._call(["powershell.exe", 'Set-NetIpInterface -InterfaceAlias Cellular* -IgnoreDefaultRoutes Enabled -InterfaceMetric 500'])
        elif self.connection.lower() == "cellular": 
            # See if connection minimize policy is already 0, to save us from having to set it.
            try:
                logging.info("Checking if connection minimize policy is already set to 0.")
                response = self._call(["powershell.exe", '(Get-PolicyFileEntry -Path "$env:windir\\' + system_path + '\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Windows\\WcmSvc\\GroupPolicy -ValueName fMinimizeConnections).Data'])
            except:
                response = "1" # fail
            if (response != "0"):
                logging.info("Uploading PolicyFileEditor.")

                self._upload("utilities\\third_party\\PolicyFileEditor", "C:\\Program Files\\WindowsPowerShell\\Modules")
                self._upload("utilities\\third_party\\PolicyFileEditor", "C:\\Program Files (x86)\\WindowsPowerShell\\Modules")

                # Set MinimizeConnections policy to 0, so that Wi=Fi and Cellular can be active at same time
                logging.debug("Setting MinimizeConnections policy to 0.")
                self._call(["powershell.exe", 'set-executionpolicy unrestricted -Force'])
                self._call(["powershell.exe", 'Set-PolicyFileEntry -Path "$env:windir\\' + system_path + '\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Windows\\WcmSvc\\GroupPolicy -ValueName fMinimizeConnections -Data 0 -Type DWord'])
                self._call(["powershell.exe", 'Get-PolicyFileEntry -Path "$env:windir\\' + system_path + '\\GroupPolicy\\Machine\\registry.pol" -All'])
                self._call([cmd, '/C gpupdate'])

            # Add route to host
            logging.info("Setting route to host for Wi-Fi.")
            self._call(["powershell.exe", 'New-NetRoute -DestinationPrefix "' + self.host_ip + '/32" -InterfaceAlias "Wi-Fi*" -ErrorAction SilentlyContinue'], expected_exit_code="")
            logging.info("Setting route to host for Ethernet.")
            self._call(["powershell.exe", 'New-NetRoute -DestinationPrefix "' + self.host_ip + '/32" -InterfaceAlias "Ethernet*" -ErrorAction SilentlyContinue'], expected_exit_code="")

            # Ignore default route on Wi-Fi and set Wi-Fi interface at low priority
            logging.info("Disabling Wi-Fi default route to the internet, and setting low priority.")
            self._call(["powershell.exe", 'Set-NetIpInterface -InterfaceAlias Wi-Fi* -IgnoreDefaultRoutes Enabled -InterfaceMetric 500'])
            self._call(["powershell.exe", 'Set-NetIpInterface -InterfaceAlias Cellular* -IgnoreDefaultRoutes Disabled -InterfaceMetric 30'])
            # Mobile Network Profile settings
            response = self._call([cmd, '/c netsh mbn show profiles'], expected_exit_code="")
            # Assume active profile is top in list
            split_response = response.split('    ')
            for profile in split_response:
                if "There are no profiles" in profile:
                    self.fail("There are no profiles")
                if "There is no Mobile Broadband interface" in profile:
                    self.fail("There is no Mobile Broadband interface")
                if "------" in profile:
                    continue
                p = profile.strip()
                logging.info("Active cellular profile: " + p + ", setting to unmetered.")
                # Set cost to unrestricted (unmetered)
                self._call([cmd, '/c netsh mbn set profileparameter ' + p + ' cost=unrestricted'], expected_exit_code="")
        elif self.connection.lower() == "ethernet": 
            # Ignore default route on Wi-Fi and set Wi-Fi interface at low priority
            logging.info("Disabling Wi-Fi default route to the internet, and setting low priority.")
            self._call(["powershell.exe", 'Set-NetIpInterface -InterfaceAlias Wi-Fi* -IgnoreDefaultRoutes Enabled -InterfaceMetric 500'])
        else:
            self.fail("Uncrecognized connection for network_prep.  Should be one of 'Wi-Fi', 'Cellular', or 'Ethernet'")

        # Log Interface and Routing tables
        logging.info("Dumping route and interface information.")
        self._call(["powershell.exe", 'Get-NetIpInterface'])
        self._call(["powershell.exe", 'Get-NetRoute'])

    def tearDown(self):
        core.app_scenario.Scenario.tearDown(self)