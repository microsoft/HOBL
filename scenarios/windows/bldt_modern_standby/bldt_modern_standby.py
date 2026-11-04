# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Run Intel BLDT Modern Standby through HOBL."""

import csv
import json
import logging
import math
import os
import threading

import core.app_scenario
from core.parameters import Params


class BldtModernStandby(core.app_scenario.Scenario):
    """Run Intel's Modern Standby assessment through HOBL.

    Intel workload: mosTest places the DUT into Modern Standby, gathers standby
    diagnostics and produces native reports including Windows Sleep Study.

    HOBL lifecycle:
    1. Before: validate the requested sleep duration, require the DUT to be on DC,
       install or discover BLDT, and verify that an external host can wake the DUT.
    2. Run: start mosTest and leave the DUT undisturbed while the HOBL host sends one
       wake pulse after the requested sleep duration plus Intel startup allowance.
    3. After: verify one complete standby interval, stage Intel's current reports and
       shared assets, then let HOBL stop measurement and retrieve the DUT data.

    This scenario does not control the charger or require a minimum charge level.
    """

    module = __module__.split('.')[-1]
    prep_version = '1'
    minimum_sleep_duration_minutes = 20
    startup_allowance_seconds = 300

    Params.setDefault(
        module,
        'sleep_duration_minutes',
        str(minimum_sleep_duration_minutes),
        desc='Required uninterrupted Modern Standby duration in minutes.',
    )
    Params.setDefault(module, 'sleep_study_days', '1', desc='Number of days included in the native Windows Sleep Study report.')

    def setUp(self):
        """Read parameters, validate host wake support, and enter HOBL setup."""

        self.sleep_duration_minutes = int(Params.get(self.module, 'sleep_duration_minutes'))
        self.sleep_study_days = int(Params.get(self.module, 'sleep_study_days'))

        if not self.minimum_sleep_duration_minutes <= self.sleep_duration_minutes <= 1440:
            raise ValueError(f'bldt_modern_standby:sleep_duration_minutes must be between {self.minimum_sleep_duration_minutes} and 1440.')
        if not 1 <= self.sleep_study_days <= 28:
            raise ValueError('bldt_modern_standby:sleep_study_days must be between 1 and 28.')

        self.wake_after_seconds = (
            self.sleep_duration_minutes * 60
        ) + self.startup_allowance_seconds
        self.execution_timeout = self.wake_after_seconds + 900
        self.sleep_wake_call = Params.get('global', 'sleep_wake_call')
        self.cancel_pending_wake = threading.Event()
        self.wake_sent = False
        self.wake_error = None
        self.wake_timer = None

        if not self.prep_run_only:
            if self._get_power_source() != 'DC':
                raise RuntimeError(
                    'BLDT Modern Standby requires the DUT to be running on battery power. '
                    'Run the "charge_off" scenario before this scenario or add the '
                    '"auto_charge" tool to the test plan.'
                )
            if not self.sleep_wake_call:
                raise RuntimeError('BLDT Modern Standby requires global:sleep_wake_call in the device profile.')
            if self.async_comm != '1':
                raise RuntimeError('BLDT Modern Standby requires global:async_comm=1 so the DUT can notify HOBL after it wakes.')
            if Params.get('global', 'local_execution') == '1' or self.dut_ip in ('127.0.0.1', '::1', 'localhost', self.host_ip):
                raise RuntimeError('BLDT Modern Standby requires a separate, awake HOBL host to wake the DUT.')
            if self.rundown_mode != '0':
                raise RuntimeError('BLDT Modern Standby requires global:rundown_mode=0 because rundown monitoring would disturb sleep.')

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
        """Run Modern Standby and collect Intel's native reports."""

        if self.prep_run_only:
            return

        logging.info('Running BLDT Modern Standby on DC for at least %d minutes.', self.sleep_duration_minutes)

        self.wake_timer = threading.Timer(self.wake_after_seconds, self._send_wake)
        self.wake_timer.daemon = True
        logging.info('Leaving the DUT undisturbed; sending one wake pulse in %d seconds.', self.wake_after_seconds)
        self.wake_timer.start()
        try:
            result = self._run_modern_standby()
        except Exception:
            if self.wake_error is not None:
                raise RuntimeError('The Modern Standby wake command failed.') from self.wake_error
            raise
        finally:
            self.wake_timer.cancel()

        if self.wake_error is not None:
            raise RuntimeError('The Modern Standby wake command failed.') from self.wake_error

        reports = self._copy_reports(result['started_utc'])
        self._write_metrics(result['seconds'])

        logging.info('Collected BLDT Modern Standby reports: %s', reports)

        if result['exit_code'] != 0:
            raise RuntimeError(f"BLDT Modern Standby failed ({result['exit_code']}); see its logs.")
        if not reports:
            raise RuntimeError('No BLDT Modern Standby reports were collected.')
        self._validate_standby_events(result.get('events') or [])

    def tearDown(self):
        """Stop HOBL measurement and retrieve the staged reports and logs."""

        if self.prep_run_only:
            return

        logging.info('Tearing down BLDT Modern Standby scenario.')
        super().tearDown()

    def kill(self):
        """Cancel the pending wake and stop BLDT if the scenario is cancelled."""

        if hasattr(self, 'cancel_pending_wake'):
            self.cancel_pending_wake.set()
        if getattr(self, 'wake_timer', None) is not None:
            self.wake_timer.cancel()

        try:
            self._kill('BatteryLifeDiagnosticTool.exe')
        except Exception:
            pass

    def _send_wake(self):
        """Send the configured wake command once unless it was cancelled."""

        if self.cancel_pending_wake.is_set() or self.wake_sent:
            return

        self.wake_sent = True
        logging.info('Sending the Modern Standby wake pulse.')
        try:
            self._host_call(self.sleep_wake_call, timeout=30)
            logging.info('Wake command acknowledged; waiting for the DUT to resume and BLDT to collect Sleep Study data and generate reports.')
        except Exception as error:
            self.wake_error = error
            logging.error('Modern Standby wake command failed: %s', error)

    def _get_power_source(self):
        """Return AC or DC from the DUT's current power state."""

        state = int(self._call(['powershell', '(Get-WmiObject -Class Win32_Battery -ea 0).BatteryStatus'], timeout=10))

        if state == 1:
            return 'DC'
        if state == 2:
            return 'AC'
        raise RuntimeError(f'Could not determine the DUT power source: {state}.')

    def _validate_standby_events(self, events):
        """Require one complete standby interval of the requested duration."""

        if isinstance(events, dict):
            events = [events]

        if len(events) != 2 or [event['id'] for event in events] != [506, 507]:
            raise RuntimeError('Expected one complete Modern Standby entry and exit event pair.')

        entry, exit_event = events
        duration = exit_event['seconds'] - entry['seconds']
        if entry['record_id'] >= exit_event['record_id'] or entry['seconds'] < 0 or not math.isfinite(duration) or duration < self.sleep_duration_minutes * 60:
            raise RuntimeError(f'Modern Standby lasted {duration:.3f} seconds; at least {self.sleep_duration_minutes * 60} seconds are required.')

        logging.info('Validated Modern Standby duration: %.3f seconds.', duration)
        return round(duration, 3)

    def _write_metrics(self, scenario_runtime):
        """Write the required native workload runtime."""

        os.makedirs(self.result_dir, exist_ok=True)
        metrics_path = os.path.join(self.result_dir, 'bldt_modern_standby_results.csv')
        with open(metrics_path, 'w', newline='', encoding='utf-8') as stream:
            csv.writer(stream).writerow(['scenario_runtime', scenario_runtime])

        logging.info('========== BLDT Modern Standby metrics ==========')
        logging.info('scenario_runtime: %ss', scenario_runtime)

    def _install_bldt(self):
        """Upload and run the BLDT installation script."""

        local_script = os.path.join(
            os.path.dirname(__file__),
            'bldt_modern_standby_resources\\bldt_modern_standby_prep.ps1',
        )
        remote_script = f'{self.dut_exec_path}\\bldt_modern_standby_prep.ps1'

        self._upload(local_script, self.dut_exec_path, check_modified=False)

        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action Install '
            f'-DataRoot "{self.dut_data_path}"'
        )
        self._call(['powershell.exe', arguments], timeout=10860)

    def _discover_bldt(self):
        """Return the installed BLDT executable path."""

        remote_script = f'{self.dut_exec_path}\\bldt_modern_standby_prep.ps1'
        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action Discover '
            f'-DataRoot "{self.dut_data_path}"'
        )
        executable = self._call(['powershell.exe', arguments], timeout=30).strip()

        logging.info('Using BLDT executable: %s', executable)
        return executable

    def _run_modern_standby(self):
        """Run Intel's Modern Standby workload and return its result."""

        remote_script = f'{self.dut_exec_path}\\bldt_modern_standby_prep.ps1'
        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action Run '
            f'-SleepStudyDays {self.sleep_study_days} '
            f'-DataRoot "{self.dut_data_path}" '
            f'-TimeoutSeconds {self.execution_timeout}'
        )
        output = self._call(
            ['powershell.exe', arguments],
            timeout=self.execution_timeout + 60,
        )
        return json.loads(output)

    def _copy_reports(self, started_utc):
        """Copy current native Modern Standby reports into the DUT result directory."""

        remote_script = f'{self.dut_exec_path}\\bldt_modern_standby_prep.ps1'
        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action CopyReports '
            f'-StartedUtc "{started_utc}" '
            f'-DataRoot "{self.dut_data_path}"'
        )
        output = self._call(['powershell.exe', arguments], timeout=120)
        return json.loads(output)['reports']
