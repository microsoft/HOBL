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
import scenarios.windows.dut_setup as dut_setup

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

    Params.setOverride("dut_setup", "reboot_prompt", "0")
    Params.setOverride("dut_setup", "reboot", "0")
    Params.setOverride("dut_setup", "run_cmd", "1")
    Params.setOverride("dut_setup", "upload_path", "")
    Params.setOverride("dut_setup", "target_path", "")

    common_preps      = Params.get('prep', 'common_preps').split()
    scenarios_to_prep = Params.get('prep', 'scenarios_to_prep').split()
    additional_preps  = Params.get('prep', 'additional_preps').split()

    run_dir     = Params.getCalculated('run_dir')
    params_file = Params.getCalculated('params_file')

    hobl_external = Params.get('global', 'hobl_external').split()

    is_prep = True
    hide_ui = False
    num_preps = 0 # excludes net_preps

    def get_prep_scenarios(self):
        # Check if inserting net_preps are needed by checking if anything other than Wi-Fi is specified in the profile or overrides
        net_prep_needed = False
        if Params.get('global', 'platform').lower() == "windows" and Params.get('net_prep', 'connection') != "Wi-Fi":
            net_prep_needed = True

        parent_modules = get_parent_modules(["scenarios"], ext_paths=self.hobl_external)

        prep_scenarios = []

        if Params.get('global', 'platform').lower() == "windows":
            if net_prep_needed:
                prep_scenarios.append("net_prep_wifi")
            prep_scenarios.extend(self.checkPrepStatusNew(self.common_preps))

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

        if net_prep_needed:
            prep_scenarios.append("net_prep")

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

        # See if dut_setup needs to be updated.
        self.updateDutSetup()

        prep_scenarios = self.get_prep_scenarios()
        self.num_preps = sum(1 for p in prep_scenarios if p not in ["net_prep_wifi", "net_prep"])
        if self.num_preps == 0:  # If only net_prep_wifi and net_prep are in the list, then no other preps to run.
            logging.info("No preps to run")
            return

        # self.checkLocalExecution()

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
                "global:post_run_delay=0",
                "global:dashboard_plan_id=" + Params.get('global', 'dashboard_plan_id'),
                "global:dashboard_scenario_id=" + Params.get('global', 'dashboard_scenario_id'),
                "global:prep_dashboard_url=" + Params.get('global', 'dashboard_url'), # Used in app_scenario in case of reboot.  We don't want to pass the real dashboard_url to these sub-preps because it is used in many places for updating the UI.
                "global:preserve_status_window=1", # This will keep the StatusWindow open for preps spawned by the prep scenario.  When prep itself completes, the window will be dismissed.
                "global:check_ui=1" # This instructs the scenario to respect the "hide_ui" flag even though no dashboard_url is present.
            ])

            if result.returncode != 0 and not failing_scenario:
                failing_scenario = s
            time.sleep(10)

        # self.postLocalExecution()

        # Delete to prevent this scenario from copying over the last prep data files during teardown
        self._remote_make_dir(self.dut_data_path, True)

        if failing_scenario:
            self.error_fail(f"Prep scenario {failing_scenario} failed")

    def tearDown(self):
        return

    def kill(self):
        prep_scenarios = self.get_prep_scenarios()

        if len(prep_scenarios) <= 2:  # If only net_prep_wifi and net_prep are in the list, then no other preps to run.
            return

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

    def updateDutSetup(self):
        # Check the current dut_setup.cmd version and compare with version on DUT.  If not the same, then run the dut_setup scenario.
        if self.platform.lower() == "windows":
            dut_version = self._getDutSetupVersionOfDut()
            host_version = self._getDutSetupVersionOfHost()
            if dut_version != host_version:
                logging.info(f"Updating dut_setup.cmd on DUT from version {dut_version} to {host_version}")
                ds = dut_setup.DutSetup()
                ds.runTest()
