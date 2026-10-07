# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# discharge
# 
# Wait until charge is below specified threshold
#
# Setup instructions:
#   Set up the charge_on and charge_off paramters in the device profile.
##

import logging
import subprocess
import time

from core.parameters import Params
import core.app_scenario


class Discharge(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]

    # Set default parameters
    Params.setDefault(module, 'resume_threshold', '100', desc="Percent battery level to discharge to")
    Params.setDefault(module, 'poll_period', '30', desc="How often to check battery level (default 30s)")
    Params.setDefault(module, 'run_scenario', '', desc="Run LVP, FishBowl, or GPU stress in the background", valOptions=["lvp", "fishbowl", "stress"])
    Params.setDefault(module, 'leave_on_dc', '1', desc="Leave on DC power after discharge scenario (default 1 - keep charger off)") 
    Params.setDefault(module, 'taper_workload', '0', desc="Stop workload to cool down device. resume_threshold + taper_workload. (default 0)")

    # Get parameters
    resume_threshold = int(Params.get(module, 'resume_threshold'))
    charge_off_call  = Params.get('global', 'charge_off_call')
    charge_on_call   = Params.get('global', 'charge_on_call')
    poll_period      = int(Params.get(module, 'poll_period'))
    run_scenario     = Params.get(module, 'run_scenario')
    leave_on_dc      = Params.get(module, 'leave_on_dc') 
    taper_workload    = int(Params.get(module, 'taper_workload'))

    Params.setOverride('global', 'tools', '')
    Params.setOverride('global', 'collection_enabled', '0')

    if not run_scenario:
        Params.setOverride('global', 'prep_tools', '')

    run_dir     = Params.getCalculated('run_dir')
    params_file = Params.getCalculated('params_file')

    is_prep = True


    def is_discharge_done(self, battery_level=None):
        if battery_level is None:
            battery_level = self.resume_threshold
        batt_level = self.getBattLevel()
        logging.info(f"Battery level: {str(batt_level)} Expected Level: {str(battery_level)}")

        if batt_level <= battery_level:
            logging.info("Discharging complete")
            return True
        return False

    def setUp(self):
        logging.info("Discharging...")
        self._host_call(self.charge_off_call)

        # Call base class setUp() to dump config, call tool callbacks, and start measurment
        core.app_scenario.Scenario.setUp(self)

    def runTest(self):
        if self.is_discharge_done():
            return

        p = None

        if self.run_scenario.lower() == "lvp":
            logging.info(f"Starting {self.run_scenario.lower()}")

            p = subprocess.Popen([
                ".\\hobl.cmd",
                "-p", self.params_file,
                "-s", "lvp",
                f"global:result_dir_complete={self.run_dir}",
                "lvp:duration=14400",
                "global:tools=tearcheck",
                "global:post_run_delay=0"
            ], stdin=subprocess.PIPE)

            time.sleep(30)
        elif self.run_scenario.lower() == "fishbowl":
            logging.info(f"Starting {self.run_scenario.lower()}")

            p = subprocess.Popen([
                ".\\hobl.cmd",
                "-p", self.params_file,
                "-s", "fishbowl",
                f"global:result_dir_complete={self.run_dir}",
                "fishbowl:duration=14400",
                "fishbowl:fish_count=2000",
                "global:tools=tearcheck",
                "global:post_run_delay=0"
            ], stdin=subprocess.PIPE)

            time.sleep(30)
        elif self.run_scenario.lower() == "stress":
            logging.info(f"Starting {self.run_scenario.lower()}")

            p = subprocess.Popen([
                ".\\hobl.cmd",
                "-p", self.params_file,
                "-s", "stress",
                f"global:result_dir_complete={self.run_dir}",
                "stress:duration=14400",
                "stress:loads=GPU",
                "global:tools=tearcheck",
                "global:delay_between_runs=0"
            ], stdin=subprocess.PIPE)

            time.sleep(30)

        while True:
            if self.is_discharge_done(self.resume_threshold + self.taper_workload):
                break
            else:
                time.sleep(int(self.poll_period))

        logging.info(f"Stopping {self.run_scenario.lower()}")

        if p:
            p.stdin.write(b"teardown\n")
            p.stdin.flush()
            p.wait()

        # Check if workload has been tapered if so then we need to finish discharing to resume_threshold
        if self.taper_workload > 0:
            logging.info("Workload tapered to cool down device. Now finishing discharging to resume_threshold.")
            while True:
                if self.is_discharge_done(self.resume_threshold):
                    break
                else:
                    time.sleep(int(self.poll_period))


    def getBattLevel(self):
        batt_level = self._call(["powershell.exe",
            "Add-Type -Assembly System.Windows.Forms; [Math]::round(([System.Windows.Forms.SystemInformation]::PowerStatus.BatteryLifePercent) * 100, 2)"
        ])

        return int(batt_level)

    def tearDown(self):
        # Call base class tearDown() to stop measurment and call tool callbacks
        core.app_scenario.Scenario.tearDown(self)

        if self.leave_on_dc == '0':
            logging.info("Re-enabling charging...")
            self._host_call(self.charge_on_call)

    def kill(self):
        if self.run_scenario.lower() == "lvp":
            subprocess.run([
                ".\\hobl.cmd",
                "-p", self.params_file,
                "-k", "lvp"
            ])
        elif self.run_scenario.lower() == "fishbowl":
            subprocess.run([
                ".\\hobl.cmd",
                "-p", self.params_file,
                "-k", "fishbowl"
            ])
        elif self.run_scenario.lower() == "stress":
            subprocess.run([
                ".\\hobl.cmd",
                "-p", self.params_file,
                "-k", "stress"
            ])

        return 0
