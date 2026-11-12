# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# study_report
# 
# Generates a report of the current study.  Can be run repeatedly befor study complets.
#
# Setup instructions:
##

import builtins
import logging
from core.app_scenario import Scenario
from core.parameters import Params
import os.path
import shutil

class Tool(Scenario):
    '''
    Generate a report for the study (all runs in the same study directory).
    '''
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'result_path', '')
    Params.setDefault(module, 'template', 'docs\\hobl_study_report_template.xlsx')
    Params.setDefault(module, 'weights', '')
    Params.setDefault(module, 'trend', '')
    Params.setDefault(module, 'goals', '')
    Params.setDefault(module, 'adders', '')
    Params.setDefault(module, 'name', '')
    Params.setDefault(module, 'active_target', '')
    Params.setDefault(module, 'hobl_target', '')
    Params.setDefault(module, 'battery_capacity', '')  # Capacity in Wh
    Params.setDefault(module, 'battery_min_capacity', '')  # Minimum Capacity in Wh
    Params.setDefault(module, 'battery_derating', '')  # Fraction of battery than can not be consumed
    Params.setDefault(module, 'battery_reserve', '')  # Fraction of battery than can not be consumed
    Params.setDefault(module, 'os_shutdown_reserve', '')
    Params.setDefault(module, 'hibernate_timeout', '')  # Hours of standby before Hibernate is activated
    Params.setDefault(module, 'hibernate_budget_target', '')  # Percentage of battery allowed to drain in standby during hibernate_timeout period
    Params.setDefault(module, 'device_name', '')
    Params.setDefault(module, 'comments', '')
    Params.setDefault(module, 'csv_path', '')
    Params.setDefault(module, 'enable_phase_report', '1')
    Params.setDefault(module, 'uploader', '')


    def initCallback(self, scenario):
        # Initialization code
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario

        # Get parameters
        self.result_path = Params.get(self.module, 'result_path')
        self.template = Params.get(self.module, 'template')
        self.weights = Params.get(self.module, 'weights')
        self.trend = Params.get(self.module, 'trend')
        self.goals = Params.get('global', 'goals')
        if self.goals == "" or self.goals == None:
            self.goals = Params.get(self.module, 'goals')
        self.adders = Params.get(self.module, 'adders')
        self.name = Params.get(self.module, 'name')
        self.active_target = Params.get(self.module, 'active_target')
        self.hobl_target = Params.get(self.module, 'hobl_target')
        self.battery_capacity = Params.get(self.module, 'battery_capacity')
        self.battery_min_capacity = Params.get(self.module, 'battery_min_capacity')
        self.battery_derating = Params.get(self.module, 'battery_derating')
        self.battery_reserve = Params.get(self.module, 'battery_reserve')
        self.os_shutdown_reserve = Params.get(self.module, 'os_shutdown_reserve')
        self.hibernate_timeout = Params.get(self.module, 'hibernate_timeout')
        self.hibernate_budget_target = Params.get(self.module, 'hibernate_budget_target')
        self.product = Params.get('global', 'product')
        self.study_type = Params.get('global', 'study_type')
        self.device_name = Params.get(self.module, 'device_name')
        self.comments = Params.get(self.module, 'comments')
        self.csv_path = Params.get(self.module, 'csv_path')
        self.local_execution = Params.get('global', 'local_execution')
        self.enable_phase_report = Params.get(self.module, 'enable_phase_report')
        self.uploader = Params.get(self.module, 'uploader')
        self.dashboard_url = Params.get('global', 'dashboard_url')

    def reportCallback(self):    
        logging.info("Generating Study Report")
        '''
        self.result_path = Params.resolveVars(self.result_path)
        cmd = ".\\hobl.cmd -e utilities.gen_study_report " + self.result_path + " -html_only 1 -template " + self.template + " -enable_phase_report " + self.enable_phase_report
        # if self.trend is not '':
        #     cmd += " -trend " + self.trend
        #     cmd += " -a " + self.active_target
        #     cmd += " -tt " + self.telemetry_target
        #     cmd += " -o " + self.hobl_target
        if self.battery_capacity != '':
            cmd += " -b " + self.battery_capacity
        if self.battery_derating != '':
            cmd += " -bd " + self.battery_derating
        if self.battery_reserve != '':
            cmd += " -r " + self.battery_reserve
        if self.hibernate_timeout != '':
            cmd += " -ht " + self.hibernate_timeout
        if self.hibernate_budget_target != '':
            cmd += " -hbt " + self.hibernate_budget_target
        if self.goals != '':
            cmd += " -goals " + '"' + self.goals + '"'
        if self.adders != '':
            cmd += " -adders " + self.adders
        if self.name != '':
            cmd += " -name " + self.name
        if self.product != '':
            cmd += " -product " + '"' + self.product + '"'
        if self.study_type != '':
            cmd += " -study_type " + '"' + self.study_type + '"'
        if self.device_name != '':
            cmd += " -device_name " + '"' + self.device_name + '"'
        if self.comments != '':
            cmd += " -comments " + '"' + self.comments + '"'

        # logging.info("Study report command: " + cmd)
        # res = self._host_call(cmd, expected_exit_code = "")
        res = self._host_call(cmd)
        if "ERROR" in res:
            logging.error("Study report failed.")
        else:
            logging.info("Study report generated in " + self.result_path)
        '''

        # Get the current scenario name
        parts = self.scenario.result_dir.split("\\")
        current_scenario = "\\".join(parts[-2:])

        # Call the json study report
        if (self.result_path == ''):
            # self.result_path = Params.get('global', 'result_dir')
            self.result_path = Params.getCalculated("study_result_dir")
        cwd2 = os.path.abspath(os.getcwd())
        cmd = cwd2 + "\\hobl.cmd -e utilities.open_source.gen_study_report_json " + self.result_path + " -dashboard_url " + self.dashboard_url + " -current_run " + current_scenario
        
        # copy goals, adders, and weights template to the result path under study_report_params folder. Create text file with command for reference.
        study_report_params_dir = os.path.join(self.result_path, "study_report_params")
        os.makedirs(study_report_params_dir, exist_ok=True)

        if self.goals != '':
            shutil.copy2(self.goals, os.path.join(study_report_params_dir, "goals.csv"))
            self.goals = os.path.join(study_report_params_dir, "goals.csv")
        if self.adders != '':
            shutil.copy2(self.adders, os.path.join(study_report_params_dir, "adders.csv"))
            self.adders = os.path.join(study_report_params_dir, "adders.csv")
        if self.weights != '':
            shutil.copy2(self.weights, os.path.join(study_report_params_dir, "template.json"))
            self.weights = os.path.join(study_report_params_dir, "template.json")
        

        if self.active_target != '':
            cmd += " -a " + self.active_target
        if self.hobl_target != '':
            cmd += " -o " + self.hobl_target
        if self.battery_capacity != '':
            cmd += " -b " + self.battery_capacity
        if self.battery_derating != '':
            cmd += " -bd " + self.battery_derating
        if self.battery_reserve != '':
            cmd += " -r " + self.battery_reserve
        if self.os_shutdown_reserve != '':
            cmd += " -sr " + self.os_shutdown_reserve
        if self.hibernate_budget_target != '':
            cmd += " -hbt " + self.hibernate_budget_target
        if self.goals != '':
            cmd += " -goals " + '"' + self.goals + '"'
        if self.adders != '':
            cmd += " -adders " +  '"' + self.adders + '"'
        # if self.name != '':
        #     cmd += " -name " + self.name
        if self.study_type != '':
            cmd += " -study_type " + '"' + self.study_type + '"'
        if self.device_name != '':
            cmd += " -device_name " + '"' + self.device_name + '"'
        if self.comments != '':
            cmd += " -comments " + '"' + self.comments + '"'
        if self.template != '':
            cmd += " -template " + '"' + self.weights + '"'
        
        # Set the study name
        report_name = ''
        if self.name != '':
            report_name = self.name.replace(".xlsx", ".json")
        elif self.device_name != '':
            report_name = self.result_path.split('\\')[-1] + '_' + self.device_name + "_study_report.json"
        else:
            report_name = self.result_path.split('\\')[-1] + "_study_report.json"
        cmd += " -name " + report_name

        # logging.info("Study report command: " + cmd)
        res = self._host_call(cmd)
        if "Closing gracefully" not in res:
            if "ERROR" in res:
                self.fail("Study report failed.")
            else:
                logging.info("Study report json generated in " + report_name)
                if self.uploader != '' and self.uploader != None:
                    if os.path.exists(self.uploader):
                        command = f'python.exe {self.uploader} {os.path.join(self.result_path, report_name)}'
                        logging.info("uploading study report cmd: " + command)
                        self._host_call(command)
        else:
            logging.debug("Skipping generating JSON study report")

        with open(os.path.join(study_report_params_dir, "report_call_cmd.txt"), 'w') as file:
            file.write(cmd)

    def cleanup(self):
        # Can't kill Excel process because another scenario may be running simultaneously on the same host that is using it.
        # self._host_kill("Excel.exe")
        return
