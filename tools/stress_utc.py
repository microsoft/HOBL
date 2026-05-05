# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Tool for collecting and processing UTC performance data for perf_stress scenarios.
# Runs the proprietary PerfParser binary against the captured ETL and post-processes
# its output CSV: filters rows to the metrics declared in our manifest and rewrites
# the Scenario column with the manifest's id.

from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import csv
import logging
import os
import re
import xml.etree.ElementTree as ET


class Tool(Scenario):
    '''
    Collects and processes UTC performance metrics for stress workloads.
    Outputs a CSV with manifest id instead of Scenario name.
    '''

    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'provider', 'perf_utc.wprp', desc="WPRP file to use for UTC traces.", valOptions=["@\\providers"])
    # Get parameters
    provider = Params.get(module, 'provider')

    def initCallback(self, scenario):
        self.scenario = scenario

        all_providers = Params.getCalculated('trace_providers')
        all_providers = all_providers + " " + self.provider
        Params.setCalculated('trace_providers', all_providers)

    def testBeginCallback(self):
        return

    def testEndCallback(self):
        return

    @staticmethod
    def _build_pt_lookup(manifest_file):
        """Parse the manifest XML and build a dict mapping the manifest's metric
        name to the manifest scenario id.
        """
        lookup = {}
        try:
            tree = ET.parse(manifest_file)
            root = tree.getroot()
            for scenario in root.iter('scenario'):
                sname = scenario.get('scenarioname', '')
                pt_name = scenario.get('ptscenarioname', '')
                match = re.match(r'PT_(\d+)_', sname)
                if not match:
                    continue
                pt_num = match.group(1)
                if pt_name:
                    lookup[pt_name] = pt_num
                stripped_match = re.match(r'^PT_\d+_(.+)_[^_]*$', sname)
                if stripped_match:
                    parser_form = stripped_match.group(1)
                    if parser_form:
                        lookup.setdefault(parser_form, pt_num)
                        trimmed = parser_form.strip()
                        if trimmed and trimmed != parser_form:
                            lookup.setdefault(trimmed, pt_num)
        except Exception as e:
            logging.warning(f"Could not parse manifest for id lookup: {e}")
        return lookup

    # PerfParser writes either the full manifest scenario name or the HOBL
    # etw_event_tag value into the Scenario column, and the manifest's metric
    # name into the Metric column. We recover the scenario id from whichever
    # column carries it.
    def dataReadyCallback(self):
        etl_trace = self.scenario.result_dir + "\\" + self.scenario.testname + ".etl"
        if not os.path.isfile(etl_trace):
            logging.warning("Perf Stress Tool - ETL file not found, skipping: " + etl_trace)
            return
        raw_output = self.scenario.result_dir + "\\" + self.scenario.testname + "_PerfMetrics_raw.csv"
        perf_output = self.scenario.result_dir + "\\" + self.scenario.testname + "_PerfMetrics.csv"
        manifest_file = "utilities\\proprietary\\ParseUtc\\StressUtcPerftrack.xml"

        logging.info("Perf Stress Tool - Running PerfParser on " + etl_trace)

        # Run PerfParser to produce the raw CSV (Scenario, Metric, Duration)
        try:
            self._host_call("utilities\\proprietary\\ParseUtc\\PerfParser.exe " + etl_trace + " " + manifest_file + " " + raw_output)
        except Exception as e:
            logging.warning(f"PerfParser returned an error (may still have partial output): {e}")

        # Post-process: replace Scenario column with PT column
        if not os.path.isfile(raw_output):
            logging.warning("PerfParser did not produce output: " + raw_output)
            return

        pt_lookup = self._build_pt_lookup(manifest_file)

        try:
            with open(raw_output, 'r', newline='') as f_in:
                reader = csv.DictReader(f_in)
                rows = list(reader)

            matched_rows = []
            with open(perf_output, 'w', newline='') as f_out:
                writer = csv.writer(f_out)
                writer.writerow(['PT', 'Metric', 'Duration'])
                for row in rows:
                    scenario_name = row.get('Scenario', '').strip()
                    metric = row.get('Metric', '').strip()
                    duration = row.get('Duration', '').strip()
                    # First try: extract id directly from Scenario column
                    pt = ''
                    scenario_match = re.match(r'PT_(\d+)_', scenario_name)
                    if scenario_match:
                        pt = scenario_match.group(1)
                    # Second try: look up Metric against manifest mapping. This
                    # handles rows where Scenario is an injected etw_event_tag
                    # rather than the manifest scenario name itself.
                    if not pt:
                        pt = pt_lookup.get(metric, '')
                    # Only include metrics whose id is in our manifest. Built-in
                    # scenarios not in our XML are skipped.
                    if pt:
                        writer.writerow([pt, metric, duration])
                        matched_rows.append(pt)
                    else:
                        logging.debug(f"Skipping unmatched metric: {metric}")

            logging.info(f"Perf Stress Tool - Wrote {len(matched_rows)} metrics to {perf_output} (filtered {len(rows) - len(matched_rows)} unmatched)")
            # Keep raw_output so the operator can see ALL ids PerfParser found,
            # including those filtered by manifest whitelisting. Useful for tuning
            # the manifest and diagnosing metric loss under stress.
        except Exception as e:
            logging.error(f"Error post-processing PerfMetrics CSV: {e}")
            # If post-processing fails, keep the raw output as the final output
            if os.path.isfile(raw_output) and not os.path.isfile(perf_output):
                os.rename(raw_output, perf_output)

    def testTimeoutCallback(self):
        return
