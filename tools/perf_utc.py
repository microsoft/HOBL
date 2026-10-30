# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Tool for collecting and processing UTC performance data

from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import csv
from decimal import Decimal, InvalidOperation
import logging
import os


class Tool(Scenario):
    '''
    Collects and processes UTC Perftrack scenarios
    '''

    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'provider', 'perf_utc.wprp', desc="WPRP file to use for UTC Perftrack traces.", valOptions=["@\\providers"])
    Params.setDefault(module, 'cm', '0', desc="Use the ConsumerMultitaskerPTs.xml manifest.")
    # Get parameters
    provider = Params.get(module, 'provider')
    cm = Params.get(module, 'cm')
    exception_metrics = ["PerfCodeMarker_ExcelPdfExport_PrintPage", "PerfCodeMarker_PowerPointLaunch_Open"]
    summation_metrics = ["PerfCodeMarker_PowerPointR3ExportPDF_PrintPage"]

    def initCallback(self, scenario):
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        self.conn_timeout = False

        # Getting global providers and adding to the list with etl_trace providers
        all_providers = Params.getCalculated('trace_providers')

        all_providers = all_providers + " " + self.provider
        if self.cm == '1':
            all_providers = all_providers + " utc_codemarkers.wprp"
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

        if self.cm == '1':
            manifest_file = "utilities\\proprietary\\ParseUtc\\ConsumerMultitaskerPTs.xml"

        logging.info("Perf Tool - Running PerfParser on " + etl_trace)

        self._host_call("utilities\\proprietary\\ParseUtc\\PerfParser.exe " + etl_trace + " " + manifest_file + " " + perf_output )

        if self.cm == '1':
            codemarker_output = perf_output + ".codemarker.tmp"
            self._host_call(
                '"utilities\\proprietary\\ParseCodeMarkers\\cmparser.exe" "' + etl_trace +
                '" --manifest "utilities\\proprietary\\ParseCodeMarkers\\CMEvents.xml" --output "' +
                codemarker_output + '"'
            )
            with open(perf_output, "ab+") as perf_file, open(codemarker_output, "rb") as codemarker_file:
                perf_file.seek(0, os.SEEK_END)
                if perf_file.tell() > 0:
                    perf_file.seek(-1, os.SEEK_END)
                    if perf_file.read(1) not in (b"\n", b"\r"):
                        perf_file.write(b"\r\n")
                perf_file.write(codemarker_file.read())
            os.remove(codemarker_output)

        self._processMetrics(perf_output)

    def _processMetrics(self, perf_output):
        temporary_output = perf_output + ".tmp"

        try:
            with open(perf_output, "r", newline="") as perf_file:
                reader = csv.reader(perf_file)
                rows = list(reader)

            if not rows:
                return

            header = None
            normalized_first_row = [column.strip().lower() for column in rows[0]]
            if "metric" in normalized_first_row and "duration" in normalized_first_row:
                header = rows.pop(0)
                metric_index = normalized_first_row.index("metric")
                duration_index = normalized_first_row.index("duration")
            elif len(rows[0]) >= 2:
                metric_index = 0
                duration_index = 1
            else:
                raise ValueError("Perf metrics CSV must contain Metric and Duration columns.")

            exception_metrics = set(self.exception_metrics)
            summation_metrics = set(self.summation_metrics)
            processed_rows = []
            summed_rows = {}
            summed_durations = {}

            for row in rows:
                if not row or (header is not None and row == header):
                    continue
                if len(row) <= max(metric_index, duration_index):
                    raise ValueError("Perf metrics CSV contains an incomplete row: " + str(row))

                metric = row[metric_index].strip()
                if metric in exception_metrics:
                    continue

                if metric in summation_metrics:
                    try:
                        duration = Decimal(row[duration_index].strip())
                    except InvalidOperation as error:
                        raise ValueError("Invalid duration for summation metric " + metric + ": " + row[duration_index]) from error

                    if metric not in summed_rows:
                        summed_rows[metric] = row
                        summed_durations[metric] = duration
                        processed_rows.append(row)
                    else:
                        summed_durations[metric] += duration
                    continue

                processed_rows.append(row)

            for metric, row in summed_rows.items():
                row[duration_index] = format(summed_durations[metric], "f")

            regular_rows = [
                row for row in processed_rows
                if "InputProcessDelay" not in row[metric_index]
            ]
            input_delay_rows = [
                row for row in processed_rows
                if "InputProcessDelay" in row[metric_index]
            ]

            with open(temporary_output, "w", newline="") as output_file:
                writer = csv.writer(output_file)
                if header is not None:
                    writer.writerow(header)
                writer.writerows(regular_rows + input_delay_rows)

            os.replace(temporary_output, perf_output)
        finally:
            if os.path.exists(temporary_output):
                os.remove(temporary_output)

    def testTimeoutCallback(self):
        self.conn_timeout = True
