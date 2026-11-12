# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Template for creating a tool wrapper

from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import logging
import sys
import os


class Tool(Scenario):
    '''
    Calculates a MOS score from an abl_perf run.

    Collects an ETL trace with abl_perf.wprp and will parse results from it to calculate a MOS score.
    '''
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'provider', 'abl_perf.wprp')
    
    
    def initCallback(self, scenario):
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        self.scenario.perf_mode = "1"
        self.conn_timeout = False
           
        logging.info("Perf Tool - initializing, associated with scenario: " + self.scenario._module)

        # Getting global providers and adding to the list with etl_trace providers
        all_providers = Params.getCalculated('trace_providers')

        all_providers = all_providers + " abl_perf.wprp" 
        Params.setCalculated('trace_providers', all_providers)

    def testBeginCallback(self):
        return

    def testEndCallback(self):
        return

    def dataReadyCallback(self):
        if self.conn_timeout:
            return

        # ETL traces have been pulled back to the host
        # result_dir contains the full path to the results directory, and ends in <testname>_<iteration>

        etl_trace = self.scenario.result_dir + "\\" + self.scenario.testname + ".etl"
        os.makedirs(os.path.join(self.scenario.result_dir, f"{self.module}"), exist_ok=True)
        perf_output = self.scenario.result_dir + "\\" + f"{self.module}\\" + self.scenario.testname
        mos_input = perf_output + "_PerfResult.csv"
        mos_output = self.scenario.result_dir + "\\" + f"{self.module}\\" + self.scenario.testname

        logging.info("Perf Tool - Running PerfMeasure on " + etl_trace)

        # Parse the ETL trace into a CSV file summarizing latency measurements for each activity
        self._host_call("utilities\\x64\\WUxPC.exe -i " + etl_trace + " -o " + perf_output)

        # Produce MOS score from CSV file.
        scenario_name = self.scenario.testname[:-4]
        self._host_call("python.exe utilities\\MOS\\ABL_Performance_Tool.py " + scenario_name + " " + mos_input + " " + mos_output)

    def testTimeoutCallback(self):
        self.conn_timeout = True

