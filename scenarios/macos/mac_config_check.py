# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# config_check
# 
# Runs the config_check script on the DUT to get the system  configuration
# details.
#
# Setup instructions:
#   Run config_check_prep scenario.
##

import builtins
import logging
import core.app_scenario
from core.parameters import Params
import os
import json


class MacConfigCheck(core.app_scenario.Scenario):

    module = __module__.split('.')[-1]
    # Set default parameters
    override_keys = ['Study Type', 'Comments', 'Hardware Version', 'Blade', 'Accessories', 'RTC Reserve (%)', 'Raw Data Location', 'Device Name']
    for key in override_keys:
        Params.setDefault(module, key, '')

    # Get parameters

    # Override some potential global params that wouldn't be appropriate for a config_check
    Params.setOverride("global", "trace", "0")
    Params.setOverride("global", "config_check", "0")
    Params.setOverride("global", "callback_test_begin", "")
    Params.setOverride("global", "callback_test_end", "")
    Params.setOverride("global", "tools", "")

    is_prep = True

    def runTest(self):
        hobl_ver = "Unknown"
        try:
            fo = open("hobl_version.txt", "r")
            hobl_ver = fo.readline(50).strip()
            fo.close()
        except Exception as e:
            logging.warning(f"Failed to read hobl_version.txt: {e}")

        override_dict = {key: Params.get(self.module, key) for key in self.override_keys}
        override_dict["Hardware Version"] = override_dict["Hardware Version"].upper()
        override_dict['HOBL Version'] = hobl_ver.strip()
        override_str = json.dumps(override_dict)
        override_str = override_str.replace('"', "'")

        dest = self.dut_exec_path + "/config_check.sh"
        self._upload("utilities\\open_source\\config_check.sh", self.dut_exec_path, check_modified=True)
        cmd = f'-c "{dest} --logfile={self.dut_data_path}/Config --override-string=\\\"{override_str}\\\""'
        self._call(["zsh", cmd])
        
        
