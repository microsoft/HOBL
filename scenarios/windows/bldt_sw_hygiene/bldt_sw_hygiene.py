# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Prepare Intel BLDT, run Software Hygiene once, and stage its reports for HOBL."""

import base64
import csv
import hashlib
import json
import logging
import math
import ntpath
from pathlib import Path, PureWindowsPath
import time

import core.app_scenario
from core.parameters import Params


class _BatteryStateTimeout(RuntimeError):
    """The DUT responded, but did not reach the requested battery state in time."""


class BldtSwHygiene(core.app_scenario.Scenario):
    """Assess software hygiene with Intel BLDT and collect its reports.

    Steps:
    1. Upload the prep script if missing or changed; install or repair BLDT only when needed.
    2. Reach min_battery_charge and confirm the selected power source before measurement.
    3. Run SWHygiene once on DC (default) or AC.
    4. Collect fresh matching HTML, JSON and ZIP reports, assets, logs and metrics.
    5. Restore charging after measurement.

    Prep automatically stops any existing BLDT session before installation or collection.
    Charger control is automated or manual; manual reconnect timeouts only warn.
    scenario_runtime measures the BLDT process, excluding charging and report collection.
    Either BLDT edition works without AI models; no AI analysis is run.
    Debug providers, process grouping and hidden processes are disabled; lost-event tolerance is zero.
    Prep-only mode skips charging and the workload.
    Success means complete execution and reports, not passing every Intel check.
    """

    module = __module__.split('.')[-1]

    Params.setDefault(
        module,
        'power_source',
        'DC',
        desc='Required power source for Software Hygiene (BLDT socwatch_pwrsrc).',
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
        '1800',
        desc='BLDT system/process activity collection duration in seconds.',
    )
    Params.setDefault(
        module,
        'socwatch_delay',
        '600',
        desc='BLDT delay before SoC Watch collection in seconds.',
    )
    Params.setDefault(
        module,
        'wpr_duration_power',
        '300',
        desc='Additional power collection in seconds (300 = 5 minutes; 60 for a smoke test).',
    )
    Params.setDefault(
        module,
        'charge_timeout_minutes',
        '240',
        desc='Maximum time to wait for the battery to reach min_battery_charge.',
    )

    @staticmethod
    def _get_integer_parameter(name, minimum, maximum):
        value = Params.get(BldtSwHygiene.module, name)
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f'bldt_sw_hygiene:{name} must be an integer.') from error
        if not minimum <= parsed <= maximum:
            raise ValueError(
                f'bldt_sw_hygiene:{name} must be between {minimum} and {maximum}.'
            )
        return parsed

    def prep(self):
        """Refresh changed scripts and discover BLDT; install or repair only if needed."""
        # HOBL can call prep again in prep-only mode within the same invocation.
        if getattr(self, 'installation', None) is not None:
            return
        # The marker records prep completion; live discovery still checks for missing artifacts.
        needs_marker = bool(self.checkPrepStatus(['bldt']))
        script = Path(__file__).with_name('bldt_sw_hygiene_resources') / 'bldt_sw_hygiene_prep.ps1'
        remote_script = ntpath.join(self.dut_exec_path, script.name)
        try:
            expected_hash = hashlib.sha256(script.read_bytes()).hexdigest()
            hash_check = r"""
                Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1')
                $matches = (Test-Path -LiteralPath $path -PathType Leaf) -and
                    ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -eq $expected)
                ConvertTo-Json -InputObject $matches -Compress
            """
            hash_args = {'path': remote_script, 'expected': expected_hash}
            if not json.loads(self._powershell(hash_check, **hash_args)):
                logging.info("BLDT prep script is missing or changed; uploading %s.", remote_script)
                self._upload(str(script), self.dut_exec_path, check_modified=False)
                if not json.loads(self._powershell(hash_check, **hash_args)):
                    raise RuntimeError('BLDT prep script hash mismatch after upload.')
            else:
                logging.info("BLDT prep script is current; skipping upload.")
            output = self._powershell(
                '& $prepScript -CacheRoot $cache -LogRoot $logs',
                timeout=32460, prepScript=remote_script,
                cache=ntpath.join(self.dut_exec_path, 'bldt_resources'), logs=self.dut_data_path,
            )
            prepared = json.loads(output)
        except Exception:
            try:
                self._copy_data_from_remote(self.result_dir)
            except Exception:
                logging.exception("Could not retrieve BLDT preparation logs after setup failed.")
            raise
        self.installation = prepared['installation']
        logging.info("BLDT ready: %s", self.installation)
        if needs_marker or prepared['installed']:
            self.createPrepStatusControlFile(module='bldt')

    def _get_battery_state(self):
        """Read actual DUT power state rather than trusting a relay acknowledgment."""
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
        output = self._powershell(command, timeout=30)
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError('BLDT Software Hygiene could not read the DUT battery state.')
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
                f'BLDT Software Hygiene received an invalid battery-state response: {output!r}'
            ) from error
        if 'NoSystemBattery' in state.get('battery_charge_status', ''):
            raise RuntimeError('BLDT Software Hygiene requires a DUT with a system battery.')
        if not 0 <= state['battery_percent'] <= 100:
            raise RuntimeError(
                f"BLDT Software Hygiene read an invalid battery level: {state['battery_percent']}."
            )
        return state

    def _request_charger(self, callback, action):
        """Prompt an operator or use the existing host-side charger callback."""
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
                f'BLDT Software Hygiene requires global:{action}_call for automated {self.power_source} testing.'
            )
        logging.info("Requesting charger %s through the configured host callback.", action)
        self._host_call(callback)

    def _wait_for_state(self, description, predicate, timeout_seconds, poll_seconds=30):
        """Bound charging and physical transition waits using a monotonic deadline."""
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
        """Complete charging and any disconnect before HOBL starts measurement."""
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
                # Reconnect after the run even if this scenario did not unplug the charger.
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
            # Arm cleanup before disconnecting so a failed transition still restores AC.
            self.restore_charging = True
            self._request_charger(self.charge_off_call, 'charge_off')
            self._wait_for_state(
                'DC power after disabling the charger',
                lambda state: state['power_line_status'] == 'Offline',
                timeout_seconds=120,
                poll_seconds=5,
            )

    def _restore_charging(self, best_effort=False):
        """Restore AC after measurement; only a manual reconnect timeout is advisory."""
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
            logging.exception("Failed to restore charging after BLDT Software Hygiene.")

    def setUp(self):
        """Prepare installation and power before entering HOBL's measured lifecycle."""
        self.power_source = Params.get(self.module, 'power_source').strip().upper()
        if self.power_source not in ('AC', 'DC'):
            raise ValueError('bldt_sw_hygiene:power_source must be AC or DC.')

        self.charger_mode = Params.get(self.module, 'charger_mode').strip().lower()
        if self.charger_mode not in ('automated', 'manual'):
            raise ValueError('bldt_sw_hygiene:charger_mode must be automated or manual.')

        self.min_battery_charge = self._get_integer_parameter(
            'min_battery_charge', 0, 100
        )
        self.socwatch_duration = self._get_integer_parameter(
            'socwatch_duration', 10, 86400
        )
        self.socwatch_delay = self._get_integer_parameter(
            'socwatch_delay', 0, 86400
        )
        self.wpr_duration_power = self._get_integer_parameter(
            'wpr_duration_power', 10, 86400
        )
        self.charge_timeout_minutes = self._get_integer_parameter(
            'charge_timeout_minutes', 1, 1440
        )
        # Budget all requested phases plus an hour for BLDT overhead, not battery charging.
        collection_seconds = (
            self.socwatch_delay
            + self.socwatch_duration
            + self.wpr_duration_power
            + 3600
        )
        self.bldt_timeout_minutes = math.ceil(collection_seconds / 60)

        self.charge_on_call = Params.get('global', 'charge_on_call')
        self.charge_off_call = Params.get('global', 'charge_off_call')
        if not self.prep_run_only and self.charger_mode == 'automated' and self.power_source == 'DC' and (
            not self.charge_on_call or not self.charge_off_call
        ):
            raise RuntimeError(
                'BLDT Software Hygiene DC testing requires global:charge_on_call and '
                'global:charge_off_call in the device profile.'
            )

        self.restore_charging = False

        # Installation-only runs must not disconnect the charger or start a workload.
        if self.prep_run_only:
            self.prep()
            core.app_scenario.Scenario.setUp(self)
            return

        if self.charger_mode == 'automated':
            self._ensure_charger_on()
        else:
            state = self._get_battery_state()
            if self.power_source == 'AC' or state['battery_percent'] < self.min_battery_charge:
                self._ensure_charger_on()

        self.prep()

        try:
            self._prepare_power_state()
            # Base setup starts measurement only after charging and power-source confirmation.
            core.app_scenario.Scenario.setUp(self)
        except Exception:
            self._restore_charging(best_effort=True)
            raise

    def runTest(self):
        """Measure one BLDT invocation and require fresh, matching native reports."""
        if self.prep_run_only:
            return
        # Intel retains earlier reports; only new or changed files can satisfy this run.
        before = self._report_files()
        parameters = (
            f'min_battery_charge:{self.min_battery_charge};'
            f'socwatch_duration:{self.socwatch_duration};'
            f'socwatch_delay:{self.socwatch_delay};'
            f'socwatch_pwrsrc:{self.power_source};'
            f'wpr_duration_power:{self.wpr_duration_power};'
            'socwatch_cfg:false;groupByProcessName:false;'
            'showHiddenProcesses:false;allow_lost_events:0'
        )
        logging.info(
            "Running BLDT Software Hygiene on %s power (timeout: %d minutes, not expected duration).",
            self.power_source,
            self.bldt_timeout_minutes,
        )
        logging.info("BLDT Software Hygiene parameters: %s", parameters)
        try:
            result = self._run_process(
                self.installation['executable'],
                f'--type SWHygiene --params "{parameters}" --telemetry false',
                ntpath.join(self.dut_data_path, 'bldt_sw_hygiene'),
                self.bldt_timeout_minutes * 60,
                ntpath.dirname(self.installation['executable']),
            )
        except Exception:
            try:
                self._stage_reports(before, self.dut_data_path)
            except Exception:
                logging.exception("Could not stage partial BLDT reports after execution failed.")
            raise

        reports = self._stage_reports(before, self.dut_data_path)
        metrics = {
            # DUT-side process time excludes report staging, RPC overhead and charger waits.
            'scenario_runtime': round(result['seconds'], 3),
            'bldt_exit_code': result['exit_code'],
            'bldt_version': self.installation['version'],
            'bldt_edition': self.installation['edition'],
            'power_source': self.power_source,
            'min_battery_charge': self.min_battery_charge,
            'socwatch_duration': self.socwatch_duration,
            'socwatch_delay': self.socwatch_delay,
            'wpr_duration_power': self.wpr_duration_power,
            'socwatch_cfg': 'false',
            'group_by_process_name': 'false',
            'show_hidden_processes': 'false',
            'allow_lost_events': 0,
            'report_file_count': reports['files'],
        }
        directory = Path(self.result_dir)
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / 'bldt_sw_hygiene_results.csv').open('w', newline='', encoding='utf-8') as stream:
            csv.writer(stream).writerows(metrics.items())
        logging.info("========== BLDT Software Hygiene metrics ==========")
        for key, value in metrics.items():
            logging.info("%s: %s", key, value)
        if result['exit_code'] != 0:
            raise RuntimeError(f"BLDT Software Hygiene failed ({result['exit_code']}); see its logs.")
        # Require all formats from one report, rather than combining unrelated report sets.
        required = {'html', 'json', 'zip'}
        if not any(required <= formats for formats in reports['sets'].values()):
            missing = '; '.join(
                f"{name}: missing fresh, nonempty {', '.join(sorted(required - formats)).upper()}"
                for name, formats in sorted(reports['sets'].items())
            ) or 'no fresh, nonempty SWHygiene HTML, JSON or ZIP reports'
            raise RuntimeError(f'BLDT did not produce a complete matching report set: {missing}.')

    def tearDown(self):
        """Stop measurement and collect results before attempting charger restoration."""
        try:
            logging.info("Collecting BLDT Software Hygiene logs, metrics, and reports.")
            core.app_scenario.Scenario.tearDown(self)
        except Exception:
            self._restore_charging(best_effort=True)
            raise
        self._restore_charging()

    def kill(self):
        """Stop only this run's BLDT process and attempt to restore charging."""
        # HOBL creates a new scenario instance for cleanup; ownership must survive on the DUT.
        path = ntpath.join(self.dut_data_path, 'bldt_sw_hygiene.process.json')
        try:
            self._powershell(r"""
                if (Test-Path -LiteralPath $path) {
                    $saved = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
                    $process = Get-Process | Where-Object { $_.Id -eq $saved.pid }
                    if ($process -and [string]$process.StartTime.ToUniversalTime().Ticks -eq $saved.started) {
                        Stop-Process -Id $process.Id -Force
                    }
                }
            """, timeout=30, path=path)
        except Exception:
            logging.exception("Could not stop this run's BLDT process; check the DUT.")
        self._restore_charging(best_effort=True)

    @staticmethod
    def _quote(value):
        """Escape literal values before transporting PowerShell through RPC."""
        return "'" + str(value).replace("'", "''") + "'"

    def _powershell(self, script, timeout=300, **values):
        """Keep JSON replies free of progress serialization and propagate remote errors."""
        assignments = '\n'.join(f'${name} = {self._quote(value)}' for name, value in values.items())
        command = (
            "$ErrorActionPreference = 'Stop'\n"
            "$ProgressPreference = 'SilentlyContinue'\n"
            f"{assignments}\ntry {{\n{script}\n}} catch {{\n"
            "Write-Output (' ERROR - ' + $_.Exception.Message)\nexit 1\n}"
        )
        encoded = base64.b64encode(command.encode('utf-16-le')).decode('ascii')
        return self._call(
            ['powershell.exe',
             f'-NoProfile -NonInteractive -OutputFormat Text -ExecutionPolicy Bypass -EncodedCommand {encoded}'],
            timeout=timeout,
        )

    def _run_process(self, executable, arguments, log_prefix, timeout, working_directory):
        """Capture output and stop a timed-out process on the DUT, not just the RPC."""
        output = self._powershell(r"""
            New-Item -ItemType Directory -Path (Split-Path -Parent $prefix) -Force | Out-Null
            $timer = [Diagnostics.Stopwatch]::StartNew()
            $process = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $cwd `
                -RedirectStandardOutput "$prefix.stdout.log" -RedirectStandardError "$prefix.stderr.log" -PassThru
            try {
                $null = $process.Handle
                [pscustomobject]@{ pid = $process.Id; started = [string]$process.StartTime.ToUniversalTime().Ticks } |
                    ConvertTo-Json -Compress | Set-Content -LiteralPath "$prefix.process.json" -Encoding UTF8
                if (-not $process.WaitForExit([int]$seconds * 1000)) {
                    Stop-Process -Id $process.Id -Force
                    if (-not $process.WaitForExit(10000)) { throw 'Timed-out BLDT process could not be stopped.' }
                    throw "BLDT process timed out after $seconds seconds."
                }
                $process.WaitForExit()
                if ($null -eq $process.ExitCode) { throw 'BLDT process exit code is unavailable.' }
                $timer.Stop()
                [pscustomobject]@{ exit_code = $process.ExitCode; seconds = $timer.Elapsed.TotalSeconds } |
                    ConvertTo-Json -Compress
            } finally {
                $process.Dispose()
            }
        """, timeout=timeout + 300, exe=executable, arguments=arguments, prefix=log_prefix,
            seconds=timeout, cwd=working_directory)
        return json.loads(output)

    def _report_files(self):
        """Snapshot native report metadata without writing extra state on the DUT."""
        output = self._powershell(r"""
            $root = Join-Path (Get-Item -LiteralPath $env:USERPROFILE).FullName 'Intel\BatteryLifeDiagnostic'
            $files = @(
                if (Test-Path -LiteralPath $root) {
                    Get-ChildItem -LiteralPath $root -File -Recurse | ForEach-Object {
                        [pscustomobject]@{
                            path = $_.FullName.Substring($root.Length).TrimStart('\')
                            size = $_.Length; modified = [string]$_.LastWriteTimeUtc.Ticks
                        }
                    }
                }
            )
            [pscustomobject]@{ root = $root; files = $files } | ConvertTo-Json -Depth 4 -Compress
        """)
        snapshot = json.loads(output)
        snapshot['files'] = {
            item['path']: (item['size'], item['modified']) for item in snapshot['files']
        }
        return snapshot

    def _stage_reports(self, before, report_dir):
        """Stage changed reports and required HTML assets for normal HOBL collection."""
        after = self._report_files()
        if after['root'] != before['root']:
            raise RuntimeError('BLDT report directory changed during the run.')
        changed = {
            name: metadata for name, metadata in after['files'].items()
            if before['files'].get(name) != metadata
        }
        # Shared HTML assets may be unchanged but are still needed to view fresh reports.
        selected = {
            name: metadata for name, metadata in after['files'].items()
            if name in changed or PureWindowsPath(name).parts[0].lower() == 'assets'
        }
        files = []
        for name, (size, _) in selected.items():
            relative = PureWindowsPath(name)
            if relative.drive or relative.root or '..' in relative.parts:
                raise RuntimeError(f'Invalid relative BLDT report path: {name}')
            files.append({'path': name, 'size': size})
        # Bound encoded command lengths; file contents remain on the DUT until teardown.
        for start in range(0, len(files), 20):
            self._powershell(r"""
            foreach ($file in (ConvertFrom-Json -InputObject $files)) {
                $source = Join-Path $root $file.path
                $target = Join-Path $destination $file.path
                New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
                Copy-Item -LiteralPath $source -Destination $target -Force
                if ((Get-Item -LiteralPath $target).Length -ne $file.size) {
                    throw "BLDT report staging incomplete: $($file.path)"
                }
            }
        """, root=after['root'], destination=report_dir, files=json.dumps(files[start:start + 20]))
        report_sets = {}
        for name, (size, _) in changed.items():
            relative = PureWindowsPath(name)
            suffix = relative.suffix.lower()
            if (size > 0 and relative.name.lower().startswith('swhygiene_')
                    and suffix in ('.html', '.htm', '.json', '.zip')):
                stem = str(relative.with_suffix('')).lower()
                report_sets.setdefault(stem, set()).add('html' if suffix == '.htm' else suffix[1:])
        return {'sets': report_sets, 'files': len(selected)}
