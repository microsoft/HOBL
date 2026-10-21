# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# charge_off
# 
# Turns off the device charger.
# Intended to be included at the beginning of a test plan
#
# Setup instructions:
#   Specify the command to call to turn off the charger for the "charge_off_call" parameter in your parameters file.
##

import logging
import core.app_scenario
from core.parameters import Params
from utilities.open_source.widgets import Widgets


class ChargeOff(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]

    # Override collection of config data, traces, and execution of callbacks 

    # Prevent any tools from running
    Params.setOverride('global', 'prep_tools', '')

    widgets = Widgets()

    is_prep = True
    hide_ui = False

    def setUp(self):
        # Don't call base setUp so that we don't interact with DUT.
        return

    def runTest(self):
        # Get parameters
        charge_off_call = Params.get('global', 'charge_off_call')
        is_local = Params.get('global', 'dut_ip') in ['127.0.0.1', 'localhost']

        logging.info("Attempting to turn off charger...")
        if is_local:
            self._status_window("Attempting to turn off charger...")
        if charge_off_call == '':
            if self.checkState() == 1:
                logging.info("Already on DC power.")
                if is_local:
                    self._status_window("Already on DC power.")
                return
            logging.warning("No charge_off_call specified.  Manually turn off charger to continue.")
            if is_local:
                self._status_window("Attempting to turn off charger...\nAutomated charging not set up.\nManually disconnect charger to continue.")
            self.widgets.about("Disconnect Charger", "Manually disconnect charger.", break_callback=self.onDC)
        else:
            self._host_call(charge_off_call)
            logging.info("Charger turned off.")
            if is_local:
                self._status_window("Charger turned off.")

    def tearDown(self):
        # Don't call base tearDown so that we don't interact with DUT.
        return

    def kill(self):
        # Prevent base kill routine from running
        return 0

    def checkState(self):
        # Returns 1 for DC, 2 for AC.
        state = 0
        if self.platform.lower() == 'macos':
            battery_status = self._call(["bash", "-c \"pmset -g batt | grep -o 'discharging\\|charging\\|charged' | head -n 1\""], timeout=10)
            if "discharging" in battery_status:
                state = 1
            elif "charging" in battery_status:
                state = 2
            elif "charged" in battery_status:
                state = 2
        else:
            state = int(self._call(["powershell", "(Get-WmiObject -Class Win32_Battery -ea 0).BatteryStatus"], timeout=10))

        return state

    def onDC(self):
        state = self.checkState()
        if state == 1:
            return True
        else:
            return False

