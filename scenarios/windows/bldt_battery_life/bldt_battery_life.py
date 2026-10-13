# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Intel Battery Life Diagnostic Tool Battery Life scenario.

charger_mode=manual skips relay callbacks and prints charger instructions in the
HOBL log, waiting up to 120 seconds for each physical connection change.
An unplugged DUT at or above min_battery_charge can proceed without charging.
Below the threshold, connect AC and charge before measurement. Reconnect after
measurement when requested; a manual post-run reconnect timeout only warns.
Pre-measurement timeouts and automated restoration failures remain errors.
Automated mode requires working charger callbacks.
"""

import base64
import json
import logging
import math
import time

import core.app_scenario
from core.parameters import Params


class _BatteryStateTimeout(RuntimeError):
    """The DUT responded, but did not reach the requested battery state in time."""


class BldtBatteryLife(core.app_scenario.Scenario):

    module = __module__.split('.')[-1]
    prep_version = "1"
    resources = module + "_resources"
    prep_marker_module = "bldt"

    Params.setDefault(
        module,
        'use_ai',
        'false',
        desc='Install/require the BLDT AI edition. The AI edition also satisfies standard requests.',
        valOptions=['true', 'false'],
    )
    Params.setDefault(
        module,
        'power_source',
        'DC',
        desc='Power source used for the Battery Life collection.',
        valOptions=['AC', 'DC'],
    )
    Params.setDefault(
        module,
        'charger_mode',
        'automated',
        desc='automated uses charger callbacks; manual logs connect/unplug instructions and verifies power state (120-second transition timeout; post-run reconnect timeout only warns).',
        valOptions=['automated', 'manual'],
    )
    Params.setDefault(
        module,
        'min_battery_charge',
        '90',
        desc='Minimum battery charge percentage required before the BLDT collection starts.',
    )
    Params.setDefault(
        module,
        'socwatch_duration',
        '600',
        desc='BLDT SoC Watch collection duration in seconds.',
    )
    Params.setDefault(
        module,
        'socwatch_delay',
        '300',
        desc='BLDT delay before SoC Watch collection in seconds.',
    )
    Params.setDefault(
        module,
        'energy_rpt_duration',
        '600',
        desc='BLDT energy report collection duration in seconds.',
    )
    Params.setDefault(
        module,
        'charge_timeout_minutes',
        '240',
        desc='Maximum time to wait for the battery to reach min_battery_charge.',
    )

    @staticmethod
    def _encoded_powershell(command):
        encoded = base64.b64encode(command.encode('utf-16-le')).decode('ascii')
        return ['powershell.exe', f'-NoProfile -NonInteractive -EncodedCommand {encoded}']

    @classmethod
    def _powershell_command(cls, script, **parameters):
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        command = "& " + quote(script)
        for name, value in parameters.items():
            command += f" -{name} {quote(value)}"
        return cls._encoded_powershell(command)

    @staticmethod
    def _get_integer_parameter(name, minimum, maximum):
        value = Params.get(BldtBatteryLife.module, name)
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f'bldt_battery_life:{name} must be an integer.') from error
        if not minimum <= parsed <= maximum:
            raise ValueError(
                f'bldt_battery_life:{name} must be between {minimum} and {maximum}.'
            )
        return parsed

    def _prep_command(self, validate_only=False):
        parameters = {
            'UseAi': str(self.use_ai).lower(),
            'LogFile': f"{self.dut_data_path}\\bldt_battery_life_prep.log",
        }
        if validate_only:
            parameters['ValidateOnly'] = 'true'
        return self._powershell_command(
            f"{self.target}\\bldt_battery_life_prep.ps1",
            **parameters,
        )

    def _run_prep(self):
        if self.use_ai:
            logging.info(
                "Preparing Intel BLDT v3.1.1 AI edition; "
                "the AI package may take over an hour to download and extract."
            )
        else:
            logging.info("Preparing Intel BLDT v3.1.1 standard edition.")
        try:
            self._call(self._prep_command(), timeout=10800)
            self._call(self._prep_command(validate_only=True), timeout=300)
        finally:
            self._copy_data_from_remote(self.result_dir)
        self.createPrepStatusControlFile(self.prep_version, module=self.prep_marker_module)

    def _get_battery_state(self):
        command = (
            "$ErrorActionPreference = 'Stop'; "
            "$ProgressPreference = 'SilentlyContinue'; "
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$status = [System.Windows.Forms.SystemInformation]::PowerStatus; "
            "[pscustomobject]@{"
            "battery_percent = [math]::Round($status.BatteryLifePercent * 100, 2); "
            "power_line_status = [string]$status.PowerLineStatus; "
            "battery_charge_status = [string]$status.BatteryChargeStatus"
            "} | ConvertTo-Json -Compress"
        )
        output = self._call(self._encoded_powershell(command), timeout=30)
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError('BLDT Battery Life could not read the DUT battery state.')
        try:
            json_lines = [line for line in lines if line.startswith('{')]
            if len(json_lines) != 1:
                raise ValueError('Expected exactly one battery-state JSON object.')
            state = json.loads(json_lines[0])
            state['battery_percent'] = float(state['battery_percent'])
            if state['power_line_status'] not in ('Online', 'Offline'):
                raise ValueError('Battery power source is unknown.')
            if not isinstance(state['battery_charge_status'], str):
                raise ValueError('Battery charge status must be a string.')
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f'BLDT Battery Life received an invalid battery-state response: {output!r}'
            ) from error
        if 'NoSystemBattery' in state.get('battery_charge_status', ''):
            raise RuntimeError('BLDT Battery Life requires a DUT with a system battery.')
        if not 0 <= state['battery_percent'] <= 100:
            raise RuntimeError(
                f"BLDT Battery Life read an invalid battery level: {state['battery_percent']}."
            )
        return state

    def _request_charger(self, callback, action):
        if self.charger_mode == 'manual':
            instruction = 'Connect the charger' if action == 'charge_on' else 'Unplug the charger'
            logging.warning(
                "BLDT manual charger mode: %s now. Waiting up to 120 seconds "
                "for Windows to confirm the power source.",
                instruction,
            )
            return
        if not callback:
            raise RuntimeError(
                f'BLDT Battery Life requires global:{action}_call for automated {self.power_source} testing.'
            )
        logging.info("Requesting charger %s through the configured host callback.", action)
        self._host_call(callback)

    def _wait_for_state(self, description, predicate, timeout_seconds, poll_seconds=30):
        deadline = time.monotonic() + timeout_seconds
        while True:
            state = self._get_battery_state()
            logging.info(
                "Battery state while waiting for %s: %.2f%%, power=%s, charge=%s",
                description,
                state['battery_percent'],
                state['power_line_status'],
                state['battery_charge_status'],
            )
            if predicate(state):
                return state
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _BatteryStateTimeout(f'Timed out waiting for {description}.')
            time.sleep(min(poll_seconds, remaining))

    def _ensure_charger_on(self):
        state = self._get_battery_state()
        if state['power_line_status'] != 'Online':
            self._request_charger(self.charge_on_call, 'charge_on')
            state = self._wait_for_state(
                'AC power after enabling the charger',
                lambda current: current['power_line_status'] == 'Online',
                timeout_seconds=120,
                poll_seconds=5,
            )
        return state

    def _prepare_power_state(self):
        state = self._get_battery_state()
        if self.charger_mode == 'manual' and self.power_source == 'DC':
            if (
                state['power_line_status'] == 'Offline'
                and state['battery_percent'] >= self.min_battery_charge
            ):
                logging.info(
                    "DUT is already on DC at %.2f%% (minimum %d%%); no charging needed.",
                    state['battery_percent'], self.min_battery_charge,
                )
                self.restore_charging = True
                return
        self._ensure_charger_on()
        logging.info(
            "Keep the charger connected until the battery reaches %d%% "
            "(charging timeout: %d minutes).",
            self.min_battery_charge, self.charge_timeout_minutes,
        )
        self._wait_for_state(
            f'the battery to reach {self.min_battery_charge}%',
            lambda state: (
                state['power_line_status'] == 'Online'
                and state['battery_percent'] >= self.min_battery_charge
            ),
            timeout_seconds=self.charge_timeout_minutes * 60,
        )

        if self.power_source == 'DC':
            self.restore_charging = True
            self._request_charger(self.charge_off_call, 'charge_off')
            self._wait_for_state(
                'DC power after disabling the charger',
                lambda state: state['power_line_status'] == 'Offline',
                timeout_seconds=120,
                poll_seconds=5,
            )

    def _restore_charging(self, best_effort=False):
        if not getattr(self, 'restore_charging', False):
            return
        try:
            if self.charger_mode == 'manual':
                try:
                    self._ensure_charger_on()
                except _BatteryStateTimeout:
                    logging.warning(
                        "BLDT manual charger mode: AC power was not confirmed within "
                        "120 seconds after the run. Connect the charger to prevent "
                        "battery drain. This reconnect timeout does not change the "
                        "assessment result; charging restoration remains unconfirmed."
                    )
                    return
            else:
                self._request_charger(self.charge_on_call, 'charge_on')
                self._wait_for_state(
                    'AC power after restoring the charger',
                    lambda state: state['power_line_status'] == 'Online',
                    timeout_seconds=120,
                    poll_seconds=5,
                )
            self.restore_charging = False
        except Exception:
            if not best_effort:
                raise
            logging.exception("Failed to restore charging after BLDT Battery Life.")

    def setUp(self):
        use_ai = Params.get(self.module, 'use_ai').strip().lower()
        if use_ai not in ('true', 'false'):
            raise ValueError('bldt_battery_life:use_ai must be true or false.')
        self.use_ai = use_ai == 'true'

        self.power_source = Params.get(self.module, 'power_source').strip().upper()
        if self.power_source not in ('AC', 'DC'):
            raise ValueError('bldt_battery_life:power_source must be AC or DC.')

        self.charger_mode = Params.get(self.module, 'charger_mode').strip().lower()
        if self.charger_mode not in ('automated', 'manual'):
            raise ValueError('bldt_battery_life:charger_mode must be automated or manual.')

        self.min_battery_charge = self._get_integer_parameter(
            'min_battery_charge', 0, 100
        )
        self.socwatch_duration = self._get_integer_parameter(
            'socwatch_duration', 10, 86400
        )
        self.socwatch_delay = self._get_integer_parameter(
            'socwatch_delay', 0, 86400
        )
        self.energy_rpt_duration = self._get_integer_parameter(
            'energy_rpt_duration', 1, 3600
        )
        self.charge_timeout_minutes = self._get_integer_parameter(
            'charge_timeout_minutes', 1, 1440
        )
        collection_seconds = (
            self.socwatch_delay
            + self.socwatch_duration
            + self.energy_rpt_duration
            + 3600
        )
        self.bldt_timeout_minutes = math.ceil(collection_seconds / 60)

        self.charge_on_call = Params.get('global', 'charge_on_call')
        self.charge_off_call = Params.get('global', 'charge_off_call')
        if self.charger_mode == 'automated' and self.power_source == 'DC' and (
            not self.charge_on_call or not self.charge_off_call
        ):
            raise RuntimeError(
                'BLDT Battery Life DC testing requires global:charge_on_call and '
                'global:charge_off_call in the device profile.'
            )

        self.target = f"{self.dut_exec_path}\\{self.resources}"
        self.restore_charging = False

        if self.charger_mode == 'automated':
            self._ensure_charger_on()
        else:
            state = self._get_battery_state()
            if self.power_source == 'AC' or state['battery_percent'] < self.min_battery_charge:
                self._ensure_charger_on()

        logging.info("Uploading BLDT Battery Life resources to %s", self.target)
        self._upload(
            f"scenarios\\windows\\{self.module}\\{self.resources}",
            self.dut_exec_path,
        )
        needs_prep = bool(
            self.checkPrepStatus([self.prep_marker_module + self.prep_version])
        )

        if not needs_prep:
            try:
                self._call(self._prep_command(validate_only=True), timeout=300)
            except Exception as error:
                logging.warning(
                    "BLDT live validation failed; prep will repair the installation: %s",
                    error,
                )
                needs_prep = True

        if needs_prep:
            self._run_prep()

        try:
            self._prepare_power_state()
            core.app_scenario.Scenario.setUp(self)
        except Exception:
            self._restore_charging(best_effort=True)
            raise

    def runTest(self):
        logging.info(
            "Running BLDT Battery Life on %s power for up to %d minutes.",
            self.power_source,
            self.bldt_timeout_minutes,
        )
        self._call(
            self._powershell_command(
                f"{self.target}\\bldt_battery_life_run.ps1",
                UseAi=str(self.use_ai).lower(),
                PowerSource=self.power_source,
                MinBatteryCharge=self.min_battery_charge,
                SocwatchDuration=self.socwatch_duration,
                SocwatchDelay=self.socwatch_delay,
                EnergyRptDuration=self.energy_rpt_duration,
                TimeoutMinutes=self.bldt_timeout_minutes,
            ),
            timeout=(self.bldt_timeout_minutes * 60) + 300,
        )

    def tearDown(self):
        try:
            logging.info("Collecting BLDT Battery Life logs, metrics, and reports.")
            core.app_scenario.Scenario.tearDown(self)
        except Exception:
            self._restore_charging(best_effort=True)
            raise
        self._restore_charging()

    def kill(self):
        for process_name in ('BatteryLifeDiagnosticTool.exe', 'bldtUI.exe'):
            try:
                self._kill(process_name)
            except Exception:
                logging.debug("BLDT process was not running: %s", process_name)
        self._restore_charging(best_effort=True)
