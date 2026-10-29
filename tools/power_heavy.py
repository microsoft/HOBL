# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Parses power heavy traces for different telemetry specified by the user

from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import pandas as pd
import logging
import sys
import os
import re


class Tool(Scenario):
    '''
    Collect and parse a detailed power trace.  Has a significant impact on power consumption.
    '''
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'soc', '')
    Params.setDefault(module, 'wifi', '')
    Params.setDefault(module, 'memory', '')
    Params.setDefault(module, 'display', '')
    Params.setDefault(module, 'storage', '')
    Params.setDefault(module, 'total', '')
    Params.setDefault(module, 'total_active', '')
    Params.setDefault(module, 'total_standby', '')


    def initCallback(self, scenario):
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        self.conn_timeout = False
        if Params.get("global", "local_execution") == "0":
            # For remote execution, use the cmd.exe that matches the OS
            cmd = "cmd.exe"
        else:
            # For local execution, since this is 32b Python, we need to explicitly specify the native cmd.exe
            cmd = "c:\\windows\\sysnative\\cmd.exe"

        logging.info("Power Heavy Tool - initializing, associated with scenario: " + self.scenario._module)

        # Set polling rate for Surface power monitor chips (after all reboots have happened)
        self._call([cmd, '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SRUM\\Parameters" /v Tier1Period /t REG_DWORD /d 30 /f > null 2>&1'])
        self._call([cmd, '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SRUM\\Parameters" /v Tier2Period /t REG_DWORD /d 120 /f > null 2>&1'])
        self._call([cmd, '/C reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\intelpep\\Parameters" /v ActiveAccountingIntervalInMs /t REG_DWORD /d 0x2710 /f > null 2>&1'])   

        # Getting global providers and adding to the list with etl_trace providers
        all_providers = Params.getCalculated('trace_providers')

        all_providers = all_providers + " power_heavy.wprp" 
        Params.setCalculated('trace_providers', all_providers)

  
    def dataReadyCallback(self):
        if self.conn_timeout:
            return
        # ETL traces have been pulled back to the host
        # result_dir contains the full path to the results directory, and ends in <testname>_<iteration>

        etl_trace = self.scenario.result_dir + "\\" + self.scenario.testname + ".etl"
        logging.info("ETL trace: " + etl_trace)
        if not os.path.exists(etl_trace):
            logging.info("Power Heavy Tool: Trace file not found: " + etl_trace)
            return

        logging.info("Power Heavy Tool - Running Parse_power_heavy.exe on " + etl_trace)

        # Create output dir for power_heavy results
        output_path = os.path.join(self.scenario.result_dir, self.module)
        os.makedirs(output_path, exist_ok=True)

        output_name = output_path + "\\" + self.scenario.testname
        base_name = self.scenario.result_dir + "\\" + self.scenario.testname
        self._host_call("utilities\\proprietary\\ParsePowerHeavy\\Parse_power_heavy.exe -m all -i " + etl_trace + " -o " + output_name, expected_exit_code="")

        # Create a list of files that need to be processed for roll_up metrics
        roll_up_file_path = os.path.relpath(output_name, self.scenario.result_dir)
        files_to_process = [roll_up_file_path + "_power_heavy_summary.csv"]
        # Append files to process to the roll-up list, creating it if needed.
        roll_up_file = os.path.join(self.scenario.result_dir, "roll_up_files.txt")
        with open(roll_up_file, "a") as f:
            for file in files_to_process:
                f.write(file + "\n")
    #     power_light_file_path = base_name + "_power_light.csv"
    #     if os.path.exists(power_light_file_path):
    #         try:
    #             rails_group = pd.read_csv(power_light_file_path, header=None, index_col=0, squeeze=True).to_dict()

    #             total = self.calculateSubsystemPower(Params.get(self.module, 'total'), rails_group)
    #             total_active = self.calculateSubsystemPower(Params.get(self.module, 'total_active'), rails_group)
    #             total_standby = self.calculateSubsystemPower(Params.get(self.module, 'total_standby'), rails_group)
    #             soc = self.calculateSubsystemPower(Params.get(self.module, 'soc'), rails_group)
    #             memory = self.calculateSubsystemPower(Params.get(self.module, 'memory'), rails_group)
    #             wifi = self.calculateSubsystemPower(Params.get(self.module, 'wifi'), rails_group)
    #             display = self.calculateSubsystemPower(Params.get(self.module, 'display'), rails_group)
    #             storage = self.calculateSubsystemPower(Params.get(self.module, 'storage'), rails_group)
    #             rop, total_subsystem = 0, 0

    #             results = {
    #                 "PM SOC Power (W)": soc,
    #                 "PM Memory Power (W)": memory,
    #                 "PM WiFi Power (W)": wifi,
    #                 "PM Display Power (W)": display,
    #                 "PM Storage Power (W)": storage
    #                 # "PM Total Power (W)": total,
    #                 # "PM Total Active Power (W)": total_active,
    #                 # "PM Total Standby Power (W)": total_standby
    #             }

    #             append_rop = True
    #             for k, v in list(results.items()):
    #                 if results[k] == float('-inf'):
    #                     del results[k]
    #                     append_rop = False
    #                 else:
    #                     total_subsystem += results[k]

    #             if append_rop and total != float('-inf'):
    #                 results["PM ROP Power (W)"] = total - total_subsystem
                
    #             # Append totals
    #             if total != float('-inf'):
    #                 results["PM Total Power (W)"] = total
    #             if total_active != float('-inf'):
    #                 results["PM Total Active Power (W)"] = total_active
    #             if total_standby != float('-inf'):
    #                 results["PM Total Standby Power (W)"] = total_standby

    #             outfile = self.scenario.result_dir + "\\" + self.scenario.testname + "_power_light_summary.csv"
    #             pd.DataFrame.from_dict(results, orient='index').to_csv(outfile, float_format='%0.3f', header=False)

    #         except:
    #             logging.error("Could not read *power_light.csv file for parsing.")
    #     else:
    #         logging.debug("*power_light.csv file doesn't exist.")

    # def testTimeoutCallback(self):
    #     self.conn_timeout = True

    # def calculateSubsystemPower(self, rails, rails_group):
    #     subsystem_power = 0
    #     if rails != "" and rails != None:
    #         rail_list = re.split(r"[ |]+", rails)
    #         for rail in rail_list:
    #             try:
    #                 subsystem_power += rails_group[rail.strip()]
    #             except:
    #                 logging.debug("Power Light Tool: rail name [" + rail.strip() +  "] doesn't match name in power_light.csv file")
    #                 return float('-inf')
    #     else:
    #         subsystem_power = float('-inf')

    #     return subsystem_power
