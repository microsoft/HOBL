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
import subprocess
import tempfile
import xml.etree.ElementTree as ET


# --- ETL side-channel constants -------------------------------------------------
# A subset of PerfTrack scenarios in StressUtcPerftrack.xml depend on legacy
# event sources that modern Windows builds no longer emit, so PerfParser cannot
# complete their state machines. For those metrics, an alternate provider is
# read directly from the ETL via tracerpt.
_TIP_PROVIDER_GUID = "{50109fbd-6d85-5815-731e-c907eca1607b}"
_TIP_PROVIDER_NAME = "microsoft.windows.health.testinproduction"
_TIP_TEST_CASE = "TypeToSearchTestTopResultRendered"
_TIP_COMPLETION_PASSED = "1"
_TIP_PT_NUMBER = "10010"
_TIP_METRIC_NAME = "TopResultRender"


class Tool(Scenario):
    '''
    Collects and processes UTC performance metrics for stress workloads.
    Outputs a CSV with manifest id instead of Scenario name.
    '''

    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'provider', 'GTPLight_CustomMemHardFaults.wprp', desc="WPRP file to use for UTC traces.", valOptions=["@\\providers"])
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
                # Accept PT_ and PTSdw_ scenarioname prefixes.
                match = re.match(r'PT(?:Sdw)?_(\d+)_', sname)
                if not match:
                    continue
                pt_num = match.group(1)
                if pt_name:
                    lookup[pt_name] = pt_num
                stripped_match = re.match(r'^PT(?:Sdw)?_\d+_(.+)_[^_]*$', sname)
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
        raw_output = self.scenario.result_dir + f"\\{self.module}\\" + self.scenario.testname + "_PerfMetrics_raw.csv"
        perf_output = self.scenario.result_dir + f"\\{self.module}\\" + self.scenario.testname + "_PerfMetrics.csv"
        manifest_file = "utilities\\proprietary\\ParseUtc\\StressUtcPerftrack.xml"
        os.makedirs(os.path.join(self.scenario.result_dir, self.module), exist_ok=True) # make results dir for tool outputs

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
                    scenario_match = re.match(r'PT(?:Sdw)?_(\d+)_', scenario_name)
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

        # Side-channel: extract the PT_10010 metric directly from the ETL because
        # its manifest state machine cannot complete on modern Windows builds.
        # Emits one row per passing event, matching the behavior used for the
        # other PT metrics.
        try:
            extra = self._extract_type_to_search(etl_trace)
            if extra and os.path.isfile(perf_output):
                durations_ms = []
                for d in extra:
                    try:
                        durations_ms.append(float(d))
                    except (TypeError, ValueError):
                        continue
                if durations_ms:
                    with open(perf_output, 'a', newline='') as f_out:
                        w = csv.writer(f_out)
                        for value_ms in durations_ms:
                            w.writerow([_TIP_PT_NUMBER, _TIP_METRIC_NAME, str(int(round(value_ms)))])
                    logging.info(
                        f"Perf Stress Tool - Appended {len(durations_ms)} PT_{_TIP_PT_NUMBER} "
                        f"{_TIP_METRIC_NAME} instance(s) from ETL side-channel"
                    )
        except Exception as e:
            logging.warning(f"TypeToSearch ETL side-channel extraction failed: {e}")

    @staticmethod
    def _extract_type_to_search(etl_path):
        """Return a list of durationMs strings for passing
        TypeToSearchTestTopResultRendered events found in the ETL.
        Uses tracerpt.exe to render the ETL to XML, then streams events.
        Returns [] on any failure or if no matching events are present.
        """
        if not os.path.isfile(etl_path):
            return []
        with tempfile.TemporaryDirectory() as tmp:
            out_xml = os.path.join(tmp, "etl_dump.xml")
            cmd = ["tracerpt.exe", etl_path, "-of", "XML", "-o", out_xml, "-y"]
            try:
                subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            except FileNotFoundError:
                logging.warning("tracerpt.exe not found; skipping TypeToSearch side-channel.")
                return []
            except subprocess.TimeoutExpired:
                logging.warning("tracerpt timed out on %s", etl_path)
                return []
            if not (os.path.isfile(out_xml) and os.path.getsize(out_xml) > 0):
                return []

            durations = []
            guid_lower = _TIP_PROVIDER_GUID.lower()
            try:
                for _, elem in ET.iterparse(out_xml, events=("end",)):
                    tag = elem.tag.split("}", 1)[1] if "}" in elem.tag else elem.tag
                    if tag != "Event":
                        continue
                    try:
                        provider = ""
                        data = {}
                        for child in elem:
                            ctag = child.tag.split("}", 1)[1] if "}" in child.tag else child.tag
                            if ctag == "System":
                                for sc in child:
                                    sctag = sc.tag.split("}", 1)[1] if "}" in sc.tag else sc.tag
                                    if sctag == "Provider":
                                        provider = (sc.get("Guid") or sc.get("Name") or "").lower()
                            elif ctag in ("EventData", "UserData"):
                                for d in child.iter():
                                    dtag = d.tag.split("}", 1)[1] if "}" in d.tag else d.tag
                                    name = d.get("Name")
                                    if dtag == "Data" and name is not None:
                                        data[name] = (d.text or "").strip()
                                    elif dtag not in ("EventData", "UserData") and d.text:
                                        data[dtag] = (d.text or "").strip()
                        if guid_lower not in provider and _TIP_PROVIDER_NAME not in provider:
                            continue
                        tc_name = data.get("testCaseName") or data.get("TestCaseName") or ""
                        if tc_name != _TIP_TEST_CASE:
                            continue
                        ck = data.get("completionKind") or data.get("CompletionKind") or ""
                        if ck != _TIP_COMPLETION_PASSED:
                            continue
                        dur = data.get("durationMs") or data.get("DurationMs") or ""
                        if dur:
                            durations.append(dur)
                    finally:
                        elem.clear()
            except ET.ParseError as e:
                logging.warning(f"Could not parse tracerpt XML: {e}")
                return []
            return durations

    def testTimeoutCallback(self):
        return
