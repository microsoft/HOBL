# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Analyze one Software Hygiene report through Intel BLDT and collect its report bundle."""

import base64
import csv
import hashlib
import json
import logging
import ntpath
from pathlib import Path, PureWindowsPath
import re
import shutil
import tempfile
import zipfile

import core.app_scenario
from core.parameters import Params


class BldtAiAnalysis(core.app_scenario.Scenario):
    """Run Intel's Software Hygiene AI analysis on an existing report.

    Steps:
    1. Install the AI edition and upload the selected host JSON report.
    2. Run BLDT's AIAnalysis flow, including native model initialization (Global region).
    3. Collect fresh matching HTML, JSON and ZIP reports, assets, logs and metrics.

    Prep automatically stops any existing BLDT session before installation or analysis.
    AC power is recommended, not required; no power checks or charger control.
    No DAQ measurement or new diagnostic collection.
    scenario_runtime measures BLDT, including its initialization but excluding MSI prep.
    Prep-only mode installs BLDT without running analysis or requiring an input report.
    Missing WMI source data is logged as skipped; other analyzer errors fail the run.
    Success means complete execution and reports, not passing every Intel health check.
    Collected reports normalize Intel's non-JSON numeric values to null for browser rendering.
    Unmodified bundles are retained in intel_originals when normalization is needed.
    """

    is_prep = True
    module = __module__.split('.')[-1]
    Params.setDefault(
        module, 'input_file', '',
        desc='Absolute HOST path to an existing native Software Hygiene JSON report.',
    )

    def setUp(self):
        self.input_path = None
        self.no_wmi_data = False
        if not self.prep_run_only:
            self.input_path = Path(Params.get(self.module, 'input_file').strip())
            if not self.input_path.is_absolute() or not self.input_path.is_file():
                raise ValueError('bldt_ai_analysis:input_file must be an existing absolute HOST file path.')
            source = self.input_path.read_bytes()
            report = json.loads(source.decode('utf-8-sig'))
            if (
                self.input_path.suffix.lower() != '.json' or not isinstance(report, dict)
                or report.get('name') != 'SWHygiene'
                or not isinstance(report.get('data'), list) or not report['data']
            ):
                raise ValueError('input_file must be a native Software Hygiene JSON report, not HOBL metrics.')
            native_source = ntpath.basename(str(report.get('source', '')))
            if not re.fullmatch(r'SWHygiene_[A-Za-z0-9_-]+\.zip', native_source):
                raise ValueError('input_file must retain its native SWHygiene source ZIP filename.')
            self.input_relative = ntpath.splitext(native_source)[0] + '.json'
            self.input_sha256 = hashlib.sha256(source).hexdigest()
            wmi = [item for item in report['data']
                   if isinstance(item, dict) and isinstance(item.get('Config'), dict)
                   and item['Config'].get('type') == 'wmiActivity']
            self.no_wmi_data = (
                len(wmi) == 1 and wmi[0].get('Results') is None
                and isinstance(wmi[0].get('ErrorMsg'), dict)
                and wmi[0]['ErrorMsg'].get('Title') == 'No WMI Activity Found'
            )
        self.prep()
        super().setUp()

    def prep(self):
        """Install the AI edition; leave model setup and analysis to Intel's native flow."""
        if getattr(self, 'installation', None) is not None:
            return
        script = Path(__file__).with_name('bldt_ai_analysis_resources') / 'bldt_ai_analysis_prep.ps1'
        remote_script = ntpath.join(self.dut_exec_path, script.name)
        try:
            self._upload_verified(script, remote_script)
            prepared = json.loads(self._powershell(
                '& $prepScript -CacheRoot $cache -LogRoot $logs',
                timeout=32460, prepScript=remote_script,
                cache=ntpath.join(self.dut_exec_path, 'bldt_resources'), logs=self.dut_data_path,
            ))
            if self.input_path is not None:
                # Intel discovers source reports by native filename directly in its report root.
                self.remote_input = ntpath.join(self._report_files()['root'], self.input_relative)
                self._upload_verified(self.input_path, self.remote_input, self.input_sha256, preserve_existing=True)
            self.installation = prepared
            logging.info("BLDT AI edition ready: %s", prepared)
        except Exception:
            try:
                self._copy_data_from_remote(self.result_dir)
            except Exception:
                logging.exception("Could not collect BLDT AI preparation logs.")
            raise

    def _upload_verified(self, source, target, expected=None, preserve_existing=False):
        """Upload only missing/changed files and verify the bytes used by the DUT."""
        expected = expected or hashlib.sha256(source.read_bytes()).hexdigest()
        check = """
            Import-Module (Join-Path $PSHOME 'Modules\\Microsoft.PowerShell.Utility\\Microsoft.PowerShell.Utility.psd1')
            $matches = (Test-Path -LiteralPath $path -PathType Leaf) -and
                ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -eq $expected)
            ConvertTo-Json -InputObject $matches -Compress
        """
        if json.loads(self._powershell(check, path=target, expected=expected)):
            logging.info("BLDT AI file is current; skipping upload: %s", target)
            return
        if preserve_existing:
            self._powershell("""
                if (Test-Path -LiteralPath $path) {
                    throw "A different native report already exists at $path; refusing to overwrite it."
                }
            """, path=target)
        directory = ntpath.dirname(target)
        self._powershell('New-Item -ItemType Directory -Path $path -Force | Out-Null', path=directory)
        # HOBL uploads into a directory and preserves the source basename.
        with tempfile.TemporaryDirectory() as temporary:
            staged = Path(temporary, ntpath.basename(target))
            shutil.copyfile(source, staged)
            self._upload(str(staged), directory, check_modified=False)
        if not json.loads(self._powershell(check, path=target, expected=expected)):
            raise RuntimeError(f'BLDT AI file hash mismatch after upload: {target}')

    @staticmethod
    def _check_result(result, phase, skipped_wmi_error=''):
        allowed = {
            ' '.join(f'ERROR - Error analyzing wmiActivity: {skipped_wmi_error}'.split()),
            ' '.join(f'ERROR - Analysis failed: {skipped_wmi_error}'.split()),
        } if skipped_wmi_error else set()
        errors = [line for line in result['errors'] if ' '.join(line.split()) not in allowed]
        if result['exit_code'] != 0 or errors:
            detail = '; '.join(errors) or f"exit code {result['exit_code']}"
            raise RuntimeError(f'BLDT AI {phase} failed: {detail}. See its stdout/stderr logs.')

    def runTest(self):
        if self.prep_run_only:
            return
        before = self._report_files()
        try:
            result = self._run_process(
                self.installation['executable'],
                f'--type AIAnalysis --params "inputFile:{self.input_relative};region:global" --telemetry=false',
                ntpath.join(self.dut_data_path, 'bldt_ai_analysis'), 10800,
            )
        except Exception:
            try:
                self._stage_reports(before, self.dut_data_path)
            except Exception:
                logging.exception("Could not stage partial BLDT AI reports after execution failed.")
            raise
        reports = self._stage_reports(before, self.dut_data_path)
        metrics = {
            'scenario_runtime': round(result['seconds'], 3),
            'bldt_exit_code': result['exit_code'],
            'bldt_version': self.installation['version'],
            'input_file': str(self.input_path),
            'input_sha256': self.input_sha256,
            'report_file_count': reports['files'],
        }
        directory = Path(self.result_dir)
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / 'bldt_ai_analysis_results.csv').open('w', newline='', encoding='utf-8') as stream:
            csv.writer(stream).writerows(metrics.items())
        logging.info("========== BLDT AI analysis metrics ==========")
        for key, value in metrics.items():
            logging.info("%s: %s", key, value)
        if result['exit_code'] != 0:
            self._check_result(result, 'analysis')
        complete = [
            stem for stem, formats in reports['sets'].items()
            if {'html', 'json', 'zip'} <= formats
        ]
        if len(complete) != 1:
            self._check_result(result, 'analysis')
            raise RuntimeError('BLDT did not produce one fresh, nonempty matching AIAnalysis HTML/JSON/ZIP report set.')
        analysis = self._read_analysis(ntpath.join(self.dut_data_path, complete[0]))
        skipped_wmi_error = ''
        for error in analysis['errors']:
            if (self.no_wmi_data and error['module'] == 'wmiActivity'
                    and error['message'].startswith('WMI Activity validation failed: ["Missing required columns:')):
                skipped_wmi_error = error['message']
                logging.warning(
                    "Skipping WMI analysis: the source report explicitly contains no WMI activity. "
                    "Intel's native report retains its no-data error notice."
                )
            else:
                raise RuntimeError(f"BLDT AI module error: {error['module']}: {error['message']}")
        if analysis['error_count'] != len(analysis['errors']):
            raise RuntimeError('BLDT AI report has inconsistent module error counts; see analysis_report.json.')
        self._check_result(result, 'analysis', skipped_wmi_error)

    def _report_files(self):
        """Snapshot Intel's report tree so old bundles cannot satisfy this invocation."""
        snapshot = json.loads(self._powershell(r"""
            $root = Join-Path (Get-Item -LiteralPath $env:USERPROFILE).FullName 'Intel\BatteryLifeDiagnostic'
            $files = @(
                if (Test-Path -LiteralPath $root) {
                    Get-ChildItem -LiteralPath $root -Recurse -File | ForEach-Object {
                        [pscustomobject]@{
                            path = $_.FullName.Substring($root.Length).TrimStart('\')
                            size = $_.Length; modified = [string]$_.LastWriteTimeUtc.Ticks
                        }
                    }
                }
            )
            [pscustomobject]@{ root = $root; files = $files } | ConvertTo-Json -Depth 4 -Compress
        """))
        snapshot['files'] = {
            item['path']: (item['size'], item['modified']) for item in snapshot['files']
        }
        return snapshot

    def _stage_reports(self, before, destination):
        """Preserve Intel's folders and shared HTML assets, like the other BLDT scenarios."""
        after = self._report_files()
        if after['root'] != before['root']:
            raise RuntimeError('BLDT report directory changed during the run.')
        changed = {
            name: metadata for name, metadata in after['files'].items()
            if before['files'].get(name) != metadata
        }
        selected = {
            name: metadata for name, metadata in after['files'].items()
            if name in changed or PureWindowsPath(name).parts[0].lower() == 'assets'
        }
        files = []
        for name, (size, _) in selected.items():
            path = PureWindowsPath(name)
            if path.drive or path.root or '..' in path.parts:
                raise RuntimeError(f'Invalid relative BLDT report path: {name}')
            files.append({'path': name, 'size': size})
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
            """, root=after['root'], destination=destination, files=json.dumps(files[start:start + 20]))
        report_sets = {}
        for name, (size, _) in changed.items():
            path = PureWindowsPath(name)
            suffix = path.suffix.lower()
            expected_stem = ntpath.splitext(self.input_relative)[0] + '.AIAnalysis'
            if (size > 0 and path.stem.lower() == expected_stem.lower()
                    and suffix in ('.html', '.htm', '.json', '.zip')):
                report_sets.setdefault(str(path.with_suffix('')), set()).add(
                    'html' if suffix == '.htm' else suffix[1:]
                )
        return {'sets': report_sets, 'files': len(selected)}

    def _read_analysis(self, stem):
        """Validate the native bundle and read only its execution-error summary."""
        return json.loads(self._powershell(r"""
            $report = Get-Content -LiteralPath "$stem.json" -Raw | ConvertFrom-Json
            if ($report.name -ne 'AIAnalysis' -or $report.data -isnot [array] -or $report.data.Count -eq 0) {
                throw 'BLDT JSON is not an AIAnalysis report.'
            }
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $zip = [IO.Compression.ZipFile]::OpenRead("$stem.zip")
            try {
                $source = $zip.GetEntry('source_report.json')
                $entry = $zip.GetEntry('analysis_report.json')
                if ($null -eq $source -or $source.Length -eq 0 -or $null -eq $entry -or $entry.Length -eq 0) {
                    throw 'BLDT AI ZIP is missing source_report.json or analysis_report.json.'
                }
                $stream = $source.Open()
                $sha = [Security.Cryptography.SHA256]::Create()
                try { $hash = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '') }
                finally { $stream.Dispose(); $sha.Dispose() }
                if ($hash -ne $expected) { throw 'BLDT AI bundle does not match the selected input report.' }
                $reader = [IO.StreamReader]::new($entry.Open())
                try { $analysis = $reader.ReadToEnd() | ConvertFrom-Json }
                finally { $reader.Dispose() }
                if ($null -eq $analysis.results -or $null -eq $analysis.results.modules -or
                    @($analysis.results.modules.PSObject.Properties).Count -eq 0 -or
                    $null -eq $analysis.results.error) {
                    throw 'AI analysis JSON has no module results or error count.'
                }
                $errors = @($analysis.results.modules.PSObject.Properties | Where-Object {
                    $_.Value.is_error -eq $true
                } | ForEach-Object {
                    [pscustomobject]@{ module = $_.Name; message = [string]$_.Value.error_message }
                })
                [pscustomobject]@{ error_count = $analysis.results.error; errors = $errors } |
                    ConvertTo-Json -Depth 4 -Compress
            } finally { $zip.Dispose() }
        """, stem=stem, expected=self.input_sha256))

    def tearDown(self):
        """Collect native reports and repair nonstandard JSON without changing the findings."""
        super().tearDown()
        for bundle in Path(self.result_dir).rglob('*.AIAnalysis.zip'):
            if 'intel_originals' not in bundle.relative_to(self.result_dir).parts:
                self._repair_report_bundle(bundle)

    @staticmethod
    def _repair_report_bundle(bundle):
        """Normalize analysis data in all native formats, retaining Intel's original files."""
        def normalize(text):
            constants = []
            data = json.loads(text, parse_constant=lambda value: constants.append(value))
            if not constants:
                return text
            return json.dumps(data, indent=2, ensure_ascii=True, allow_nan=False)

        html_path = bundle.with_suffix('.html')
        json_path = bundle.with_suffix('.json')
        html = html_path.read_text(encoding='utf-8-sig')
        report = json.loads(json_path.read_text(encoding='utf-8-sig'))
        changed_widgets = 0
        for widget in report['data']:
            files = widget.get('FileData', {})
            if 'analysis_report.json' in files:
                original = files['analysis_report.json']
                files['analysis_report.json'] = normalize(original)
                changed_widgets += files['analysis_report.json'] != original

        # Parse the JSON string arguments, not a regex replacement of the word "NaN".
        decoder = json.JSONDecoder()
        replacements = []
        calls = list(re.finditer(r'(?m)^\s*ai_(?:summary|system_summary|report)_ingest\(', html))
        if len(calls) != 3:
            raise RuntimeError('Unexpected BLDT AI HTML initialization; cannot safely normalize its data.')
        for call in calls:
            _, end = decoder.raw_decode(html, call.end())
            start = end
            while start < len(html) and html[start].isspace():
                start += 1
            if html[start:start + 1] != ',':
                raise RuntimeError('Invalid BLDT AI HTML data arguments.')
            start += 1
            while start < len(html) and html[start].isspace():
                start += 1
            original, end = decoder.raw_decode(html, start)
            normalized = normalize(original)
            if normalized != original:
                literal = json.dumps(normalized, ensure_ascii=True)
                literal = literal.replace('<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')
                replacements.append((start, end, literal))
        for start, end, literal in reversed(replacements):
            html = html[:start] + literal + html[end:]

        with zipfile.ZipFile(bundle) as archive:
            required = {
                html_path.name, json_path.name, 'analysis_report.json',
                'AIAnalyzer/json_reports/analysis_report.json',
            }
            if not required <= set(archive.namelist()):
                raise RuntimeError('BLDT AI ZIP is missing report copies needed for JSON normalization.')
            normalized_analysis = {
                name: normalize(archive.read(name).decode('utf-8-sig'))
                for name in required if name.endswith('analysis_report.json')
            }
            changed_archive = any(
                text != archive.read(name).decode('utf-8-sig')
                for name, text in normalized_analysis.items()
            )
            if not (changed_widgets or replacements or changed_archive):
                return
            if (archive.read(html_path.name) != html_path.read_bytes()
                    or archive.read(json_path.name) != json_path.read_bytes()):
                raise RuntimeError('Native HTML/JSON differ from their ZIP copies; refusing to overwrite them.')
            originals = bundle.parent / 'intel_originals'
            paths = (html_path, json_path, bundle)
            for path in paths:
                backup = originals / path.name
                if backup.exists() and backup.read_bytes() != path.read_bytes():
                    raise RuntimeError(f'An earlier original backup already exists: {backup}')
            with tempfile.TemporaryDirectory(dir=bundle.parent) as temporary:
                staged = Path(temporary)
                (staged / html_path.name).write_text(html, encoding='utf-8')
                (staged / json_path.name).write_text(
                    json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False), encoding='utf-8',
                )
                with zipfile.ZipFile(staged / bundle.name, 'w') as repaired:
                    repaired.comment = archive.comment
                    for entry in archive.infolist():
                        if entry.filename in normalized_analysis:
                            content = normalized_analysis[entry.filename].encode('utf-8')
                        elif entry.filename in (html_path.name, json_path.name):
                            content = (staged / entry.filename).read_bytes()
                        else:
                            content = archive.read(entry)
                        repaired.writestr(entry, content)
                originals.mkdir(exist_ok=True)
                for path in paths:
                    if not (originals / path.name).exists():
                        shutil.copy2(path, originals / path.name)
                # Close the original ZIP before replacing it on Windows.
                archive.close()
                replaced = []
                try:
                    for path in paths:
                        (staged / path.name).replace(path)
                        replaced.append(path)
                except OSError:
                    for path in replaced:
                        shutil.copy2(originals / path.name, path)
                    raise
        logging.warning(
            "Normalized nonstandard AI numeric values to null in %s and its HTML/JSON reports. "
            "Intel originals are preserved in %s.", bundle.name, originals,
        )

    def kill(self):
        """Stop only the recorded process from this invocation, if still running."""
        path = getattr(self, '_process_path', None)
        if not path:
            return
        try:
            self._powershell("""
                if (Test-Path -LiteralPath $path) {
                    $saved = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
                    $process = Get-Process | Where-Object { $_.Id -eq $saved.pid }
                    if ($process -and [string]$process.StartTime.ToUniversalTime().Ticks -eq $saved.started) {
                        Stop-Process -Id $process.Id -Force
                    }
                }
            """, timeout=30, path=path)
        except Exception:
            logging.exception("Could not stop the BLDT AI process; check the DUT.")

    def _powershell(self, script, timeout=300, **values):
        assignments = '\n'.join(
            f"${name} = '" + str(value).replace("'", "''") + "'" for name, value in values.items()
        )
        command = (
            "$ErrorActionPreference = 'Stop'\n$ProgressPreference = 'SilentlyContinue'\n"
            f"{assignments}\ntry {{\n{script}\n}} catch {{\n"
            "Write-Output (' ERROR - ' + $_.Exception.Message)\nexit 1\n}"
        )
        encoded = base64.b64encode(command.encode('utf-16-le')).decode('ascii')
        return self._call(
            ['powershell.exe',
             f'-NoProfile -NonInteractive -OutputFormat Text -ExecutionPolicy Bypass -EncodedCommand {encoded}'],
            timeout=timeout,
        )

    def _run_process(self, executable, arguments, prefix, timeout):
        """Use Intel's native CLI with captured logs and a DUT-side timeout."""
        self._process_path = prefix + '.process.json'
        return json.loads(self._powershell(r"""
            New-Item -ItemType Directory -Path (Split-Path -Parent $prefix) -Force | Out-Null
            $timer = [Diagnostics.Stopwatch]::StartNew()
            $process = Start-Process -FilePath $exe -ArgumentList $arguments `
                -WorkingDirectory (Split-Path -Parent $exe) -PassThru `
                -RedirectStandardOutput "$prefix.stdout.log" -RedirectStandardError "$prefix.stderr.log"
            try {
                $null = $process.Handle
                [pscustomobject]@{ pid = $process.Id; started = [string]$process.StartTime.ToUniversalTime().Ticks } |
                    ConvertTo-Json -Compress | Set-Content -LiteralPath "$prefix.process.json" -Encoding UTF8
                if (-not $process.WaitForExit([int]$seconds * 1000)) {
                    Stop-Process -Id $process.Id -Force
                    $null = $process.WaitForExit(10000)
                    throw "BLDT AI process timed out after $seconds seconds."
                }
                $process.WaitForExit()
                $timer.Stop()
                if ($null -eq $process.ExitCode) { throw 'BLDT AI process exit code is unavailable.' }
                [pscustomobject]@{
                    exit_code = $process.ExitCode; seconds = $timer.Elapsed.TotalSeconds
                    errors = @(Select-String -LiteralPath "$prefix.stdout.log", "$prefix.stderr.log" `
                        -Pattern '^\s*ERROR(?:\s*:\s*|\s+-\s+)' | ForEach-Object { $_.Line.Trim() })
                } | ConvertTo-Json -Depth 3 -Compress
            } finally { $process.Dispose() }
        """, timeout=timeout + 60, exe=executable, arguments=arguments, prefix=prefix, seconds=timeout))
