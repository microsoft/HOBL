# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Socwatch tool

from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import logging
import sys
import time
import os


class Tool(Scenario):
    '''
    Run Intel's SOCWatch tool and parses results.
    '''
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'delay', '0')
    # Params.setDefault(module, 'additional_args', '-f cpu -f gfx-cstate -f pch-slps0 --max-detail -f panel-srr -f pcie-ltr -f pcie-lpm -f platform-ltr -f pmc-power-status -r detail -f dram-srr')
    # Params.setDefault(module, 'additional_args', '-f cpu-cstate -f cpu-pstate -f cpu-pkgc-dbg -f panel-srr -f sa-freq -f cpu -f gfx -f acpi-dstate -f sstate -f ddr-bw -f timer-resolution -f pch-all -f lpss-ltr -f pch-ip-status -f pch-slps0 -f pcie -f xhci -m -r auto')
    Params.setDefault(module, 'additional_args', '-f cpu-pkgc-dbg -f pcie -f platform-ltr -f panel-srr -f cpu-cstate -f cpu-pstate -f gfx-cstate -f gfx-pstate -f acpi-dstate -f sstate -f ddr-bw -f timer-resolution -f cpu-gpu-concurrency -f pch-slps0 -f pcie-lpm -f hw-gfx-pstate -f ddr-bw -f pch-ip-active-all -f pch-ip-status -f sys -f sa-freq -f pch-all')
    # Params.setDefault(module, 'additional_args', '-f cpu-pkgc-dbg -f cpu -f ddr-bw -f acpi-dstate -f sstate')
    # Get parameters
    delay = Params.get(module, 'delay')
    additional_args = Params.get(module, 'additional_args')
    platform = Params.get('global', 'platform')

    output_dir = ""

    def initCallback(self, scenario):
        # Initialization code
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        self.conn_timeout = False

    def testBeginCallback(self):
        if self.platform == "WCOS":
            self.output_dir = os.path.join(self.scenario.dut_exec_path, self.scenario._module)
            self._call([os.path.join(self.scenario.dut_exec_path, "socwatch", "socwatch.exe"), " -f cpu -f pch -f cpu-pkgc-dbg -f pcie-lpm -f s0ix-subs-res -t " + self.delay + " -o " + self.output_dir], blocking = False)
        else:
            self.output_dir = 'c:\\hobl_data\\socwatch\\' + self.scenario._module
            self._call(['cmd.exe', '/c mkdir "C:\\Users\\sfudally\\AppData\\Local\\Intel Corporation\\"'], expected_exit_code="") #overrides NDA prompt
            self._call(['cmd.exe', '/c echo 1 > "C:\\Users\\sfudally\\AppData\\Local\\Intel Corporation\\intel_socwatch_isip"']) #overrides NDA prompt
            self._call(["powershell.exe", "start-process -WindowStyle Minimized -FilePath c:\\hobl_bin\\socwatch\\socwatchhelper.exe -ArgumentList '-start -s " + self.delay + " -o " + self.output_dir + " " + self.additional_args + "'"], blocking = False)
        time.sleep(2)

    def testEndCallback(self):
        if self.platform == "WCOS":
            self._call([os.path.join(self.scenario.dut_exec_path, "socwatch", "socwatch.exe"), "-stop "], blocking = True, expected_exit_code="")
        else:
            self._call(["c:\\hobl_bin\\socwatch\\socwatchhelper.exe", "-stop "], blocking = True, expected_exit_code="")
        # temporary workaround to wait for socwatch exit.
        logging.info("Waiting Socwatch to complete output files to exit.........")
        
        # self._call(["powershell.exe", "c:\hobl_bin\wait_socwatch_exit.ps1"], blocking = True)
        while True:
            res = self._call(["cmd.exe", '/C tasklist /FI "imagename eq socwatch.exe" /nh'])
            print(res)
            if "No tasks are running" in res:
                break
            else:
                time.sleep(5)
        
        logging.info("Done waiting for Socwatch to exit.")
        if self.conn_timeout:
            output_file = self.output_dir + ".csv"
            self._call(["cmd.exe", '/c del ' + output_file], expected_exit_code="")

    def dataReadyCallback(self):
        if self.conn_timeout:
            return

        logging.info("Socwatch tool dataReadyCallback")
        logging.info("collection_enabled = " + Params.get('global', 'collection_enabled'))
        if Params.get('global', 'collection_enabled') != '0':
            logging.info("Parsing socwatch data")
            # host call of script_path
            infile = self.scenario.result_dir + "\\socwatch\\" + self.scenario._module + ".csv"
            outfile = self.scenario.result_dir + "\\socwatch\\" + self.scenario.testname + "_socwatch.csv"
            self._host_call("python.exe utilities\\open_source\\parse_socwatch.py" + " -i " + infile + " -o " + outfile)

    def testTimeoutCallback(self):
        self.conn_timeout = True

