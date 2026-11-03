# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Run Intel BLDT Battery Life through HOBL."""

import csv
import json
import logging
import os

import core.app_scenario
from core.parameters import Params


class BldtBatteryLife(core.app_scenario.Scenario):
    """Run Intel's Battery Life assessment through HOBL.

    Intel workload: Battery Life records system activity and checks Windows for
    power-efficiency problems, then produces native HTML, JSON and ZIP reports.

    HOBL lifecycle:
    1. Before: validate the collection duration and require the DUT to be on DC;
       install or discover BLDT, then enter HOBL's normal measured lifecycle.
    2. Run: invoke batteryLife with no charge threshold or collection delay and use
       the selected duration for both native collection phases.
    3. After: stage current native reports, shared HTML assets and execution logs;
       HOBL teardown stops measurement and retrieves the DUT data.

    This scenario does not control the charger or require a minimum charge level.
    Success requires a zero BLDT exit code and at least one current native report,
    not that every Intel diagnostic finding passes.
    """

    module = __module__.split('.')[-1]
    prep_version = '1'

    Params.setDefault(module, 'collection_duration_seconds', '600', desc='Duration of each Intel Battery Life collection phase in seconds.')

    def setUp(self):
        """Read the duration, prepare BLDT, and enter HOBL setup."""

        self.collection_duration_seconds = int(Params.get(self.module, 'collection_duration_seconds'))

        if not 10 <= self.collection_duration_seconds <= 3600:
            raise ValueError('bldt_battery_life:collection_duration_seconds must be between 10 and 3600.')

        self.execution_timeout = (self.collection_duration_seconds * 2) + 300

        if not self.prep_run_only and self._get_power_source() != 'DC':
            raise RuntimeError(
                'BLDT Battery Life requires the DUT to be running on battery power. '
                'Run the "charge_off" scenario before this scenario or add the '
                '"auto_charge" tool to the test plan.'
            )

        self.prep()
        super().setUp()

    def prep(self):
        """Install BLDT once and locate its executable."""

        prep_suffix = f'_{self.prep_version}'

        if self.checkPrepStatus([self.module + prep_suffix]):
            self._install_bldt()
            self.createPrepStatusControlFile(prep_suffix)

        self.bldt_executable = self._discover_bldt()

    def runTest(self):
        """Run Battery Life and collect Intel's native reports."""

        logging.info('Running BLDT Battery Life on DC; each collection phase is %d seconds.', self.collection_duration_seconds)

        result = self._run_battery_life()
        reports = self._copy_reports(result['started_utc'])
        self._write_metrics(result['seconds'])

        logging.info('Collected BLDT Battery Life reports: %s', reports)

        if result['exit_code'] != 0:
            raise RuntimeError(f"BLDT Battery Life failed ({result['exit_code']}); see its logs.")
        if not reports:
            raise RuntimeError('No BLDT Battery Life reports were collected.')

    def tearDown(self):
        """Stop HOBL measurement and retrieve the staged reports and logs."""

        if self.prep_run_only:
            return

        logging.info('Tearing down BLDT Battery Life scenario.')
        super().tearDown()

    def kill(self):
        """Stop BLDT if the scenario is cancelled."""

        try:
            self._kill('BatteryLifeDiagnosticTool.exe')
        except Exception:
            pass


    def _get_power_source(self):
        """Return AC or DC from the DUT's current power state."""

        state = int(self._call(
            ['powershell', '(Get-WmiObject -Class Win32_Battery -ea 0).BatteryStatus'],
            timeout=10,
        ))

        if state == 1:
            return 'DC'
        if state == 2:
            return 'AC'
        raise RuntimeError(f'Could not determine the DUT power source: {state}.')

    def _write_metrics(self, scenario_runtime):
        """Write the required native workload runtime."""

        os.makedirs(self.result_dir, exist_ok=True)
        metrics_path = os.path.join(self.result_dir, 'bldt_battery_life_results.csv')
        with open(metrics_path, 'w', newline='', encoding='utf-8') as stream:
            csv.writer(stream).writerow(['scenario_runtime', scenario_runtime])

        logging.info('========== BLDT Battery Life metrics ==========')
        logging.info('scenario_runtime: %ss', scenario_runtime)

    def _install_bldt(self):
        """Upload and run the BLDT installation script."""

        local_script = os.path.join(
            os.path.dirname(__file__),
            'bldt_battery_life_resources\\bldt_battery_life_prep.ps1',
        )
        remote_script = f'{self.dut_exec_path}\\bldt_battery_life_prep.ps1'

        self._upload(local_script, self.dut_exec_path, check_modified=False)

        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action Install '
            f'-DataRoot "{self.dut_data_path}"'
        )
        self._call(['powershell.exe', arguments], timeout=10860)

    def _discover_bldt(self):
        """Return the installed BLDT executable path."""

        remote_script = f'{self.dut_exec_path}\\bldt_battery_life_prep.ps1'
        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action Discover '
            f'-DataRoot "{self.dut_data_path}"'
        )
        executable = self._call(['powershell.exe', arguments], timeout=30).strip()

        logging.info('Using BLDT executable: %s', executable)
        return executable

    def _run_battery_life(self):
        """Run Intel's Battery Life workload and return its result."""

        remote_script = f'{self.dut_exec_path}\\bldt_battery_life_prep.ps1'
        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action Run '
            f'-CollectionDurationSeconds {self.collection_duration_seconds} '
            f'-DataRoot "{self.dut_data_path}" '
            f'-TimeoutSeconds {self.execution_timeout}'
        )
        output = self._call(
            ['powershell.exe', arguments],
            timeout=self.execution_timeout + 60,
        )
        return json.loads(output)

    def _copy_reports(self, started_utc):
        """Copy current native Battery Life reports into the DUT result directory."""

        remote_script = f'{self.dut_exec_path}\\bldt_battery_life_prep.ps1'
        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action CopyReports '
            f'-StartedUtc "{started_utc}" '
            f'-DataRoot "{self.dut_data_path}"'
        )
        output = self._call(['powershell.exe', arguments], timeout=120)
        return json.loads(output)['reports']
