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

class Recharge(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'resume_threshold', '100')  # Percent battery level to charge to
    Params.setDefault(module, 'post_charge_delay', '7200', desc="How many seconds to wait after reaching the resume_threshold before disconnecting charger.")  # Adding time here can help sensure the device is maximally charged.
    Params.setDefault(module, 'leave_on_ac', '0', valOptions=["0", "1"])
    Params.setDefault(module, 'monitor_only', '0', valOptions=["0", "1"])  # Do not turn on charger, just monitor battery level
    Params.setDefault(module, 'check_smart_charge', '1', valOptions=["0", "1"])
    Params.setDefault('charge_on', 'charge_on_call', '')
    Params.setDefault('charge_off', 'charge_off_call', '')

     # Get parameters
    resume_threshold = Params.get(module, 'resume_threshold')
    post_charge_delay = Params.get(module, 'post_charge_delay')
    leave_on_ac = Params.get(module, 'leave_on_ac')
    monitor_only = Params.get(module, 'monitor_only')
    platform = Params.get('global', 'platform')
    check_smart_charge = Params.get(module, 'check_smart_charge')

    charge_on_call = Params.get('global', 'charge_on_call')
    charge_off_call = Params.get('global', 'charge_off_call')

    if charge_on_call == '' or charge_on_call is None:
        charge_on_call = Params.get('charge_on', 'charge_on_call')
    if charge_off_call == '' or charge_off_call is None:
        charge_off_call = Params.get('charge_off', 'charge_off_call')

    # Override collection of config data, traces, and execution of callbacks 
    Params.setOverride("global", "prep_tools", "")

    is_prep = True

    def setResumeThreshold(self, value):
        self.resume_threshold = value
    
    def setLeaveOnAc(self, value):
        self.leave_on_ac = value

    def setMonitorOnly(self, value):
        self.monitor_only = value

    def runTest(self):
        MAX_COUNT = 60
        count = 0
        if self.monitor_only != '1' and (self.charge_on_call == None or self.charge_on_call == ''):
            logging.info("Recharge: no charge_on_call found, returning...")
            return

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

            if batt_level >= int(self.resume_threshold):
                logging.info("Charging complete")
                delay = 0
                try:
                    delay = int(self.post_charge_delay)
                except:
                    logging.error(f"Invalid post_charge_delay setting: {self.post_charge_delay}.  Make sure it's an integer.")
                else:
                    logging.info(f"Delaying for {delay} seconds.")
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
                    logging.info("Smart charging feature prevents recharge from completing.")
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
        else:
            batt_level = self._call(["powershell.exe", "Add-Type -Assembly System.Windows.Forms; [Math]::round(([System.Windows.Forms.SystemInformation]::PowerStatus.BatteryLifePercent) * 100, 2)"])
        return int(batt_level)
    
    def chargeOn(self):
        if self.monitor_only == '1':
            logging.info("Monitoring only, not turning on charger.")
            return
        logging.info("Attempting to turn on charger...")
        if (self.charge_on_call != ""):
            self._host_call(self.charge_on_call)
            logging.info("Charger turned on.")
        else:
            logging.warning("No charge_on_call specified.")
        if Params.get('global', 'local_execution') == '1':
            self._host_call('utilities\\MsgPrompt.exe -WaitForAC')
            logging.info("Charger plugged in.")

    def chargeOff(self):
        if (self.leave_on_ac != '0'):
            return
        if self.monitor_only == '1':
            logging.info("Monitoring only, not turning off charger.")
            return
        logging.info("Attempting to turn off charger...")
        if (self.charge_off_call!=""):
            self._host_call(self.charge_off_call)
            logging.info("Charger turned off.")
        else:
            logging.warning("No charge_off_call specified.")
        if Params.get('global', 'local_execution') == '1':
            self._host_call('utilities\\MsgPrompt.exe -WaitForDC')
            logging.info("Charger unplugged.")
