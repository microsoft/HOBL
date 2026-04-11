# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Powercfg tool

from core.parameters import Params
from core.app_scenario import Scenario
import logging
import os


class Tool(Scenario):
    '''
    Switch to specified power mode (best power efficiency, recommended/balanced, better, best/best performance). Returns to last mode on test end.
    '''
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'mode', 'best power efficiency', desc="The power mode to switch to (best power efficiency, recommended/balanced, better, best performance).", valOptions=["best power efficiency", "recommended/balanced", "better", "best performance"])

    # Get parameters
    mode = Params.get(module, 'mode').lower() # forse to lower for comparison

    # Registry key path for storing initial power mode
    REG_KEY_PATH = r"HKLM\SOFTWARE\HOBL"
    REG_VALUE_NAME = "InitialPowerMode"

    def setPowerMode(self, power_mode):
        if power_mode == "best power efficiency":
            self._call(["cmd.exe", "/C powercfg /overlaysetactive 961cc777-2547-4f9d-8174-7d86181b8a7a"])
        elif power_mode == "recommended/balanced":
            self._call(["cmd.exe", "/C powercfg.exe /overlaysetactive overlay_scheme_none"])
        elif power_mode == "better":
            self._call(["cmd.exe", "/C powercfg.exe /overlaysetactive overlay_scheme_high"])
        elif power_mode == "best performance":
            self._call(["cmd.exe", "/C powercfg.exe /overlaysetactive overlay_scheme_max"])
        else:
            msg = f"Unsupported Power Mode {power_mode}.  Choices are: 'best power efficiency', 'recommended/balanced', 'better', 'best performance'"
            logging.error(msg)
            self.fail(msg)

    def initCallback(self, scenario):
        # Initialization code
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        
        # Call config_check.ps1 to get the initial power mode so it can swap back to it
        # Check if config_check.ps1 file exists on DUT
        self._upload("utilities\\open_source\\config_check.ps1", self.dut_exec_path, check_modified=True)
        cmd = '-ExecutionPolicy Unrestricted -Command "' + os.path.join(self.dut_exec_path, "config_check.ps1 -GetPowerModeOnly") + '"'
        initial_power_mode = self._call(["powershell.exe", cmd]).lower()
        logging.info(f"Initial Power Mode: {initial_power_mode}")
        
        # Store the initial power mode in registry on dut locally.
        # Using reg key to store as when it gets to cleanup() it creates a new scenario so any variables are resetted losing the initial power mode value.
        self._call(["cmd.exe", '/C reg add "' + self.REG_KEY_PATH + '" /v ' + self.REG_VALUE_NAME + ' /t REG_SZ /d "' + initial_power_mode + '" /f'])
        
        # Set the power mode
        self.setPowerMode(self.mode)


    def testBeginCallback(self):
        return
    
    def testEndCallback(self):
        # Read the initial power mode from registry
        result = self._call(["cmd.exe", '/C reg query "' + self.REG_KEY_PATH + '" /v ' + self.REG_VALUE_NAME], expected_exit_code="")
        if result and self.REG_VALUE_NAME in result:
            # Parse the value from reg query output
            initial_power_mode = result.split("REG_SZ")[-1].strip()
            logging.info(f"Restoring power mode to: {initial_power_mode}")
            self.setPowerMode(initial_power_mode)
            # Delete the registry key after restoring
            self._call(["cmd.exe", '/C reg delete "' + self.REG_KEY_PATH + '" /v ' + self.REG_VALUE_NAME + ' /f'], expected_exit_code="")


    def dataReadyCallback(self):
        # You can do any post processing of data here.
        return
    
    def cleanup(self):
        logging.debug("Cleanup")
        self.testEndCallback()
