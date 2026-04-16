# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Run prep scenarios for specified scenarios
##

import importlib.util
import inspect
import logging
import subprocess
import sys
import os
import requests
from urllib.parse import urlparse, urlunparse
import time

import core.app_scenario
from core.parameters import Params
from utilities.open_source.modules import get_parent_modules


class Prep(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]

    Params.setDefault('prep', 'common_preps',      'msa_prep system_prep store_prep surface_app_prep adaptive_color_disable', desc='List of common prep scenarios to run, if needed', multiple=True)
    Params.setDefault('prep', 'scenarios_to_prep', '', desc='List of scenarios to run prep for, if needed', multiple=True)
    Params.setDefault('prep', 'additional_preps',  '', desc='List of additional prep scenarios to run',     multiple=True)

    Params.setOverride('global', 'tools', '')
    Params.setOverride('global', 'prep_tools', '')
    Params.setOverride('global', 'collection_enabled', '0')
    Params.setOverride('global', 'post_run_delay', '0')  # Important to be fast in common case where no preps need to be run.

    common_preps      = Params.get('prep', 'common_preps').split()
    scenarios_to_prep = Params.get('prep', 'scenarios_to_prep').split()
    additional_preps  = Params.get('prep', 'additional_preps').split()

    run_dir     = Params.getCalculated('run_dir')
    params_file = Params.getCalculated('params_file')

    hobl_external = Params.get('global', 'hobl_external').split()

    is_prep = True

    def get_prep_scenarios(self):
        parent_modules = get_parent_modules(["scenarios"], ext_paths=self.hobl_external)

        prep_scenarios = []

        if Params.get('global', 'platform').lower() == "windows":
            prep_scenarios.extend(
                self.checkPrepStatusNew(self.common_preps)
            )

        for scenario in self.scenarios_to_prep:
            for parent_module in parent_modules:
                module = f"{parent_module}.{scenario}"

                try:
                    spec = importlib.util.find_spec(module)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    for _, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, core.app_scenario.Scenario):
                            prep_scenarios.extend(
                                self.checkPrepStatusNew(getattr(obj, 'prep_scenarios', []))
                            )
                except:
                    pass

        prep_scenarios.extend(self.additional_preps)

        unique_prep_scenarios = []
        for p in prep_scenarios:
            if p not in unique_prep_scenarios:
                unique_prep_scenarios.append(p)

        return unique_prep_scenarios

    def setUp(self):
        return

    def runTest(self):
        if self.scenarios_to_prep == ["comm_check"]:
            logging.info("comm_check specified, skipping prep scenarios and running comm check only.")
            return
        
        self.checkLocalExecution()

        prep_scenarios = self.get_prep_scenarios()

        if len(prep_scenarios) == 0:
            logging.info("No preps to run")
        else:
            for p in prep_scenarios:
                if isinstance(p, tuple):
                    if isinstance(p[1], list):
                        logging.info(f"Running Prep: {p[0]} version = file dependencies")
                    else:
                        logging.info(f"Running Prep: {p[0]} version = {p[1]}")
                else:
                    logging.info(f"Running Prep: {p}")

        failing_scenario = None

        for p in prep_scenarios:
            if isinstance(p, tuple):
                s = p[0]
            else:
                s = p

            result = subprocess.run([
                ".\\hobl.cmd",
                "-p", self.params_file,
                "-s", s,
                f"global:result_dir_complete={self.run_dir}",
                "global:prep_run_only=1",
                "global:attempts=2",
                "global:post_run_delay=0"
            ])

            if result.returncode != 0 and not failing_scenario:
                failing_scenario = s
            time.sleep(10)

        self.postLocalExecution()

        # Delete to prevent this scenario from copying over the last prep data files during teardown
        self._remote_make_dir(self.dut_data_path, True)

        if failing_scenario:
            self.error_fail(f"Prep scenario {failing_scenario} failed")

    def tearDown(self):
        return

    def kill(self):
        prep_scenarios = self.get_prep_scenarios()

        for p in prep_scenarios:
            if isinstance(p, tuple):
                s = p[0]
            else:
                s = p

            subprocess.run([
                ".\\hobl.cmd",
                "-p", self.params_file,
                "-k", s
            ])

        return 0

    def checkLocalExecution(self):
        # Checks if it's local execution and will pause plan if neccessary and set registry to run prep scenario again after reboot.
        if self.dut_ip == "127.0.0.1" and self.platform.lower() == "windows":
            dashboard_url = Params.get('global', 'dashboard_url')
            hobl_path = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))

            if dashboard_url == "":
                hobl_path = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
                #combine sys.argv into a string 
                arguments = " ".join(sys.argv[1:])
                post_reboot_call = os.path.join(hobl_path, "hobl.cmd") + " " + arguments

                # Write to RunOnce registry to execute after reboot
                reg_cmd = f'reg.exe add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce" /v LocalExec_PostReboot /t REG_SZ /d "{post_reboot_call}" /f'
                self._call(["cmd.exe", "/c " + reg_cmd])
            else:
                # if were running server then we need to "trick" server into setting prep.py to pending/pending so when it reboots it will run prep again. 
                dashboard_plan_id = Params.get('global', 'dashboard_plan_id')
                dashboard_scenario_id = Params.get('global', 'dashboard_scenario_id')

                url = urlunparse(
                    urlparse(dashboard_url)._replace(
                        path='/plan/PausePlan',
                        query=f"PlanIDs={dashboard_plan_id}"
                    )
                )

                requests.get(url, allow_redirects=False)

                # Build the post-reboot command to run the wait_and_resume_plan.ps1 script
                base_url = urlunparse(urlparse(dashboard_url)._replace(path='',query='', fragment=''))

                # post_reboot_script = r"C:\hobl_bin\wait_and_resume_plan.ps1"
                post_reboot_script = os.path.join(hobl_path, "utilities", "open_source", "wait_and_resume_plan.ps1")
                post_reboot_call = f'powershell.exe -ExecutionPolicy Bypass -File "{post_reboot_script}" -PlanID {dashboard_plan_id} -ServerUrl "{base_url}" -ScenarioID {dashboard_scenario_id} -SetScenarioPending'
                
                reg_cmd = f'reg.exe add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce" /v LocalExec_PostReboot /t REG_SZ /d "{post_reboot_call}" /f'
                self._call(["cmd.exe", "/c " + reg_cmd])
                logging.info(f"Set RunOnce registry to resume plan {dashboard_plan_id} after reboot")

    def postLocalExecution(self):  
        # Post local execution check to see if need to unpause plan and delete registry key as prep has fully finished now.
        # Remove registry to run scenario again if we rebooted for local execution
        if self.dut_ip == "127.0.0.1" and self.platform.lower() == "windows":
            dashboard_url = Params.get('global', 'dashboard_url')
            dashboard_plan_id = Params.get('global', 'dashboard_plan_id')
            logging.info("Unpausing plan if paused from prep. Also deleting reg key")
            url = urlunparse(
                    urlparse(dashboard_url)._replace(
                        path='plan/ResumePlan',
                        query=f"PlanIDs={dashboard_plan_id}"
                    )
                )

            requests.get(url, allow_redirects=False)
            reg_cmd = f'reg.exe DELETE "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce" /v LocalExec_PostReboot /f'
            self._call(["cmd.exe", "/c " + reg_cmd])