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
    Params.setDefault(module, 'provider', 'GTPLight_CustomMemHardFaults.wprp', desc="WPRP file to use for UTC Perftrack traces.", valOptions=["@\\providers"])
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
        """Parse the manifest XML and build a dict mapping Metric -> PT_XXXX.

        Two keys are added per scenario:
          1. The manifest `ptscenarioname` attribute (legacy path).
          2. The parser-stripped form of `scenarioname`, mimicking PerfParser.cs:
                ptName = sname.Substring(IndexOf("PT_")+3, LastIndexOf("_")-3)
                ptName = ptName.Substring(IndexOf("_")+1)
             i.e. drop the "PT_<num>_" prefix and the "_<6hex>" suffix.
        Adding (2) makes the join robust to drift between `ptscenarioname` and the
        actual DiagTrack-emitted scenario name (e.g. PT_8998 manifest claims
        "Edge Startup Stable _Shell Click __ First Render NonEmptyPaint2_" but the
        parser emits "Edge Startup Stable _Shell Click __ First Render ").
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
                # Parser-stripped form of scenarioname.
                stripped_match = re.match(r'^PT_\d+_(.+)_[^_]*$', sname)
                if stripped_match:
                    parser_form = stripped_match.group(1)
                    if parser_form:
                        lookup.setdefault(parser_form, pt_num)
                        # Also index a whitespace-trimmed variant in case the parser
                        # output is later normalized. setdefault avoids overwriting
                        # a more authoritative ptscenarioname mapping.
                        trimmed = parser_form.strip()
                        if trimmed and trimmed != parser_form:
                            lookup.setdefault(trimmed, pt_num)
        except Exception as e:
            logging.warning(f"Could not parse manifest for PT lookup: {e}")
        return lookup

    # PerfParser writes one of two things into the Scenario column:
    #   1. The full PT scenario name from the manifest, e.g.
    #        "PT_1809_Open Start Menu_9a700f"
    #      (used for PTs whose triggers fire outside an injected event-tag window)
    #   2. The HOBL etw_event_tag value, e.g. "ExcelLaunch", "BrowserLaunch"
    #      (used for measurements taken inside an EventTag InputInject window)
    #
    # The Metric column always carries the PT's `ptscenarioname` from the manifest
    # (e.g. "Office_XL_Boot v2", "Open Start Menu", "Snipping Tool Overlay Launch
    # Performance"), so we can recover the PT number purely via string ops:
    #   - regex extract from Scenario when it's the PT_XXXX form
    #   - else look up Metric against the manifest ptscenarioname -> PT_XXXX map
    # No hand-curated (event_tag, metric) -> PT table is needed (and would be wrong
    # anyway, because a single event_tag window can contain many unrelated metrics).

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
                    # First try: extract PT number directly from Scenario column
                    # (e.g. "PT_1809_Open Start Menu_9a700f" -> 1809)
                    pt = ''
                    scenario_match = re.match(r'PT_(\d+)_', scenario_name)
                    if scenario_match:
                        pt = scenario_match.group(1)
                    # Second try: look up Metric against manifest ptscenarioname
                    # (e.g. Metric "Office_XL_Boot v2" -> PT_8806). This handles
                    # rows where Scenario is an injected etw_event_tag rather than
                    # the PT name itself.
                    if not pt:
                        pt = pt_lookup.get(metric, '')
                    # Only include metrics whose PT is in our manifest. Built-in
                    # Windows PerfTrack scenarios not in our XML are skipped.
                    if pt:
                        writer.writerow([pt, metric, duration])
                        matched_rows.append(pt)
                    else:
                        logging.debug(f"Skipping unmatched metric: {metric}")

            logging.info(f"Perf Stress Tool - Wrote {len(matched_rows)} metrics to {perf_output} (filtered {len(rows) - len(matched_rows)} unmatched)")
            # Keep raw_output so the operator can see ALL PTs PerfParser found,
            # including those filtered by manifest whitelisting and those PerfParser
            # detected but our XML doesn't track. Useful for tuning the manifest and
            # diagnosing PT loss under stress.
        except Exception as e:
            logging.error(f"Error post-processing PerfMetrics CSV: {e}")
            # If post-processing fails, keep the raw output as the final output
            if os.path.isfile(raw_output) and not os.path.isfile(perf_output):
                os.rename(raw_output, perf_output)

    def testTimeoutCallback(self):
        return
