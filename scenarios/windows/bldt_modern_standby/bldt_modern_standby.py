# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Coordinate Intel standby on a separate host, with one relay wake and post-run evidence."""

import base64
import csv
import hashlib
import json
import logging
import math
import ntpath
from pathlib import Path, PureWindowsPath
import select
import threading
import time

import core.app_scenario
import core.call_rpc as rpc
from core.parameters import Params


class _BatteryStateTimeout(RuntimeError):
    """Distinguish a power-transition timeout from RPC or malformed-response failures."""


class BldtModernStandby(core.app_scenario.Scenario):
    """Run Intel's Modern Standby diagnostics with a host-controlled wake.

    Intel workload: mosTest requests sleep, gathers standby diagnostics, and generates
    native reports including Windows Sleep Study. Intel initiates sleep; HOBL wakes the DUT.

    HOBL lifecycle:
    1. Before: require a separate host with asynchronous communication, a wake callback,
       and rundown monitoring disabled; refresh prep, close existing BLDT sessions,
       ensure either edition is installed, and establish charge/power before measurement.
    2. Run: invoke mosTest with sleep enabled and the selected power/report settings.
       Wait without DUT polling; wake once after the requested interval plus five minutes
       for startup. Early completion cancels the pending wake; never retry the toggle.
    3. After: validate one entry/exit event interval and complete native reports, write
       CSV metrics, stop measurement, collect reports/assets/logs, then restore charging.

    scenario_runtime includes BLDT and standby, excluding charging and report collection.
    Manual reconnect timeouts only warn. No AI analysis or AI models are required.
    Prep-only mode skips charging and the workload.
    Success means the event interval and reports meet validation, not every Intel check passes.
    """

    # This is a measured scenario; sleep_duration_minutes controls host wake timing.
    module = __module__.split('.')[-1]

    Params.setDefault(
        module, 'power_source', 'DC',
        desc='Power source used for the Modern Standby collection.',
        valOptions=['AC', 'DC'],
    )
    Params.setDefault(
        module, 'charger_mode', 'automated',
        desc='automated uses charger callbacks; manual prompts and verifies power state (120-second transition timeout; post-run reconnect timeout only warns).',
        valOptions=['automated', 'manual'],
    )
    Params.setDefault(
        module, 'min_battery_charge', '90',
        desc='Minimum battery charge percentage before the BLDT collection starts.',
    )
    Params.setDefault(
        module, 'sleep_duration_minutes', '20',
        desc='Required uninterrupted Modern Standby duration (20-1440 minutes). The host adds five minutes for BLDT startup before its one wake pulse.',
    )
    Params.setDefault(
        module, 'sleep_study_days', '1',
        desc='Number of days included in the native Sleep Study report (1-28).',
    )
    Params.setDefault(
        module, 'charge_timeout_minutes', '240',
        desc='Maximum time to wait for the battery to reach min_battery_charge.',
    )

    @staticmethod
    def _get_integer_parameter(name, minimum, maximum):
        """Parse one numeric setting and reject values outside its supported range."""
        value = Params.get(BldtModernStandby.module, name)
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f'bldt_modern_standby:{name} must be an integer.') from error
        if not minimum <= parsed <= maximum:
            raise ValueError(
                f'bldt_modern_standby:{name} must be between {minimum} and {maximum}.'
            )
        return parsed

    def prep(self):
        """Refresh changed scripts and discover BLDT; install or repair only if needed."""
        # Reuse discovery only within this instance; markers do not replace live checks.
        if getattr(self, 'installation', None) is not None:
            return
        needs_marker = bool(self.checkPrepStatus(['bldt']))
        script = Path(__file__).with_name('bldt_modern_standby_resources') / 'bldt_modern_standby_prep.ps1'
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
            # The DUT script installs/repairs only if discovery cannot reuse either edition.
            output = self._powershell(
                '& $prepScript -CacheRoot $cache -LogRoot $logs',
                timeout=32460, prepScript=remote_script,
                cache=ntpath.join(self.dut_exec_path, 'bldt_resources'), logs=self.dut_data_path,
            )
            prepared = json.loads(output)
        except Exception:
            # Setup failure may skip teardown, so preserve available preparation logs here.
            try:
                self._copy_data_from_remote(self.result_dir)
            except Exception:
                logging.exception("Could not retrieve BLDT preparation logs after setup failed.")
            raise
        # Retain actual executable/version metadata and update shared prep bookkeeping.
        self.installation = prepared['installation']
        logging.info("BLDT ready: %s", self.installation)
        if needs_marker or prepared['installed']:
            self.createPrepStatusControlFile(module='bldt')

    def _get_battery_state(self):
        """Read actual DUT power state rather than trusting a relay acknowledgment."""
        # These queries run before sleep or after collection, never in the standby wait loop.
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
            raise RuntimeError('BLDT Modern Standby could not read the DUT battery state.')
        # Invalid/unknown readings must not be interpreted as ready to measure.
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
                f'BLDT Modern Standby received an invalid battery-state response: {output!r}'
            ) from error
        if 'NoSystemBattery' in state.get('battery_charge_status', ''):
            raise RuntimeError('BLDT Modern Standby requires a DUT with a system battery.')
        if not 0 <= state['battery_percent'] <= 100:
            raise RuntimeError(
                f"BLDT Modern Standby read an invalid battery level: {state['battery_percent']}."
            )
        return state

    def _request_charger(self, callback, action):
        """Prompt an operator or use the existing host-side charger callback."""
        # Manual mode sends no relay command; callers still verify Windows power state.
        if self.charger_mode == 'manual':
            instruction = 'Connect the charger' if action == 'charge_on' else 'Unplug the charger'
            logging.warning(
                "BLDT manual charger mode: %s now. Waiting up to 120 seconds "
                "for Windows to confirm the power source.", instruction,
            )
            return
        if not callback:
            raise RuntimeError(
                f'BLDT Modern Standby requires global:{action}_call for automated {self.power_source} testing.'
            )
        logging.info("Requesting charger %s through the configured host callback.", action)
        self._host_call(callback)

    def _wait_for_state(self, description, predicate, timeout_seconds, poll_seconds=30):
        """Bound charging and physical transition waits using a monotonic deadline."""
        # Wall-clock corrections must not extend or shorten a charging deadline.
        deadline = time.monotonic() + timeout_seconds
        while True:
            state = self._get_battery_state()
            logging.info(
                "Battery state while waiting for %s: %.2f%%, power=%s, charge=%s",
                description, state['battery_percent'],
                state['power_line_status'], state['battery_charge_status'],
            )
            if predicate(state):
                return state
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _BatteryStateTimeout(f'Timed out waiting for {description}.')
            time.sleep(min(poll_seconds, remaining))

    def _ensure_charger_on(self):
        # Verify actual AC rather than treating callback acknowledgment as proof of power.
        state = self._get_battery_state()
        if state['power_line_status'] != 'Online':
            self._request_charger(self.charge_on_call, 'charge_on')
            state = self._wait_for_state(
                'AC power after enabling the charger',
                lambda current: current['power_line_status'] == 'Online',
                timeout_seconds=120, poll_seconds=5,
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
                # Restore charging afterward even when this run did not disconnect it.
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
            # Arm restoration before requesting disconnection, including failed transitions.
            self.restore_charging = True
            self._request_charger(self.charge_off_call, 'charge_off')
            self._wait_for_state(
                'DC power after disabling the charger',
                lambda state: state['power_line_status'] == 'Offline',
                timeout_seconds=120, poll_seconds=5,
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
                    timeout_seconds=120, poll_seconds=5,
                )
            self.restore_charging = False
        except Exception:
            # Failure/cancellation cleanup must not replace the original assessment error.
            if not best_effort:
                raise
            logging.exception("Failed to restore charging after BLDT Modern Standby.")

    def setUp(self):
        """Validate host orchestration, then prepare installation and power."""
        # Validate collection settings before installation or charger operations.
        self.power_source = Params.get(self.module, 'power_source').strip().upper()
        if self.power_source not in ('AC', 'DC'):
            raise ValueError('bldt_modern_standby:power_source must be AC or DC.')
        self.charger_mode = Params.get(self.module, 'charger_mode').strip().lower()
        if self.charger_mode not in ('automated', 'manual'):
            raise ValueError('bldt_modern_standby:charger_mode must be automated or manual.')
        self.min_battery_charge = self._get_integer_parameter('min_battery_charge', 0, 100)
        self.sleep_duration_minutes = self._get_integer_parameter('sleep_duration_minutes', 20, 1440)
        self.sleep_study_days = self._get_integer_parameter('sleep_study_days', 1, 28)
        self.charge_timeout_minutes = self._get_integer_parameter('charge_timeout_minutes', 1, 1440)
        # The host wake deadline includes five minutes for startup; actual sleep is checked later.
        self.wake_after_seconds = self.sleep_duration_minutes * 60 + 300
        self.bldt_timeout_seconds = self.wake_after_seconds + 900
        self.charge_on_call = Params.get('global', 'charge_on_call')
        self.charge_off_call = Params.get('global', 'charge_off_call')
        self.sleep_wake_call = Params.get('global', 'sleep_wake_call')
        self.restore_charging = False
        # Per-instance host state controls the one pending wake while the DUT is unavailable.
        self._standby_cancelled = threading.Event()
        self._standby_wait = False
        self._process_path = None
        self.wake_sent = False

        if self.prep_run_only:
            self.prep()
            core.app_scenario.Scenario.setUp(self)
            return
        # Require an awake external controller and disable monitoring that would disturb sleep.
        if not self.sleep_wake_call:
            raise RuntimeError('BLDT Modern Standby requires global:sleep_wake_call in the device profile.')
        if self.async_comm != '1':
            raise RuntimeError('BLDT Modern Standby requires global:async_comm=1 for completion notification after wake.')
        if Params.get('global', 'local_execution') == '1' or self.dut_ip in (
            '127.0.0.1', '::1', 'localhost', self.host_ip,
        ):
            raise RuntimeError('BLDT Modern Standby requires a separate, awake HOBL host to operate the relay.')
        if self.rundown_mode != '0':
            raise RuntimeError('BLDT Modern Standby requires global:rundown_mode=0; rundown monitoring would disturb sleep.')
        if self.charger_mode == 'automated' and self.power_source == 'DC' and (
            not self.charge_on_call or not self.charge_off_call
        ):
            raise RuntimeError(
                'BLDT Modern Standby DC testing requires global:charge_on_call and '
                'global:charge_off_call in the device profile.'
            )
        # Prepare charge/source first; base setup starts measurement only after these checks.
        if self.charger_mode == 'automated':
            self._ensure_charger_on()
        else:
            state = self._get_battery_state()
            if self.power_source == 'AC' or state['battery_percent'] < self.min_battery_charge:
                self._ensure_charger_on()
        self.prep()
        try:
            self._prepare_power_state()
            core.app_scenario.Scenario.setUp(self)
        except Exception:
            self._restore_charging(best_effort=True)
            raise

    def _wait_for_rpc_callback(self, jobid, skt, host, port, log_output=True, timeout=1800, target_ip=None):
        """Wait on the host only; a completed job takes precedence over the wake pulse."""
        # Override framework waiting only for the BLDT workload, not ordinary setup commands.
        if not getattr(self, '_standby_wait', False):
            return super()._wait_for_rpc_callback(
                jobid, skt, host, port, log_output=log_output, timeout=timeout, target_ip=target_ip,
            )
        # Host-only deadlines avoid probing the sleeping DUT for progress or power state.
        started = time.monotonic()
        wake_at = started + self.wake_after_seconds
        deadline = started + timeout
        logging.info(
            "Leaving DUT undisturbed; one relay wake in %d seconds including 300 seconds "
            "of startup allowance. Do not interact with the DUT.", self.wake_after_seconds,
        )
        try:
            skt.listen()
            while True:
                if self._standby_cancelled.is_set():
                    raise RuntimeError('BLDT Modern Standby cancelled; pending relay wake was cancelled.')
                now = time.monotonic()
                if now >= deadline:
                    raise RuntimeError(
                        'Timed out waiting for BLDT completion. No additional relay pulse will be sent; '
                        'check the DUT and its BLDT logs.'
                    )
                readable, _, _ = select.select([skt], [], [], min(1, deadline - now))
                if readable:
                    # Completion wins over a due wake: do not toggle an already completed run.
                    client, _ = skt.accept()
                    with client:
                        client.settimeout(10)
                        if not client.recv(1024):
                            raise RuntimeError('Empty BLDT completion notification.')
                    logging.info("BLDT completion notification received; no further wake pulse is pending.")
                    return rpc.call_rpc(
                        target_ip or self.dut_ip, self.rpc_port, 'GetJobResultEx', [int(jobid)],
                        log=log_output, timeout=60,
                    )
                if not self.wake_sent and time.monotonic() >= wake_at:
                    if self._standby_cancelled.is_set():
                        raise RuntimeError('BLDT Modern Standby cancelled before relay wake.')
                    # An acknowledgment only means queued. Never retry an ambiguous toggle.
                    self.wake_sent = True
                    logging.info("Sending the single wake pulse through global:sleep_wake_call.")
                    self._host_call(self.sleep_wake_call, timeout=30)
        finally:
            skt.close()

    def _wait_for_dut_comm(self):
        """Bound framework failure recovery without toggles or hard reboots."""
        # Communication recovery may poll after the workload, but never during intentional sleep.
        if getattr(self, '_standby_wait', False):
            raise RuntimeError('DUT communication can be unavailable during the intentional BLDT standby wait.')
        deadline = time.monotonic() + 120
        while True:
            try:
                reply = json.loads(rpc.call_rpc(
                    self.dut_ip, self.rpc_port, 'GetVersion', [], log=False, timeout=10,
                ))
                if 'result' not in reply or 'error' in reply:
                    raise RuntimeError(f'Unexpected DUT communication response: {reply!r}')
                return
            except (OSError, ValueError, RuntimeError) as error:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError(
                        'DUT communication did not recover within two minutes. '
                        'Check the DUT manually; no extra sleep/wake toggle was attempted.'
                    ) from error
                logging.warning("Waiting for DUT communication after BLDT: %s", error)
                time.sleep(min(5, remaining))

    def runTest(self):
        """Run once, retain diagnostics, and reject incomplete or short sleep sessions."""
        if self.prep_run_only:
            return
        before = self._report_files()
        # Intel initiates sleep; the host schedules wake separately, not through an Intel duration.
        parameters = (
            f'min_battery_charge:{self.min_battery_charge};'
            f'sleep_study_days:{self.sleep_study_days};'
            # The installed v3.1.1 test uses sleep_pwrsrc, not the guide's pwrsrc.
            f'enable_sleep:true;sleep_pwrsrc:{self.power_source}'
        )
        logging.info("BLDT Modern Standby parameters: %s", parameters)
        try:
            # Route this command through the host-only wait override while BLDT runs.
            self._standby_wait = True
            try:
                result = self._run_process(
                    self.installation['executable'],
                    f'--type mosTest --params "{parameters}" --telemetry false',
                    ntpath.join(self.dut_data_path, 'bldt_modern_standby'),
                    self.bldt_timeout_seconds,
                    ntpath.dirname(self.installation['executable']),
                )
            finally:
                self._standby_wait = False
        except Exception:
            try:
                self._stage_reports(before, self.dut_data_path)
            except Exception:
                logging.exception("Could not stage partial BLDT reports after execution failed.")
            raise
        reports = self._stage_reports(before, self.dut_data_path)
        # Keep total BLDT wall time distinct from the event-derived standby interval.
        metrics = {
            'scenario_runtime': round(result['seconds'], 3),
            'bldt_exit_code': result['exit_code'],
            'bldt_version': self.installation['version'],
            'bldt_edition': self.installation['edition'],
            'power_source': self.power_source,
            'min_battery_charge': self.min_battery_charge,
            'sleep_study_days': self.sleep_study_days,
            'sleep_duration_minutes': self.sleep_duration_minutes,
            'wake_after_seconds': self.wake_after_seconds,
            'wake_pulse_sent': int(self.wake_sent),
            'report_file_count': reports['files'],
        }
        # Persist process metrics even when native execution or sleep validation fails.
        try:
            if result['exit_code'] != 0:
                raise RuntimeError(f"BLDT Modern Standby failed ({result['exit_code']}); see its logs.")
            if result['errors']:
                raise RuntimeError('BLDT Modern Standby reported an error: ' + '; '.join(result['errors']))
            self._validate_reports(reports)
            metrics['standby_duration_seconds'] = self._validate_sleep(result['events'])
        finally:
            directory = Path(self.result_dir)
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / 'bldt_modern_standby_results.csv').open('w', newline='', encoding='utf-8') as stream:
                csv.writer(stream).writerows(metrics.items())
            logging.info("========== BLDT Modern Standby metrics ==========")
            for key, value in metrics.items():
                logging.info("%s: %s", key, value)

    def _validate_sleep(self, events):
        """Validate this invocation's first session, not historical or summed intervals."""
        # Require exactly one ordered entry/exit pair; do not sum interrupted sessions.
        if len(events) != 2 or [event['id'] for event in events] != [506, 507]:
            raise RuntimeError(
                'Expected one complete, uninterrupted Modern Standby entry/exit pair during BLDT. '
                'See bldt_modern_standby.standby_events.json and the native Sleep Study.'
            )
        entry, exit_event = events
        duration = exit_event['seconds'] - entry['seconds']
        if (
            entry['record_id'] >= exit_event['record_id'] or entry['seconds'] < 0
            or not math.isfinite(duration) or duration < self.sleep_duration_minutes * 60
        ):
            raise RuntimeError(
                f'Modern Standby interval was {duration:.3f} seconds; '
                f'at least {self.sleep_duration_minutes * 60} seconds are required. '
                'Check for slow sleep entry or an early wake.'
            )
        return round(duration, 3)

    def _validate_reports(self, reports):
        """Use native report identity rather than guessing a mosTest filename prefix."""
        # Filenames may start with mosTest; the JSON report name must instead be mosReport.
        candidates = [
            name for name, formats in reports['sets'].items()
            if {'html', 'json', 'zip'} <= formats
        ]
        if not candidates:
            raise RuntimeError('BLDT did not produce a fresh, nonempty matching HTML, JSON and ZIP report set.')
        # Require native Sleep Study XML/HTML inside the bundle, not just outer report files.
        self._powershell(r"""
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $valid = $false
            foreach ($stem in (ConvertFrom-Json -InputObject $stems)) {
                $path = Join-Path $root $stem
                $report = Get-Content -LiteralPath "$path.json" -Raw | ConvertFrom-Json
                if ($report.name -ne 'mosReport') { continue }
                $zip = [IO.Compression.ZipFile]::OpenRead("$path.zip")
                try {
                    $entries = @($zip.Entries | Where-Object { $_.Length -gt 0 } |
                        ForEach-Object { $_.FullName.Replace('\', '/').ToLowerInvariant() })
                    if (-not ($entries -match '(^|/)utility/sleepstudy-report\.xml$') -or
                        -not ($entries -match '(^|/)utility/sleepstudy-report\.html$')) {
                        throw 'BLDT Modern Standby ZIP is missing nonempty Sleep Study XML or HTML.'
                    }
                    $valid = $true
                } finally { $zip.Dispose() }
            }
            if (-not $valid) { throw 'No fresh matching BLDT report identifies report name mosReport.' }
        """, root=self.dut_data_path, stems=json.dumps(candidates))

    def tearDown(self):
        """Stop measurement and collect results before attempting charger restoration."""
        # Charger reconnection must stay outside the measured workload power trace.
        try:
            logging.info("Collecting BLDT Modern Standby logs, metrics, and reports.")
            core.app_scenario.Scenario.tearDown(self)
        except Exception:
            self._restore_charging(best_effort=True)
            raise
        self._restore_charging()

    def kill(self):
        """Cancel the pending wake; stop only this invocation's process if reachable."""
        # Do not send a cleanup toggle: an ambiguous second pulse could put an awake DUT to sleep.
        if hasattr(self, '_standby_cancelled'):
            self._standby_cancelled.set()
        if getattr(self, '_process_path', None):
            try:
                self._powershell(r"""
                    if (Test-Path -LiteralPath $path) {
                        $saved = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
                        $process = Get-Process | Where-Object { $_.Id -eq $saved.pid }
                        if ($process -and [string]$process.StartTime.ToUniversalTime().Ticks -eq $saved.started) {
                            Stop-Process -Id $process.Id -Force
                        }
                    }
                """, timeout=30, path=self._process_path)
            except Exception:
                logging.exception("Could not stop BLDT; check the DUT manually. No cleanup wake pulse will be sent.")
        self._restore_charging(best_effort=True)

    @staticmethod
    def _quote(value):
        """Escape apostrophes so caller values remain literal PowerShell strings."""
        return "'" + str(value).replace("'", "''") + "'"

    def _powershell(self, script, timeout=300, **values):
        """Keep JSON replies free of progress serialization and propagate remote errors."""
        # Bind values as literals and propagate remote failures as nonzero command exits.
        assignments = '\n'.join(f'${name} = {self._quote(value)}' for name, value in values.items())
        command = (
            "$ErrorActionPreference = 'Stop'\n"
            "$ProgressPreference = 'SilentlyContinue'\n"
            f"{assignments}\ntry {{\n{script}\n}} catch {{\n"
            "Write-Output (' ERROR - ' + $_.Exception.Message)\nexit 1\n}"
        )
        # UTF-16LE Base64 is PowerShell's command transport format, not encryption.
        encoded = base64.b64encode(command.encode('utf-16-le')).decode('ascii')
        return self._call(
            ['powershell.exe',
             f'-NoProfile -NonInteractive -OutputFormat Text -ExecutionPolicy Bypass -EncodedCommand {encoded}'],
            timeout=timeout,
        )

    def _run_process(self, executable, arguments, log_prefix, timeout, working_directory):
        """Capture BLDT output and post-run sleep evidence without monitoring during sleep."""
        # Record process ownership before waiting; event evidence is read only after BLDT exits.
        self._process_path = log_prefix + '.process.json'
        # UTC bounds select this invocation's events; retain full XML for diagnosing rejected sleep.
        output = self._powershell(r"""
            New-Item -ItemType Directory -Path (Split-Path -Parent $prefix) -Force | Out-Null
            if (Test-Path -LiteralPath "$prefix.process.json") {
                Remove-Item -LiteralPath "$prefix.process.json"
            }
            $started = [datetime]::UtcNow
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
                $finished = [datetime]::UtcNow
                $begin = $started.ToString('o')
                $end = $finished.ToString('o')
                $filter = "*[System[Provider[@Name='Microsoft-Windows-Kernel-Power'] and " +
                    "(EventID=506 or EventID=507) and TimeCreated[@SystemTime >= '$begin' and @SystemTime <= '$end']]]"
                $query = [Diagnostics.Eventing.Reader.EventLogQuery]::new(
                    'System', [Diagnostics.Eventing.Reader.PathType]::LogName, $filter)
                $reader = [Diagnostics.Eventing.Reader.EventLogReader]::new($query)
                try {
                    $events = @(
                        while ($null -ne ($event = $reader.ReadEvent())) {
                            try {
                                [pscustomobject]@{
                                    id = $event.Id; record_id = $event.RecordId
                                    seconds = ($event.TimeCreated.ToUniversalTime() - $started).TotalSeconds
                                    utc = $event.TimeCreated.ToUniversalTime().ToString('o')
                                    xml = $event.ToXml()
                                }
                            } finally { $event.Dispose() }
                        }
                    )
                } finally { $reader.Dispose() }
                ConvertTo-Json -InputObject $events -Depth 4 |
                    Set-Content -LiteralPath "$prefix.standby_events.json" -Encoding UTF8
                [pscustomobject]@{
                    exit_code = $process.ExitCode; seconds = ($finished - $started).TotalSeconds
                    events = @($events | Select-Object id, record_id, seconds, utc)
                    errors = @(Select-String -LiteralPath "$prefix.stdout.log", "$prefix.stderr.log" `
                        -Pattern '^\s*ERROR:\s*' | ForEach-Object { $_.Line.Trim() })
                } | ConvertTo-Json -Depth 4 -Compress
            } finally {
                $process.Dispose()
            }
        """, timeout=timeout + 300, exe=executable, arguments=arguments, prefix=log_prefix,
            seconds=timeout, cwd=working_directory)
        return json.loads(output)

    def _report_files(self):
        """Snapshot native report metadata without writing extra state on the DUT."""
        # Resolve Intel's report root on the DUT and return relative path/size/time records.
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
        # Intel report root -> DUT staging here; teardown retrieves staged files to the host.
        after = self._report_files()
        if after['root'] != before['root']:
            raise RuntimeError('BLDT report directory changed during the run.')
        changed = {
            name: metadata for name, metadata in after['files'].items()
            if before['files'].get(name) != metadata
        }
        # Unchanged shared assets are still needed to render newly generated HTML.
        selected = {
            name: metadata for name, metadata in after['files'].items()
            if name in changed or PureWindowsPath(name).parts[0].lower() == 'assets'
        }
        files = []
        for name, (size, _) in selected.items():
            relative = PureWindowsPath(name)
            # Reject paths that could escape the staging directory.
            if relative.drive or relative.root or '..' in relative.parts:
                raise RuntimeError(f'Invalid relative BLDT report path: {name}')
            files.append({'path': name, 'size': size})
        # Batch metadata to keep encoded commands manageable; file contents remain on the DUT.
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
        # Group by stem first; _validate_reports checks native identity instead of a filename prefix.
        report_sets = {}
        for name, (size, _) in changed.items():
            relative = PureWindowsPath(name)
            suffix = relative.suffix.lower()
            if size > 0 and suffix in ('.html', '.htm', '.json', '.zip'):
                stem = str(relative.with_suffix('')).lower()
                report_sets.setdefault(stem, set()).add('html' if suffix == '.htm' else suffix[1:])
        return {'sets': report_sets, 'files': len(selected)}
