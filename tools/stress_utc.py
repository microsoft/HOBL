# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Tool for collecting and processing UTC performance data for perf_stress scenarios.
# Uses StressUtcPerftrack.xml manifest and replaces the Scenario column with a PT column.

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
    Collects and processes UTC Perftrack scenarios for stress workloads.
    Outputs a CSV with PT number instead of Scenario name.
    '''

    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'provider', 'perf_utc.wprp', desc="WPRP file to use for UTC Perftrack traces.", valOptions=["@\\providers"])
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
        """Parse the manifest XML and build a dict mapping ptscenarioname -> PT_XXXX."""
        lookup = {}
        try:
            tree = ET.parse(manifest_file)
            root = tree.getroot()
            for scenario in root.iter('scenario'):
                sname = scenario.get('scenarioname', '')
                pt_name = scenario.get('ptscenarioname', '')
                match = re.match(r'PT_(\d+)_', sname)
                if match and pt_name:
                    lookup[pt_name] = match.group(1)
        except Exception as e:
            logging.warning(f"Could not parse manifest for PT lookup: {e}")
        return lookup

    # PerfParser uses etw_event_tag labels as Scenario column values.
    # Map known event-tag Scenario labels + Metric pairs to PT numbers.
    _scenario_metric_to_pt = {
        ('ExcelLaunch', 'ProcessLaunch_PC'): '8806',
        ('WordLaunch', 'ProcessLaunch_PC'): '8805',
        ('PowerPointLaunch', 'ProcessLaunch_PC'): '8807',
        ('OutlookLaunch', 'ProcessLaunch_PC'): '8804',
    }

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
            # Track how many times each (pt, metric) pair appears to tag cold vs warm
            pt_metric_count = {}
            with open(perf_output, 'w', newline='') as f_out:
                writer = csv.writer(f_out)
                writer.writerow(['PT', 'Metric', 'Duration'])
                for row in rows:
                    scenario_name = row.get('Scenario', '').strip()
                    metric = row.get('Metric', '').strip()
                    duration = row.get('Duration', '').strip()
                    # First try: extract PT number directly from Scenario column (e.g. "PT_8805_Office_Word_Boot v2_5f1993")
                    pt = ''
                    scenario_match = re.match(r'PT_(\d+)_', scenario_name)
                    if scenario_match:
                        pt = scenario_match.group(1)
                    # Second try: match Metric against ptscenarioname lookup
                    if not pt:
                        pt = pt_lookup.get(metric, '')
                    # Third try: prefix match for truncated metric names
                    if not pt:
                        for full_name, pt_num in pt_lookup.items():
                            if full_name.startswith(metric) or metric.startswith(full_name):
                                pt = pt_num
                                break
                    # Fourth try: match (Scenario, Metric) pair for Office Boot PTs
                    # PerfParser labels these with event-tag names, not PT scenario names
                    if not pt:
                        pt = self._scenario_metric_to_pt.get((scenario_name, metric), '')
                    # Only include metrics that match a PT in our manifest.
                    # Built-in Windows PerfTrack scenarios (not in our XML) are skipped.
                    if pt:
                        # Tag cold vs warm for Office Boot PTs (ProcessLaunch_PC)
                        key = (pt, metric)
                        count = pt_metric_count.get(key, 0)
                        pt_metric_count[key] = count + 1
                        if metric == 'ProcessLaunch_PC':
                            tag = ' (cold)' if count == 0 else f' (warm_{count})'
                            writer.writerow([pt, metric + tag, duration])
                        else:
                            writer.writerow([pt, metric, duration])
                        matched_rows.append(pt)
                    else:
                        logging.debug(f"Skipping unmatched metric: {metric}")

            logging.info(f"Perf Stress Tool - Wrote {len(matched_rows)} metrics to {perf_output} (filtered {len(rows) - len(matched_rows)} unmatched)")
            # Clean up raw file
            os.remove(raw_output)
        except Exception as e:
            logging.error(f"Error post-processing PerfMetrics CSV: {e}")
            # If post-processing fails, keep the raw output as the final output
            if os.path.isfile(raw_output) and not os.path.isfile(perf_output):
                os.rename(raw_output, perf_output)

    def testTimeoutCallback(self):
        return
