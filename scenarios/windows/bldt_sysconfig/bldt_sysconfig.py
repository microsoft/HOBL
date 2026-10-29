# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Coordinate SysConfig on the host; run prep and Intel BLDT remotely on the DUT."""

import base64
import csv
import hashlib
import json
import logging
import ntpath
from pathlib import Path, PureWindowsPath

import core.app_scenario
from core.parameters import Params


class BldtSysconfig(core.app_scenario.Scenario):
    """Run Intel's system power-configuration checks through HOBL.

    Intel workload: SysConfigChecks examines configuration relevant to power efficiency
    and produces diagnostic findings in native HTML, JSON and ZIP reports.

    HOBL lifecycle:
    1. Before: refresh the DUT prep script, close existing BLDT sessions, and discover
       either BLDT edition; install or repair only when needed.
    2. Run: invoke the discovered executable with the selected AC/DC assessment mode.
       This scenario does not control the charger or use DAQ measurement.
    3. After: require fresh matching reports, stage them with shared HTML assets and
       logs for host collection, and write runtime/version metrics to CSV.

    scenario_runtime measures native BLDT execution, not preparation or collection.
    No AI analysis or AI models are required.
    Success means complete execution and reports, not passing every Intel check.
    """

    # Skip normal DAQ callbacks; this does not enable HOBL's installation-only mode.
    is_prep = True
    module = __module__.split('.')[-1]

    Params.setDefault(module, 'power_source', 'AC', valOptions=['AC', 'DC'],
                      desc='Required DUT power source; does not control the charger.')

    def setUp(self):
        """Read parameters, ensure BLDT is ready, then complete HOBL setup."""
        # Validate the selected Intel power mode before any remote preparation.
        self.power_source = Params.get(self.module, 'power_source').strip().upper()

        if self.power_source not in ('AC', 'DC'):
            raise ValueError('bldt_sysconfig:power_source must be AC or DC.')

        # Discover/install BLDT before entering the framework's normal setup lifecycle.
        self.prep()
        super().setUp()

    def prep(self):
        """Discover on every invocation; install/repair only when discovery requires it."""
        # HOBL can call prep twice; reuse successful discovery only within this instance.
        if getattr(self, 'installation', None) is not None:
            return

        # The prep marker records a previous setup; BLDT may no longer be installed on the DUT
        needs_marker = bool(self.checkPrepStatus(['bldt']))
        script = Path(__file__).with_name('bldt_sysconfig_resources') / 'bldt_sysconfig_prep.ps1'
        remote_script = ntpath.join(self.dut_exec_path, script.name)

        # Script freshness is independent of BLDT installation and the shared prep marker.
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
                # Verify the received bytes rather than trusting upload completion.
                if not json.loads(self._powershell(hash_check, **hash_args)):
                    raise RuntimeError('BLDT prep script hash mismatch after upload.')
            else:
                logging.info("BLDT prep script is current; skipping upload.")
            # The DUT script decides whether to reuse, install or repair BLDT.
            # It writes details to a log file and returns installation metadata as JSON.
            output = self._powershell(
                '& $prepScript -CacheRoot $cache -LogRoot $logs',
                timeout=32460, prepScript=remote_script,
                cache=ntpath.join(self.dut_exec_path, 'bldt_resources'), logs=self.dut_data_path,
            )
            prepared = json.loads(output)
        except Exception:
            # HOBL does not guarantee tearDown after a setup failure.
            try:
                self._copy_data_from_remote(self.result_dir)
            except Exception:
                logging.exception("Could not retrieve BLDT preparation logs after setup failed.")
            raise
        # Save the discovered executable/version for execution and record prep completion.
        self.installation = prepared['installation']
        logging.info("BLDT ready: %s", self.installation)
        if needs_marker or prepared['installed']:
            self.createPrepStatusControlFile(module='bldt')

    def runTest(self):
        """Run Intel's checks, stage fresh reports, and write an execution summary."""

        # An unchanged report from an earlier assessment cannot satisfy this run.
        before = self._report_files()
        logging.info("Running BLDT SysConfigChecks on %s.", self.power_source)
        try:
            # Use the discovered executable; 900 seconds is a timeout, not a duration.
            result = self._run_process(
                self.installation['executable'],
                f'--type SysConfigChecks --params pwrsrc:{self.power_source} --telemetry=false',
                ntpath.join(self.dut_data_path, 'bldt'), 900,
                ntpath.dirname(self.installation['executable']),
            )
        except Exception:
            # Preserve partial output without hiding the original execution error.
            try:
                self._stage_reports(before, self.dut_data_path)
            except Exception:
                logging.exception("Could not stage partial BLDT reports after execution failed.")
            raise

        # Copy reports under dut_data_path; normal HOBL teardown retrieves them.
        reports = self._stage_reports(before, self.dut_data_path)
        if result['exit_code'] != 0:
            raise RuntimeError(f"BLDT SysConfigChecks failed ({result['exit_code']}); see its logs.")
        # All three formats must share a report stem, not come from different assessments.
        required = {'html', 'json', 'zip'}
        if not any(required <= formats for formats in reports['sets'].values()):
            missing = '; '.join(
                f"{name}: missing fresh, nonempty {', '.join(sorted(required - formats)).upper()}"
                for name, formats in sorted(reports['sets'].items())
            ) or 'no fresh, nonempty SysConfigChecks HTML, JSON or ZIP reports'
            raise RuntimeError(f'BLDT did not produce a complete matching report set: {missing}.')

        # Execution success is separate from Intel's diagnostic findings.
        # power_source records the requested mode, not a measured power state.
        metrics = {
            'scenario_runtime': round(result['seconds'], 3),
            'bldt_version': self.installation['version'],
            'bldt_edition': self.installation['edition'],
            'power_source': self.power_source,
            'html_report_created': 1,
            'json_report_created': int(reports['json'] > 0),
            'zip_report_created': int(reports['zip'] > 0),
            'report_file_count': reports['files'],
        }
        # Write the metrics summary at the host result root.
        directory = Path(self.result_dir)
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / 'bldt_sysconfig_results.csv').open('w', newline='', encoding='utf-8') as stream:
            csv.writer(stream).writerows(metrics.items())
        logging.info("========== BLDT SysConfig metrics ==========")
        for key, value in metrics.items():
            logging.info("%s: %s", key, value)

    def tearDown(self):
        """Let HOBL retrieve staged reports and logs; leave BLDT installed."""
        super().tearDown()

    def kill(self):
        """Stop only a BLDT process launched by this run, never an existing session."""
        # HOBL creates a new scenario instance for cleanup; ownership must survive on the DUT.
        # PID plus start time protects against stopping a different process after PID reuse.
        path = ntpath.join(self.dut_data_path, 'bldt.process.json')
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

    @staticmethod
    def _quote(value):
        """Escape a literal PowerShell value, including apostrophes in paths."""
        return "'" + str(value).replace("'", "''") + "'"

    def _powershell(self, script, timeout=300, **values):
        """Run a Windows operation on the DUT through HOBL, propagating failures."""
        # Bind caller values as literals, then wrap the remote script with explicit failure handling.
        assignments = '\n'.join(f'${name} = {self._quote(value)}' for name, value in values.items())
        command = (
            "$ErrorActionPreference = 'Stop'\n"
            "$ProgressPreference = 'SilentlyContinue'\n"
            f"{assignments}\ntry {{\n{script}\n}} catch {{\n"
            "Write-Output (' ERROR - ' + $_.Exception.Message)\nexit 1\n}"
        )
        # Suppress progress and CLIXML serialization so RPC output remains parseable JSON.
        # Quoting protects values; UTF-16LE Base64 transports the command, not encrypts it.
        encoded = base64.b64encode(command.encode('utf-16-le')).decode('ascii')
        # HOBL transports this command to the DUT and returns its output to the host.
        return self._call(
            ['powershell.exe',
             f'-NoProfile -NonInteractive -OutputFormat Text -ExecutionPolicy Bypass -EncodedCommand {encoded}'],
            timeout=timeout,
        )

    def _run_process(self, executable, arguments, log_prefix, timeout, working_directory):
        """Capture output and enforce a DUT-side timeout, not just an RPC timeout."""
        # DUT wall-clock timing includes BLDT startup, but not prep or report staging.
        # Retain the process handle so Windows PowerShell can reliably read ExitCode.
        # Give RPC extra time for termination and returning the measured result.
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
        """, timeout=timeout + 60, exe=executable, arguments=arguments, prefix=log_prefix,
            seconds=timeout, cwd=working_directory)
        return json.loads(output)

    def _report_files(self):
        """Read DUT filenames, sizes and modification times; keep snapshots in Python."""
        # Resolve short profile paths before computing relative filenames.
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
        # Relative paths preserve Intel's layout; metadata comparisons detect fresh output.
        snapshot['files'] = {
            item['path']: (item['size'], item['modified']) for item in snapshot['files']
        }
        return snapshot

    def _stage_reports(self, before, report_dir):
        """Select fresh output in Python, then copy it on the DUT for HOBL teardown."""
        # Intel report root -> DUT staging folder here; DUT -> host during teardown.
        after = self._report_files()
        if after['root'] != before['root']:
            raise RuntimeError('BLDT report directory changed during the run.')
        # Compare snapshots to select new or modified files, not historical results.
        changed = {
            name: metadata for name, metadata in after['files'].items()
            if before['files'].get(name) != metadata
        }
        # Assets may be unchanged but are still needed to display the copied HTML.
        selected = {
            name: metadata for name, metadata in after['files'].items()
            if name in changed or PureWindowsPath(name).parts[0].lower() == 'assets'
        }
        files = []
        for name, (size, _) in selected.items():
            relative = PureWindowsPath(name)
            # Never let a relative report path escape the staging directory.
            if relative.drive or relative.root or '..' in relative.parts:
                raise RuntimeError(f'Invalid relative BLDT report path: {name}')
            files.append({'path': name, 'size': size})

        # Keep batches small enough for encoded Windows command lines. Copies stay
        # on the DUT; there is no separate report download or snapshot file.
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
        # Only fresh, nonempty native report files count; assets are collected separately.
        report_sets = {}
        for name, (size, _) in changed.items():
            relative = PureWindowsPath(name)
            suffix = relative.suffix.lower()
            if (size > 0 and relative.name.lower().startswith('sysconfigchecks_')
                    and suffix in ('.html', '.htm', '.json', '.zip')):
                stem = str(relative.with_suffix('')).lower()
                report_sets.setdefault(stem, set()).add('html' if suffix == '.htm' else suffix[1:])
        return {
            **{kind: sum(kind in formats for formats in report_sets.values())
               for kind in ('html', 'json', 'zip')},
            'sets': report_sets, 'files': len(selected),
        }
