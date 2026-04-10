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


class ConfigCheck(core.app_scenario.Scenario):

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

    # Local parameters
    #prep_scenarios = ["config_check_prep"]
    prep_scenarios = []

    def setUp(self):
        logging.info("running setup")
        core.app_scenario.Scenario.setUp(self)


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

        if self.platform.lower() == "android":
            # self._host_call("python utilities\\Android\\config_check_android.py --LogFile " + str(self.result_dir) + '\\Config' + ' --OverrideString \'"' + override_str.replace("'", '"') + '"\' -i ' + str(self.dut_ip) + ":5555", expected_exit_code='')
            # self._host_call("python utilities\\Android\\config_check_android.py --LogFile " + str(self.result_dir) + '\\Config' + ' --OverrideString "' + '\\\"' + override_str + '\\\"" -i ' + str(self.dut_ip) + ":5555", expected_exit_code='')
            # self._host_call("python utilities\\Android\\config_check_android.py --LogFile " + str(self.result_dir) + '\\Config' + " --OverrideString '\"[" + override_str.replace("'", '""') + "]\"' -i " + str(self.dut_ip) + ":5555", expected_exit_code='')
            self._host_call("python utilities\\Android\\config_check_android.py --LogFile " + str(self.result_dir) + '\\Config' + ' --OverrideString "' '\\\"' + override_str + '\\\"" -i ' + str(self.dut_ip) + ":5555", expected_exit_code='')
            # result = self._host_call('python .\\utilities\\Android\\config_check_android.py --PreRun --OverrideString "' + '\\\"' + override_str + '\\\"" --LogFile ' + self.result_dir + '\\' + self.testname + '_ConfigPre' + " -i " + str(self.dut_ip) + ":5555", expected_exit_code="")
        elif self.platform.lower() == "wcos":
            cmd = '-ExecutionPolicy Unrestricted -Command "' + os.path.join(self.dut_exec_path, "config_check.ps1 -LogFile " + self.dut_data_path, "Config") + " -OverrideString " + '\\\"' + override_str + '\\\""'
            self._call(["pwsh.exe", cmd])
        else:
            self._upload("utilities\\open_source\\config_check.ps1", self.dut_exec_path, check_modified=True)
            cmd = '-ExecutionPolicy Unrestricted -Command "' + os.path.join(self.dut_exec_path, "config_check.ps1 -LogFile " + self.dut_data_path, "Config") + " -OverrideString " + '\\\"' + override_str + '\\\""'
            self._call(["powershell.exe", cmd])

        # # Get version report, if available (Surface devices only)
        # dut_username = Params.get('global', 'dut_username')
        # dut_data_path = Params.getCalculated("dut_data_path")
        # dut_architecture = Params.get('global', 'dut_architecture')
        # version_report_location = "C:\\Users\\" + dut_username + "\\Desktop"

        # if dut_architecture == "x64":
        #     version_report_tool = "C:\\Tools\\VersionReport.cmd -LogFile c:\hobl_data\VersionInformation.txt"
        #     try:
        #         self._call(["cmd.exe", "/C" + version_report_tool])   
        #         # self._call(["robocopy.exe", version_report_location + " " + dut_data_path + " " + "VersionInformation.txt"], expected_exit_code="")
        #         logging.info("Version report generated")
        #     except:
        #         logging.info("Version report not supported")
        #         return
        # # For arm64 architecture
        # else:
        #     version_report_tool = "C:\\GoldenPath\\modules\\provisioning\\VersionReport.cmd"
        #     try:
        #         self._call(["cmd.exe", "/C" + version_report_tool])   
        #         # self._call(["robocopy.exe", version_report_location + " " + dut_data_path + " " + "VersionInformation.txt"], expected_exit_code="")
        #         logging.info("Version report generated")
        #     except:
        #         logging.info("Version report not supported")
        #         return

        self.createPrepStatusControlFile()
        
        
