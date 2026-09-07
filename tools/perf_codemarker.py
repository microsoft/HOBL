# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Tool for collecting and processing code marker performance data

from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import logging


class Tool(Scenario):
    '''
    Collects and processes code marker performance metrics.
    '''

    module = __module__.split('.')[-1]
    Params.setDefault(module, 'provider', 'utc_codemarkers.wprp', desc="WPRP file to use for code marker traces.", valOptions=["@\\providers"])
    provider = Params.get(module, 'provider')

    def initCallback(self, scenario):
        self.scenario = scenario
        self.conn_timeout = False

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

        etl_trace = self.scenario.result_dir + "\\" + self.scenario.testname + ".etl"
        metrics_output = self.scenario.result_dir + "\\" + self.scenario.testname + "_CodeMarkerMetrics.csv"
        parser = "utilities\\proprietary\\ParseCodeMarkers\\cmparser.exe"
        manifest = "utilities\\proprietary\\ParseCodeMarkers\\CMEvents.xml"

        logging.info("Perf CodeMarker Tool - Running cmparser on " + etl_trace)

        self._host_call(
            '"' + parser + '" "' + etl_trace + '" --manifest "' + manifest + '" --output "' + metrics_output + '"'
        )

    def testTimeoutCallback(self):
        self.conn_timeout = True
