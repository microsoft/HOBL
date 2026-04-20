# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Powercfg tool

from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import logging
import sys
import os
import csv
import xml.etree.ElementTree as ET


class Tool(Scenario):
    '''
    Collect sleep study and battery reports.
    '''
    module = __module__.split('.')[-1]
    # Set default parameters
    #Params.setDefault(module, 'delay', '0')
    #Params.setDefault(module, 'duration', '10')
    # Params.setDefault(module, 'additional_args', '/SLEEPSTUDY /OUTPUT c:\\hobl_data\\sleepstudy.html')
    Params.setDefault(module, 'battery_report', '1')

    # Get parameters
    #delay = Params.get(module, 'delay')
    #duration = Params.get(module, 'duration')
    # additional_args = Params.get(module, 'additional_args')
    battery_report = Params.get(module, 'battery_report')
    platform = Params.get('global', 'platform')

    def initCallback(self, scenario):
        # Initialization code
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        return

    def testBeginCallback(self):
        pass
    
    def testEndCallback(self):
        output_file_xml = '\\sleepstudy-report.xml /XML'
        battery_file_xml = '\\battery-report.xml /XML'
        output_file_html = '\\sleepstudy-report.html'
        battery_file_html = '\\battery-report.html'

        self._call(["cmd.exe", "/C powercfg.exe /SLEEPSTUDY /VERBOSE /DURATION 5 /OUTPUT " + self.scenario.dut_data_path + output_file_xml], expected_exit_code="", fail_on_exception=False)
        if self.platform.lower() != "wcos":
            self._call(["cmd.exe", "/C powercfg.exe /SLEEPSTUDY /VERBOSE /DURATION 5 /OUTPUT " + self.scenario.dut_data_path + output_file_html], expected_exit_code="", fail_on_exception=False)
        if self.battery_report  == '1':
            self._call(["cmd.exe", "/C powercfg.exe /BATTERYREPORT /DURATION 5 /OUTPUT " + self.scenario.dut_data_path + battery_file_xml], expected_exit_code="", fail_on_exception=False)
            if self.platform.lower() != "wcos":
                self._call(["cmd.exe", "/C powercfg.exe /BATTERYREPORT /DURATION 5 /OUTPUT " + self.scenario.dut_data_path + battery_file_html], expected_exit_code="", fail_on_exception=False)
        self._call(["cmd.exe", "/C powercfg.exe /SRUMUTIL /OUTPUT " + self.scenario.dut_data_path + "\\srumutil.csv"], expected_exit_code="", fail_on_exception=False)

        # if self.platform.lower() == "wcos":
        #     self._copy_data_from_remote(self.scenario.result_dir)
        #     self._host_call('%SystemRoot%\\sysnative\\WindowsPowerShell\\v1.0\\powershell.exe cmd.exe /c powercfg.exe /sleepstudy /transformxml ' 
        #                     + self.scenario.result_dir + '\\sleepstudy-report.xml /output ' + self.scenario.result_dir + '\\sleepstudy-report.html')
            
        #     if self.battery_report  == '1':
        #         self._host_call('%SystemRoot%\\sysnative\\WindowsPowerShell\\v1.0\\powershell.exe cmd.exe /c powercfg.exe /batteryreport /transformxml \"' 
        #                         + self.scenario.result_dir + '\\battery-report.xml /output ' + self.scenario.result_dir + '\\battery_report.html')

    def dataReadyCallback(self):
        # You can do any post processing of data here.
        if self.platform.lower() == "wcos":
            self._host_call('%SystemRoot%\\sysnative\\WindowsPowerShell\\v1.0\\powershell.exe cmd.exe /c powercfg.exe /sleepstudy /transformxml ' 
                                + self.result_dir + '\\sleepstudy-report.xml /output ' + self.result_dir + '\\sleepstudy-report.html')
            if self.battery_report  == '1':
                    self._host_call('%SystemRoot%\\sysnative\\WindowsPowerShell\\v1.0\\powershell.exe cmd.exe /c powercfg.exe /batteryreport /transformxml \"' 
                                    + self.scenario.result_dir + '\\battery-report.xml /output ' + self.scenario.result_dir + '\\battery_report.html')
        else:
            sleep_study_path = os.path.join(self.result_dir, 'sleepstudy-report.xml')
            root = ET.parse(sleep_study_path).getroot()
            ns_prefix = root.tag.split('{')[1].split('}')[0]
            # ns = {'name_space': 'http://schemas.microsoft.com/sleepstudy/2012'}
            ns = {'name_space': ns_prefix}

            drips_under_percentage = 0
            drips_average = 0
            total_percentage = 0 
            count_drips = 0
            for buckets in root.findall('.//name_space:DripsBuckets',ns):
                ele = buckets.find('name_space:DripBucketId', ns)
                drip_percentage = 0
                for bucket in buckets.findall(".//name_space:DripsBucket", ns):
                    drip_percentage += int(bucket.get('TotalTimePercent'))
                total_percentage = total_percentage + drip_percentage
                count_drips = count_drips+1
                if drip_percentage < 80 :
                    drips_under_percentage = drips_under_percentage+1

            if count_drips != 0:
                drips_average = total_percentage // count_drips

            drips_csv = os.path.join(self.result_dir, "drips.csv")
            logging.info(drips_csv)
            row1 = ['Drips Average %', drips_average]
            row2 = ['Drips Session Under %80', drips_under_percentage]
            with open(drips_csv, 'w') as csvfile:
                writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
                writer.writerow(row1)
                writer.writerow(row2)
        pass
