# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Tool for collecting and processing UTC performance data

from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import logging


class Tool(Scenario):
    '''
    Collects and processes UTC Perftrack scenarios
    '''

    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'provider', 'perf_utc.wprp', desc="WPRP file to use for UTC Perftrack traces.", valOptions=["@\\providers"])
    # Get parameters
    provider = Params.get(module, 'provider')

    def initCallback(self, scenario):
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        self.conn_timeout = False

        # Getting global providers and adding to the list with etl_trace providers
        all_providers = Params.getCalculated('trace_providers')

        all_providers = all_providers + " " + self.provider
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
        # _module contains just the testname
        etl_trace = self.scenario.result_dir + "\\" + self.scenario.testname + ".etl"
        perf_output = self.scenario.result_dir + "\\" + self.scenario.testname + "_PerfMetrics.csv"
        manifest_file = "utilities\\proprietary\\ParseUtc\\UtcPerftrack.xml"

        logging.info("Perf Tool - Running PerfParser on " + etl_trace)

        self._host_call("utilities\\proprietary\\ParseUtc\\PerfParser.exe " + etl_trace + " " + manifest_file + " " + perf_output)

    def testTimeoutCallback(self):
        self.conn_timeout = True
