# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Run Intel BLDT SysConfigChecks through HOBL."""

import json
import logging
import os

import core.app_scenario


class BldtSysconfig(core.app_scenario.Scenario):
    """Intel's Battery Life Diagnostic Tool - System Config Checker.

    Intel workload: System Config examines configuration relevant to power efficiency
    and produces diagnostic findings in native HTML, JSON and ZIP reports.

    HOBL lifecycle:
    1. Before: refresh the DUT prep script, close existing BLDT sessions, and discover
       either BLDT edition; install or repair only when needed.
    2. Run: invoke the discovered executable with the selected AC/DC assessment mode.
       This scenario does not control the charger or use DAQ measurement.
    3. After: require fresh matching reports and stage them with shared HTML assets
       and logs for host collection.

    No AI analysis or AI models are required.
    Success means complete execution and reports, not passing every Intel check.
    """

    is_prep = True
    module = __module__.split('.')[-1]
    prep_version = '4'
    execution_timeout = 900

    def setUp(self):
        """Prepare BLDT and enter HOBL setup."""

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
        """Run BLDT SysConfigChecks and collect its reports."""

        self.power_source = self._get_power_source()
        logging.info('Running BLDT SysConfigChecks on %s.', self.power_source)

        result = self._run_sysconfig_checks()
        reports = self._copy_reports(result['started_utc'])

        logging.info('Collected BLDT reports: %s', reports)

        if result['exit_code'] != 0:
            raise RuntimeError(f"BLDT SysConfigChecks failed ({result['exit_code']}); see its logs.")
        if not reports:
            raise RuntimeError('No BLDT reports were collected.')


    def tearDown(self):
        """Let HOBL retrieve the staged reports and logs."""

        if self.prep_run_only:
            return

        logging.info('Tearing down BLDT SysConfig scenario.')
        super().tearDown()


    def kill(self):
        """Stop BLDT if the scenario is cancelled."""
        try:
            self._kill('BatteryLifeDiagnosticTool.exe')
        except:
            pass
        return


    def _get_power_source(self):
        """Return AC or DC from the DUT's current power-line state."""

        state = int(self._call(['powershell', '(Get-WmiObject -Class Win32_Battery -ea 0).BatteryStatus'], timeout=10))

        if state == 1:
            return 'DC'
        if state == 2:
            return 'AC'
        raise RuntimeError(f'Could not determine the DUT power source: {state}.')

    def _install_bldt(self):
        """Upload and run the BLDT installation script."""

        local_script = os.path.join(
            os.path.dirname(__file__),
            'bldt_sysconfig_resources\\bldt_sysconfig_helper.ps1',
        )
        remote_script = f'{self.dut_exec_path}\\bldt_sysconfig_helper.ps1'

        self._upload(local_script, self.dut_exec_path, check_modified=False)

        self._call(
            ['powershell.exe', (
                    f'-NoProfile -NonInteractive '
                    f'-ExecutionPolicy Bypass '
                    f'-File "{remote_script}" '
                    f'-Action Install '
                    f'-DataRoot "{self.dut_data_path}"'
                ), ], timeout=10860)

    def _discover_bldt(self):
        """Return the installed BLDT executable path."""

        remote_script = f'{self.dut_exec_path}\\bldt_sysconfig_helper.ps1'
        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action Discover '
            f'-DataRoot "{self.dut_data_path}"'
        )

        executable = self._call(['powershell.exe', arguments], timeout=30).strip()

        logging.info('Using BLDT executable: %s', executable)
        return executable

    def _run_sysconfig_checks(self):
        """Run SysConfigChecks and return its start time and exit code."""

        remote_script = f'{self.dut_exec_path}\\bldt_sysconfig_helper.ps1'
        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action Run '
            f'-PowerSource {self.power_source} '
            f'-DataRoot "{self.dut_data_path}"'
        )

        output = self._call(['powershell.exe', arguments], timeout=self.execution_timeout + 60)

        return json.loads(output)

    def _copy_reports(self, started_utc):
        """Copy current native System Config Checker reports into the DUT result directory."""

        remote_script = f'{self.dut_exec_path}\\bldt_sysconfig_helper.ps1'
        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action CopyReports '
            f'-StartedUtc "{started_utc}" '
            f'-DataRoot "{self.dut_data_path}"'
        )

        output = self._call(['powershell.exe', arguments], timeout=120)
        return json.loads(output)['reports']
