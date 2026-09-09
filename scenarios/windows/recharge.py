# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# recharge
# 
# Turns on the device charger and wait until battery level reache specified threshold.
# Relies on the charge_on and charge_off scenarios.
#
# Setup instructions:
#   Set up the charge_on and charge_off paramters in the device profile.
##

import builtins
import logging
import core.app_scenario
from core.parameters import Params
import time
import subprocess
from utilities.open_source.widgets import Widgets

class Recharge(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'resume_threshold', '100')  # Percent battery level to charge to
    Params.setDefault(module, 'post_charge_delay', '0', desc="How many seconds to wait after reaching the resume_threshold before disconnecting charger.")  # Adding time here can help sensure the device is maximally charged.
    Params.setDefault(module, 'leave_on_ac', '0', valOptions=["0", "1"])
    Params.setDefault(module, 'monitor_only', '0', valOptions=["0", "1"])  # Do not turn on charger, just monitor battery level
    Params.setDefault(module, 'check_smart_charge', '1', valOptions=["0", "1"])

    widgets = Widgets()

    # Override collection of config data, traces, and execution of callbacks 
    Params.setOverride("global", "prep_tools", "")

    is_prep = True
    hide_ui = False

    def setResumeThreshold(self, value):
        self.resume_threshold = value
        Params.setParam(self.module, 'resume_threshold', value)
    
    def setLeaveOnAc(self, value):
        self.leave_on_ac = value
        Params.setParam(self.module, 'leave_on_ac', value)

    def setMonitorOnly(self, value):
        self.monitor_only = value
        Params.setParam(self.module, 'monitor_only', value)

    def runTest(self):
        # Get parameters
        self.resume_threshold = Params.get(self.module, 'resume_threshold')
        self.post_charge_delay = Params.get(self.module, 'post_charge_delay')
        self.leave_on_ac = Params.get(self.module, 'leave_on_ac')
        self.monitor_only = Params.get(self.module, 'monitor_only')
        self.platform = Params.get('global', 'platform')
        self.check_smart_charge = Params.get(self.module, 'check_smart_charge')
        self.charge_on_call = Params.get('global', 'charge_on_call')
        self.charge_off_call = Params.get('global', 'charge_off_call')

        MAX_COUNT = 60
        count = 0
        # if self.monitor_only != '1' and (self.charge_on_call == None or self.charge_on_call == ''):
        #     logging.info("Recharge: no charge_on_call found, returning...")
        #     return

        logging.info("Charging...")
        # Start charging and wait until resume_threshold reached
        self.chargeOn()

        old_batt_level = -1
        # TODO: handle errors
        while True:
            try:
                batt_level = self.getBattLevel()
            except:
                logging.info("Recharge: Couldn't read battery level")
                time.sleep(60)
                continue          
            logging.info("Battery level: " + str(batt_level) + "  Expected Level: " + str(self.resume_threshold))
            self._status_window(f"Charging to {self.resume_threshold}%...\nCurrent battery level: [color=white]{batt_level}%[/color]")

            if batt_level >= int(self.resume_threshold):
                logging.info("Charging complete")
                delay = 0
                try:
                    delay = int(self.post_charge_delay)
                except:
                    logging.error(f"Invalid post_charge_delay setting: {self.post_charge_delay}.  Make sure it's an integer.")
                else:
                    logging.info(f"Delaying for {delay} seconds. This delay is configurable by adding the 'post_charge_delay' parameter in the device profile.")
                    units = "seconds"
                    print_delay = delay
                    if delay > 60:
                        print_delay = int(delay / 60)
                        units = "minutes"
                    self._status_window(f"Charging complete.\nDelaying for {print_delay} {units} before disconnecting charger.")
                    time.sleep(delay)
                if (self.leave_on_ac == '0'):
                    self.chargeOff()
                    # TODO: handle errors
                break
            else:
                if batt_level == old_batt_level:
                    count += 1
                    logging.info("Seeing same battery level for " + str(count) + " times.")
                else:
                    count = 0
                if count == MAX_COUNT and self.check_smart_charge == "1":
                    logging.info("Smart charging feature prevents recharge from completing.  Run down the battery and try again.")
                    self._status_window(f"Smart charging feature prevents recharge from completing.  Run down the battery and try again.")
                    if (self.leave_on_ac == '0'):
                        self.chargeOff()
                    break
                time.sleep(60)
                old_batt_level = batt_level
            

    def getBattLevel(self):
        if self.platform.lower() == "wcos":
            batt_level = int(self._call(["M:\\Tools\\Surface\\SMonitor\\SMonitorUAP.exe /radix dec /batteryrsoc"], blocking=True).split(":")[-1] )
        elif self.platform.lower() == "android":
            command = "adb "
            # if device_ip is not None:
            command = command + "-s " + str(self.dut_ip) + ":5555 "
            command = command + "shell \"dumpsys battery | grep 'level'|cut -f2 -d ':'\""
            p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell = True)
            out, err = p.communicate()
            actual_exit_code = p.returncode
            batt_level = out.decode('utf-8').rstrip()

        elif self.platform.lower() == 'macos':
            # Get AppleRawCurrentCapacity level via ioreg
            raw_current_capacity_result = self._call(["bash", '-c "ioreg -r -c AppleSmartBattery -a | plutil -extract 0.AppleRawCurrentCapacity raw -"'], blocking=True)
            raw_current_capacity_level = raw_current_capacity_result.strip()

            # Get AppleRawMaxCapacity level via ioreg
            raw_max_capacity_result = self._call(["bash", '-c "ioreg -r -c AppleSmartBattery -a | plutil -extract 0.AppleRawMaxCapacity raw -"'], blocking=True)
            raw_max_capacity_level = raw_max_capacity_result.strip()

            # Calculate Battery level to 2 decimal places
            level = round(float(raw_current_capacity_level) / float(raw_max_capacity_level) * 100, 2)
            batt_level = int(level)

        else:
            batt_level = self._call(["powershell.exe", "Add-Type -Assembly System.Windows.Forms; [Math]::round(([System.Windows.Forms.SystemInformation]::PowerStatus.BatteryLifePercent) * 100, 2)"])
        return int(batt_level)
    
    def chargeOn(self):
        if self.monitor_only == '1':
            logging.info("Monitoring only, not turning on charger.")
            return
        logging.info("Attempting to turn on charger...")
        if self.checkState() == 2:
            logging.info("Already charging.")
            return
        if (self.charge_on_call != ""):
            self._host_call(self.charge_on_call)
            self.waitForState(2, automated=True)
            logging.info("Charger turned on.")
        else:
            logging.warning("No charge_on_call specified.  Manually turn on charger to continue.")
            self._status_window("Attempting to turn on charger...\nAutomated charging not set up.\nManually connect charger to continue.")
            self.widgets.about("Connect Charger", "Manually connect charger.", break_callback=self.onAC)

    def chargeOff(self):
        if (self.leave_on_ac != '0'):
            return
        if self.monitor_only == '1':
            logging.info("Monitoring only, not turning off charger.")
            return
        if self.checkState() == 1:
            logging.info("Already on battery.")
            return
        logging.info("Attempting to turn off charger...")
        if (self.charge_off_call!=""):
            self._host_call(self.charge_off_call)
            logging.info("Charger turned off.")
            self.waitForState(1, automated=True)
        else:
            logging.warning("No charge_off_call specified.  Manually turn off charger to continue.")
            self._status_window("Attempting to turn off charger...\nAutomated charging not set up.\nManually disconnect charger to continue.")
            self.widgets.about("Disconnect Charger", "Manually disconnect charger.", break_callback=self.onDC)

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

    def waitForState(self, target_state, automated=False):
        state = 0
        timeout = 20 # seconds
        while state != target_state:
            state = self.checkState()
            time.sleep(1)
            if automated:
                timeout -= 1
                if timeout <= 0:
                    logging.error("Timeout waiting for target battery state.")
                    self._fail("Timeout waiting for target battery state.")
                    break
        return state

    def onAC(self):
        state = self.checkState()
        if state == 2:
            return True
        else:
            return False

    def onDC(self):
        state = self.checkState()
        if state == 1:
            return True
        else:
            return False

