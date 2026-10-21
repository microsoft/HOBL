# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# charge_on
# 
# Turns on the device charger.
# Intended to be included at the end of a test plan
#
# Setup instructions:
#   Specify the command to call to turn on the charger for the "charge_on_call" parameter in your parameters file.
##

import logging
import core.app_scenario
from core.parameters import Params
from utilities.open_source.widgets import Widgets
import time

class ChargeOn(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]

    # Override collection of config data, traces, and execution of callbacks 

    # Prevent any tools from running
    Params.setOverride('global', 'prep_tools', '')

    # Get parameters

    widgets = Widgets()

    is_prep = True
    hide_ui = False

    def setUp(self):
        # Don't call base setUp so that we don't interact with DUT.
        return

    def runTest(self):
        charge_on_call = Params.get('global', 'charge_on_call')
        is_local = Params.get('global', 'dut_ip') in ['127.0.0.1', 'localhost']
        logging.info("Attempting to turn on charger...")
        if is_local:
            logging.info("Running on local machine.")
            self._status_window("Attempting to turn on charger...")
        if charge_on_call == '':
            logging.info("No charge_on_call specified.")
            if self.checkState() == 2:
                logging.info("Already on AC power.")
                if is_local:
                    self._status_window("Already on AC power.")
                return
            logging.warning("No charge_on_call specified.  Manually turn on charger to continue.")
            if is_local:
                self._status_window("Attempting to turn on charger...\nAutomated charging not set up.\nManually connect charger to continue.")
            self.widgets.about("Connect Charger", "Manually connect charger.", break_callback=self.onAC)
        else:
            self._host_call(charge_on_call)
            logging.info("Charger turned on.")
            if is_local:
                self._status_window("Charger turned on.")
            # Don't check status with automation because DUT may be offline.

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

    def onAC(self):
        state = self.checkState()
        if state == 2:
            return True
        else:
            return False
