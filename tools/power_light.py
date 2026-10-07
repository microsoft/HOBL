# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Produce a table of the running processes and the estimated energy they consume

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
    Collect and parse a lightweight power trace.  Does not have a significant impact on power consumption.
    '''
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'soc', '')
    Params.setDefault(module, 'wifi', '')
    Params.setDefault(module, 'cellular', '')
    Params.setDefault(module, 'memory', '')
    Params.setDefault(module, 'backlight', '')
    Params.setDefault(module, 'display', '')
    Params.setDefault(module, 'storage', '')
    Params.setDefault(module, 'camera', '')
    Params.setDefault(module, 'audio', '')
    Params.setDefault(module, 'display_light', '')
    Params.setDefault(module, 'display_logic', '')
    Params.setDefault(module, 'sam', '')
    Params.setDefault(module, 'touch', '')
    Params.setDefault(module, 'trackpad', '')
    Params.setDefault(module, 'blade', '')
    Params.setDefault(module, 'keyboard', '')
    Params.setDefault(module, 'retimers', '')
    Params.setDefault(module, 'total', '')
    Params.setDefault(module, 'total_active', '')
    Params.setDefault(module, 'total_standby', '')
    Params.setDefault(module, 'provider', 'power_light.wprp', desc="WPRP file to use for power light traces.", valOptions=["power_light.wprp", "thermal_power_light.wprp"])

    provider = Params.get(module, 'provider')


    def initCallback(self, scenario):
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        self.conn_timeout = False


        logging.info("Power light Tool - initializing, associated with scenario: " + self.scenario._module)

        # Set polling rate for Surface power monitor chips (after all reboots have happened)
        self._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SRUM\\Parameters" /v Tier1Period /t REG_DWORD /d 30 /f > null 2>&1'])
        self._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SRUM\\Parameters" /v Tier2Period /t REG_DWORD /d 120 /f > null 2>&1'])
        self._call(["cmd.exe", '/C reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\intelpep\\Parameters" /v ActiveAccountingIntervalInMs /t REG_DWORD /d 0x2710 /f > null 2>&1'])   


        # Getting global providers and adding to the list with etl_trace providers
        all_providers = Params.getCalculated('trace_providers')

        # all_providers = all_providers + " power_light.wprp"
        all_providers = all_providers + " " + self.provider
        Params.setCalculated('trace_providers', all_providers)
  
    def dataReadyCallback(self):
        if self.conn_timeout and self.rundown_mode=='0' and int(self.stop_soc) <= 0:
            return
        # ETL traces have been pulled back to the host
        # result_dir contains the full path to the results directory, and ends in <testname>_<iteration>

        etl_trace = self.scenario.result_dir + "\\" + self.scenario.testname + ".etl"
        logging.info("ETL trace: " + etl_trace)
        if not os.path.exists(etl_trace):
            logging.info("Power light Tool: Trace file not found: " + etl_trace)
            return

        logging.info("Power Light Tool - Running parse_power_light.exe on " + etl_trace)

        base_name = self.scenario.result_dir + "\\" + self.scenario.testname
        self._host_call("utilities\\proprietary\\ParsePowerLight\\parse_power_light.exe -m all -f " + etl_trace + " -o " + base_name, expected_exit_code="")

        power_light_file_path = base_name + "_power_light.csv"
        if os.path.exists(power_light_file_path):
            try:
                rails_table = pd.read_csv(power_light_file_path, header=None, index_col=0)
                rails_group = rails_table.squeeze().to_dict()

                total = self.calculateSubsystemPower(Params.get(self.module, 'total'), rails_group)
                total_active = self.calculateSubsystemPower(Params.get(self.module, 'total_active'), rails_group)
                total_standby = self.calculateSubsystemPower(Params.get(self.module, 'total_standby'), rails_group)
                soc = self.calculateSubsystemPower(Params.get(self.module, 'soc'), rails_group)
                memory = self.calculateSubsystemPower(Params.get(self.module, 'memory'), rails_group)
                wifi = self.calculateSubsystemPower(Params.get(self.module, 'wifi'), rails_group)
                cellular = self.calculateSubsystemPower(Params.get(self.module, 'cellular'), rails_group)
                display = self.calculateSubsystemPower(Params.get(self.module, 'display'), rails_group)
                backlight = self.calculateSubsystemPower(Params.get(self.module, 'backlight'), rails_group)
                storage = self.calculateSubsystemPower(Params.get(self.module, 'storage'), rails_group)
                sam = self.calculateSubsystemPower(Params.get(self.module, 'sam'), rails_group)
                touch = self.calculateSubsystemPower(Params.get(self.module, 'touch'), rails_group)
                trackpad = self.calculateSubsystemPower(Params.get(self.module, 'trackpad'), rails_group)
                retimers = self.calculateSubsystemPower(Params.get(self.module, 'retimers'), rails_group)
                blade = self.calculateSubsystemPower(Params.get(self.module, 'blade'), rails_group)
                keyboard = self.calculateSubsystemPower(Params.get(self.module, 'keyboard'), rails_group)
                camera = self.calculateSubsystemPower(Params.get(self.module, 'camera'), rails_group)
                audio = self.calculateSubsystemPower(Params.get(self.module, 'audio'), rails_group)
                display_light = self.calculateSubsystemPower(Params.get(self.module, 'display_light'), rails_group)
                display_logic = self.calculateSubsystemPower(Params.get(self.module, 'display_logic'), rails_group)
                rop, total_subsystem = 0, 0

                results = {
                    "PM SOC Power (W)": soc,
                    "PM Memory Power (W)": memory,
                    "PM WiFi Power (W)": wifi,
                    "PM Cellular Power (W)": cellular,
                    "PM Backlight Power (W)": backlight,
                    "PM Display Power (W)": display,
                    "PM Storage Power (W)": storage,
                    "PM SAM Power (W)": sam,
                    "PM Touch Power (W)": touch,
                    "PM Trackpad Power (W)": trackpad,
                    "PM Retimers Power (W)": retimers,
                    "PM Blade Power (W)": blade,
                    "PM Camera Power (W)": camera,
                    "PM Keyboard Power (W)": keyboard,
                    "PM Audio Power (W)": audio,
                    "PM Display Light Power (W)": display_light,
                    "PM Display Logic Power (W)": display_logic,
                    # "PM Total Power (W)": total,
                    # "PM Total Active Power (W)": total_active,
                    # "PM Total Standby Power (W)": total_standby
                }

                append_rop = True
                for k, v in list(results.items()):
                    if results[k] == float('-inf'):
                        del results[k]
                        append_rop = False
                    else:
                        total_subsystem += results[k]

                if append_rop and total != float('-inf'):
                    results["PM ROP Power (W)"] = total - total_subsystem
                
                # Append totals
                if total != float('-inf'):
                    results["PM Total Power (W)"] = total
                if total_active != float('-inf'):
                    results["PM Total Active Power (W)"] = total_active
                if total_standby != float('-inf'):
                    results["PM Total Standby Power (W)"] = total_standby

                outfile = self.scenario.result_dir + "\\" + self.scenario.testname + "_power_light_summary.csv"
                pd.DataFrame.from_dict(results, orient='index').to_csv(outfile, float_format='%0.3f', header=False)

            except:
                logging.error("Could not read *power_light.csv file for parsing.")
        else:
            logging.debug("*power_light.csv file doesn't exist.")

    def testTimeoutCallback(self):
        self.conn_timeout = True

    def calculateSubsystemPower(self, rails, rails_group):
        subsystem_power = 0
        if rails != "" and rails != None:
            rail_list = re.split(r"[ |]+", rails)
            for rail in rail_list:
                if rail.strip() in rails_group:
                    # logging.debug(f"Calculating rail: {rail.strip()}")
                    subsystem_power += rails_group[rail.strip()]
                else:
                    logging.debug("Power Light Tool: rail name [" + rail.strip() + "] doesn't match name in power_light.csv file")
                    return float('-inf')
        else:
            subsystem_power = float('-inf')

        return subsystem_power
