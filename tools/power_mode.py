# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

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

    POWER_MODE_GUID_MAP = {
        "961cc777-2547-4f9d-8174-7d86181b8a7a": "best power efficiency",
        "00000000-0000-0000-0000-000000000000": "recommended/balanced",
        "3af9b8d9-7c97-431d-ad78-34a8bfea439f": "better",
        "ded574b5-45a0-4f42-8737-46345c09c238": "best performance"
    }

    def set_power_mode(self, power_mode, power_source, power_source_text=None):
        power_mode = power_mode.lower()

        if not power_source_text:
            power_source_text = power_source

        logging.info(f"Setting {power_source_text} power mode to: {power_mode}")

        if power_mode == "best power efficiency":
            power_manager_method = "SetPowerModeBestPowerEfficiency"
        elif power_mode == "recommended/balanced":
            power_manager_method = "SetPowerModeBalanced"
        elif power_mode == "better":
            power_manager_method = "SetPowerModeBetter"
        elif power_mode == "best performance":
            power_manager_method = "SetPowerModeBestPerformance"
        else:
            self.error_fail(
                f"Unsupported power mode {power_mode}. Choices are: 'best power efficiency', 'recommended/balanced', 'better', 'best performance'"
            )

        self.power_manager_call(power_manager_method, power_source)

    def store_reg_value(self, reg_value_suffix, data):
        reg_value = self.REG_VALUE_NAME + reg_value_suffix
        self._call(["cmd.exe", f"/C reg add {self.REG_KEY_PATH} /v {reg_value} /t REG_SZ /d \"{data}\" /f"])

    def read_and_delete_reg_value(self, reg_value_suffix):
        reg_value = self.REG_VALUE_NAME + reg_value_suffix

        result = self._call(["cmd.exe", f"/C reg query {self.REG_KEY_PATH} /v {reg_value}"], expected_exit_code="")
        self._call(["cmd.exe", f"/C reg delete {self.REG_KEY_PATH} /v {reg_value} /f"], expected_exit_code="")

        if result and reg_value in result:
            return result.split("REG_SZ")[-1].strip()
        return None

    def save_and_set_power_mode(self, power_source, power_source_text=None):
        if not power_source_text:
            power_source_text = power_source

        initial_power_mode = self.POWER_MODE_GUID_MAP[self.power_manager_call("GetPowerMode", power_source).lower()]
        logging.info(f"Initial {power_source_text} power mode: {initial_power_mode}")
        self.store_reg_value(power_source_text, initial_power_mode)
        self.set_power_mode(self.mode, power_source, power_source_text)

    def restore_power_mode(self, power_source, power_source_text=None):
        if not power_source_text:
            power_source_text = power_source

        if mode := self.read_and_delete_reg_value(power_source_text):
            self.set_power_mode(mode, power_source, power_source_text)

    def initCallback(self, scenario):
        # Initialization code
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario

        if bool(self.power_manager_call("GetUseUserConfiguredPowerMode")):
            self.save_and_set_power_mode("AC")
            self.save_and_set_power_mode("DC")
        else:
            self.save_and_set_power_mode("AC", "Overlay")

    def testBeginCallback(self):
        return

    def testEndCallback(self):
        if bool(self.power_manager_call("GetUseUserConfiguredPowerMode")):
            self.restore_power_mode("AC")
            self.restore_power_mode("DC")
        else:
            self.restore_power_mode("AC", "Overlay")

    def dataReadyCallback(self):
        # You can do any post processing of data here.
        return

    def cleanup(self):
        logging.debug("Cleanup")
        self.testEndCallback()
