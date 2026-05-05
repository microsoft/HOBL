# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Connected Standby
#
# Setup instructions:
#   Run Rundaily Prep Script
#   Have script for triggering a button press on the device 
##

from builtins import str
import builtins
import unittest
import logging
import time
import core.app_scenario
from core.parameters import Params
import os

class CS(core.app_scenario.Scenario):

    # Set default parameters
    Params.setDefault('cs_floor', 'cs_duration', '1200')  # Seconds 1200
    Params.setDefault('cs_floor', 'button_to_record_delay', '900')  # Seconds 900
    # Params.setDefault('cs_floor', 'reconnect_wait_delay', '20')  # Seconds 20
    Params.setDefault('cs_floor', 'button_sleep_callback', '')
    Params.setDefault('cs_floor', 'button_wake_callback', '')
    Params.setDefault('cs_floor', 'local_button', '1') # 0 = host, 1 = DUT
    Params.setDefault('cs_floor', 'sleep_mode', '') # Blank = connected standby, "S3" for S3.
    Params.setDefault('cs_floor', 'connection', 'Disconnected', desc="Connected or Disconnected from the network during standby", valOptions=["Disconnected", "Connected"])

    prep_scenarios = ["button_install"]


    def setUp(self):
        # Get parameters
        self.cs_duration = Params.get('cs_floor', 'cs_duration')
        self.button_to_record_delay = Params.get('cs_floor', 'button_to_record_delay')
        self.reconnect_wait_delay = Params.get('cs_floor', 'reconnect_wait_delay')
        self.button_sleep = Params.get('cs_floor', 'button_sleep_callback')
        self.button_wake = Params.get('cs_floor', 'button_wake_callback')
        self.local_button = Params.get('cs_floor', 'local_button')
        self.local_execution = Params.get('global', 'local_execution')
        self.sleep_mode = Params.get('cs_floor', 'sleep_mode')
        self.connection = Params.get('cs_floor', 'connection')

        self.wifi_off_duration = str((int(self.cs_duration)) + (int(self.button_to_record_delay)) + 15)

        # self._upload('scenarios\\cs_floor_resources\\cs_floor_wrapper.cmd', self.dut_exec_path + '\\cs_floor_resources', check_modified=True)
        self._upload("scenarios\\windows\\cs_floor\\cs_floor_wrapper.cmd", os.path.join(self.dut_exec_path, "cs_floor_resources"))
        self._upload("utilities\\proprietary\\sleep\\sleep.exe", os.path.join(self.dut_exec_path, "sleep"))


        # Call base setUp() which runs config_check and starts ETL tracing.
        # Prevent callback_test_begin from executing at this time
        core.app_scenario.Scenario.setUp(self, callback_test_begin='')
        
        # set up dut to disable wifi for wifi_off_duration
        logging.info("Setting DUT to wake on exiting standby")
        logging.info("Wifi Off Duration:" + self.wifi_off_duration)

        # Put Device to Sleep
        print("Device sleep now.")
        logging.info("Device sleep now.")
       
        if self.button_sleep != '':
            try:
                logging.info('DUT command: cmd.exe /C ' + self.dut_exec_path + '\\cs_floor_resources\\cs_floor_wrapper.cmd ' + str(15) + " " + self.connection)
                self._call(["cmd.exe", "/C " + os.path.join(self.dut_exec_path, "cs_floor_resources", "cs_floor_wrapper.cmd") + ' ' + str(15) + " " + self.connection], blocking = False) 
            except:
                pass
            time.sleep(5)
            logging.info("Sleep button:" + self.button_sleep)
            logging.info("Calling local Button Script")
            self._host_call("powershell " + self.button_sleep)
        else:
            if self.sleep_mode.lower() == "s3":
                logging.info("Calling pwrtest.exe on DUT.")
                result = self._call([os.path.join(self.dut_exec_path, "pwrtest", "pwrtest.exe"), " /sleep /p:" + str(int(self.wifi_off_duration))], blocking = False)
                print (result)
                if result is not None and 'error' in result :
                    raise Exception("pwrtest.exe could not found!")
                # Compensate for the 3s delay before hitting the button in the above button.exe command.
                time.sleep(3)
            else:  # Connected Standby
                logging.info("Calling Button.exe on DUT")
                try:             
                    logging.info("DUT command: cmd.exe /C " + self.dut_exec_path + "\\cs_floor_resources\\cs_floor_wrapper.cmd " + self.wifi_off_duration + " " + self.connection + " " + self.dut_exec_path)
                    self._call(["cmd.exe", "/C " + os.path.join(self.dut_exec_path, "cs_floor_resources", "cs_floor_wrapper.cmd") + ' ' + self.wifi_off_duration + " " + self.connection + " " + self.dut_exec_path], blocking = False) 
                    time.sleep(2)
                except:
                    logging.error("button.exe not found on DUT")

        logging.info("Delaying for " + self.button_to_record_delay + " seconds before starting power measurement.")
        
        if self.local_execution == '0':
            time.sleep(float(self.button_to_record_delay))
            

        # Start recording power
        self._callback(Params.get('global', 'callback_test_begin'))


    def runTest(self):
        # Sleep for specified duration
        
        if self.local_execution == '0':
            logging.info("Starting CS sleep for " + self.cs_duration + " seconds")        
            time.sleep(float(self.cs_duration))
        time.sleep(5)
        
        # Stop recording power
        self._callback(Params.get('global', 'callback_test_end'))

        # Give time for Stop command to propagate
        time.sleep(5)

        # Wake Up Device
        if self.button_wake != '':
            logging.info("Calling local Button Script")
            self._host_call("powershell " + self.button_wake)
        logging.info(f"Wait for DUT to be up")
        self._wait_for_dut_comm()

        if self.enable_screenshot == '1':
            self._screenshot(name="end_screen.png")

    def tearDown(self):
        # Prevent callback_test_end from executing in base tearDown() method
        core.app_scenario.Scenario.tearDown(self, callback_test_end="")
