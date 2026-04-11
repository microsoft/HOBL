# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Brightness setting tool

from builtins import str
from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import logging
import sys
import time
import re
# import xmlActionList as XAL


class Tool(Scenario):
    '''
    Map display brightness slider percentage to nits value specified by scenarios.
    '''
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'brightness', '150nits') # 65 or 65% or 150nits
    Params.setDefault(module, 'nits_map', '100nits:50% 150nits:65%')
    
    # Initialize parameters
    brightness = ""
    nits_map = ""
    platform = ""

    def initCallback(self, scenario):
        logging.warning("display_brightness tool is deprecated and will be removed in a future release. Please use the display tool instead.")
        # Get parameters
        self.brightness = Params.get(self.module, 'brightness')
        self.nits_map = Params.get(self.module, 'nits_map')
        self.platform = Params.get('global', 'platform')

        # Initialization code
        if self.nits_map == "Unknown":
            logging.error("Could not resolve specified nits_map parameter.")
            self.fail("Could not resolve specified nits_map parameter.")

        # Create map of nits values and corresponding brightness slider percentage setting
        nits_table = {}
        logging.debug("Nits map: " + self.nits_map)
        tuples_list = self.nits_map.split(" ")
        for t in tuples_list:
            nits_str, slider_str = t.split(":")
            nits = re.findall(r'\d+', nits_str)[0]
            try:
                slider = re.findall(r'\d+', slider_str)[0]
            except:
                logging.error('Invalid slider value in nits_map: ' + str(self.nits_map))
                raise Exception('Invalid slider value in nits_map:', self.nits_map)
            nits_table[nits] = slider
        logging.debug("Nits map parsed: " + str(nits_table))

        # If the specified brightness is in nits, look up the slider setting in the table, otherwise assume the number specified is a slider setting.
        brightness_val = re.findall(r'\d+', self.brightness)[0]
        if "nits" in self.brightness:
            if brightness_val in nits_table:
                brightness_val = nits_table[brightness_val]
            else:
                raise Exception('There is no slider percentage mapping for specified nits brightness {0}.'.format(self.brightness))
        logging.info ("Display brightness set to: " + brightness_val)

        # if self.platform.lower() == "wcos":
        #     alist = XAL.ActionList()
        #     alist.recordTouch(alist.find_element_by_xpath("//Group[@Name='SingleDisplayComposer0']//Pane[@Name='Taskbar']"))
        #     time.sleep(2)
        #     alist.recordTouch(alist.find_element_by_xpath("//Group[@Name='SingleDisplayComposer0']//Button[@Name='Start']"))
        #     time.sleep(2)
        #     alist.recordTouch(alist.find_element_by_name("Settings"))
        #     time.sleep(5)
        #     alist.recordTouch(alist.find_element_by_name("System"))
        #     time.sleep(2)
        #     ele = alist.find_element_by_name("Change brightness")
        #     ele_width = int(ele.get("width"))
        #     value = ((int(brightness_val) * ele_width) // 100)
        #     alist.recordTouch(ele, x_offset=value, y_offset=5)  # 344 190 | 280 32
        #     time.sleep(3)
        #     alist.recordTouch(alist.find_element_by_name("Close Settings"))
        #     time.sleep(2)

        if self.platform.lower() == "android":
            # send adb command to set brightness
            self._host_call("adb -s " + self.dut_ip + ":5555 shell settings put system screen_brightness " + str(brightness_val), expected_exit_code="")
        elif self.platform.lower() == "macos":
            self._call([self.dut_exec_path + "/brightness", str(int(brightness_val)/100.0)])
        else: # Windows
            self._call(["cmd.exe", "/c Powercfg.exe -SETDCVALUEINDEX scheme_balanced SUB_VIDEO aded5e82-b909-4619-9949-f5d71dac0bcb " + str(brightness_val)])
            self._call(["cmd.exe", "/c Powercfg.exe -SETACVALUEINDEX scheme_balanced SUB_VIDEO aded5e82-b909-4619-9949-f5d71dac0bcb " + str(brightness_val)])
            self._call(["cmd.exe", "/c Powercfg.exe -SETACTIVE scheme_balanced"])
    
    def testBeginCallback(self):
        pass
        
    def testEndCallback(self):
        pass

    def dataReadyCallback(self):
        pass
