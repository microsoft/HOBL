# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import scenarios.app_scenario
from parameters import Params
import logging
import os
import subprocess
from . import default_params

# Description:
#   Automatically generated standard scenario.

class PerfStress(scenarios.app_scenario.Scenario):

    prep_scenarios = ["edge_install", "web_prep", "teams_install", "office_install", "onedrive_prep", "productivity_prep"]
    prep_version = "1"

    # Set default parameters:
    default_params.run()

    module = __module__.split('.')[-1]

    logging.info("Adding stress_utc tool for parsing perf metrics")
    # Use override so this still works when user passes global:tools on CLI.
    Params.setOverride("global", "tools", "+stress_utc")
    Params.setOverride("stress_utc", "provider", Params.get(module, "provider"))

    if Params.get(module, "stress_run") == "1":
        logging.info("Applying stress_run parameter profile")
        cpu_param = Params.get(module, "stress_cpu_target")
        if cpu_param not in ["0", "25", "50", "65", "75", "85"]:
            cpu_param = "75"
            Params.setParam(module, "stress_cpu_target", cpu_param)
            logging.info("stress_run=1 and stress_cpu_target not provided; defaulting to 75 (high cpu load)")

        cpu_load_label = {
            "25": "low",
            "50": "medium",
            "65": "medium-high",
            "75": "high",
            "85": "very high",
        }.get(cpu_param, "high")
        logging.info(f"stress_cpu_target={cpu_param}% ({cpu_load_label} cpu load)")

    actions = None

    def prep(self):
        """Install pyenv + Python + numpy/psutil on DUT for percentile_stress.py"""
        if not self.checkPrepStatusNew([(self.module, self.prep_version)]):
            return
        logging.info("Running perf_stress prep: installing Python environment on DUT...")
        prep_script = os.path.join(os.path.dirname(__file__), "perf_stress_prep.ps1")
        self._upload(prep_script, self.dut_exec_path)
        try:
            self._call(["pwsh", rf"{self.dut_exec_path}\perf_stress_prep.ps1"])
        finally:
            self._copy_data_from_remote(self.result_dir)
        self.createPrepStatusControlFile(self.prep_version)

    def setUp(self):
        # Run prep if needed (installs Python + numpy/psutil on DUT)
        if Params.get(self.module, 'stress_run') == '1':
            self.prep()

        # Load actions JSON.
        actions_json = os.path.join(os.path.dirname(__file__), "perf_stress.json")
        self.actions = self.load_action_json(actions_json)

        # Phase 1: Sideload UtcPerftrack XML and restart DiagTrack BEFORE WPR starts.
        # DiagTrack must know about PerfTrack scenarios before WPR begins recording,
        # otherwise scenario completion events won't be emitted into the ETL.
        if Params.get(self.module, 'stress_run') == '1':
            sideload_dir = "C:\\ProgramData\\Microsoft\\Diagnosis\\Sideload"
            logging.info("Phase 1: Sideloading StressUtcPerftrack.xml before WPR starts")
            self._upload("utilities\\proprietary\\ParseUtc\\StressUtcPerftrack.xml", sideload_dir)
            self._call(["cmd.exe", f'/C copy /Y "{sideload_dir}\\StressUtcPerftrack.xml" "{sideload_dir}\\UtcPerftrack.xml"'], expected_exit_code="")
            self._upload("utilities\\proprietary\\ParseUtc\\DisableAllUploads.json", sideload_dir)
            self._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 3 /f > null 2>&1'])
            self._call(["cmd.exe", '/C reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\Windows Error Reporting" /v DisableWerUpload /t REG_DWORD /d 1 /f > null 2>&1'])
            logging.info("Restarting DiagTrack to load sideloaded UtcPerftrack.xml")
            self._call(["cmd.exe", "/c net stop DiagTrack & net start DiagTrack"], expected_exit_code="")
            import time
            time.sleep(5)  # Give DiagTrack time to register scenarios

        # Phase 2: Start WPR tracing (now DiagTrack has scenarios loaded)
        scenarios.app_scenario.Scenario.setUp(self)

        # Phase 3: Run Setup actions (Edge launch, stress scripts, etc.)
        # Edge launch during setup will now be captured in the ETL for PT_8998.
        setup_action = self._find_next_type("Setup", json=self.actions)
        if setup_action is not None:
            self.run_actions(setup_action["children"], fail_on_error=False)


    def runTest(self):
        # Execute Run Test actions, if they exist
        runtest_action = self._find_next_type("Run Test", json=self.actions)
        if runtest_action is not None:
            self.run_actions(runtest_action["children"], fail_on_error=False)
            return
        
        # If no "Run Test", "Setup", or "Teardown" specified, then just execute the whole list
        setup_action = self._find_next_type("Setup", json=self.actions)
        teardown_action = self._find_next_type("Teardown", json=self.actions)
        if runtest_action is None and setup_action is None and teardown_action is None:
            self.run_actions(self.actions)


    def tearDown(self):
        # Call base class tearDown() to stop measurment, copy back data from DUT, and call tool callbacks
        scenarios.app_scenario.Scenario.tearDown(self)

        # Execute Teardown actions, if they exist
        teardown_action = self._find_next_type("Teardown", json=self.actions)
        if teardown_action is not None:
            self.run_actions(teardown_action["children"])


    def kill(self):
        # In case of scenario failure or termination, force-stop background stress tasks.
        try:
            stop_script = os.path.join(self.dut_exec_path, "stop_perfStress_background.ps1")
            self._call([
                "cmd.exe",
                f"/C powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"{stop_script}\""
            ], expected_exit_code="")
        except Exception as ex:
            logging.warning(f"Failed to execute stop_perfStress_background.ps1 during kill(): {ex}")

        # Fallback kill list in case script execution is interrupted.
        for proc_name in ["python.exe", "py.exe", "pwsh.exe", "powershell.exe"]:
            try:
                self._kill(proc_name, force=True)
            except subprocess.TimeoutExpired:
                logging.warning(f"Timed out killing {proc_name} in kill()")
            except Exception:
                pass

        return
