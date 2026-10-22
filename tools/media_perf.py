# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Media perf tool for post processing of Media ETL traces using Media eXperience Analyzer
# ETL trace should have been collected using MediaEngine.wprp profile

from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import logging
import sys
import os
import shutil
import csv

class Tool(Scenario):
    '''
    Deprecated.
    
    Media perf tool for post processing of Media ETL traces using Media eXperience Analyzer
    ETL trace should have been collected using MediaEngine.wprp profile
    '''
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'autoxa_path', 'C:\\"Media eXperience Analyzer\\AutoXA.exe"')
   
    # Get parameters
    autoxa_path = Params.get(module, 'autoxa_path')

    def initCallback(self, scenario):
        # Initialization code

        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        self.conn_timeout = False

        logging.info("Media Perf Tool - initializing, associated with scenario: " + self.scenario._module)
        logging.info("Media Perf Tool - result_dir: " + self.scenario.result_dir)
        return

    def testBeginCallback(self):
        return

    def testEndCallback(self):
        return

    def reportCallback(self):
        if self.conn_timeout:
            return

        # Post processing of data here.
        etl_trace = self.scenario.result_dir + "\\" + self.scenario.testname + ".etl"
        log_file_csv = "C:\\temp\\MediaDiagnostics\\MediaDiagnosticsLog.csv"
        log_file_txt = "C:\\temp\\MediaDiagnostics\\MediaDiagnosticsLog.txt"
        log_file_xml = "C:\\temp\\MediaDiagnostics\\MediaDiagnosticsLog.xml"
        logging.info("Media Perf Tool - Running autoXA on: " + etl_trace)

        if not os.path.exists ('C:\\temp\\MediaDiagnostics\\'):
            os.makedirs('C:\\temp\\MediaDiagnostics\\')

        self._host_call(self.autoxa_path + " -i " + etl_trace + " -p MediaDiagnosticsForPerf")

        table = []
        print("Reading CSV file: " + log_file_csv)
        with open(log_file_csv, 'rb') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            first_row = True
            for row in reader:
                if first_row:
                    first_row = False
                    continue
                table.append(([row[0], row[3]]))

        os.remove(log_file_csv)

        print("Writing CSV file: " + log_file_csv)
        with open(log_file_csv, 'wb') as csvfile:
            writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for row in table:
                writer.writerow(row)

        shutil.copy(log_file_csv, self.scenario.result_dir)
        shutil.copy(log_file_txt, self.scenario.result_dir)
        shutil.copy(log_file_xml, self.scenario.result_dir)

    def testTimeoutCallback(self):
        self.conn_timeout = True
