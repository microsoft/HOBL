# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Run Intel BLDT Software Hygiene through HOBL."""

import json
import logging
import os
import tempfile
import zipfile

import core.app_scenario
from core.parameters import Params


class BldtSwHygiene(core.app_scenario.Scenario):
    """Run Intel's Software Hygiene assessment with optional native AI analysis.

    Intel workload: Software Hygiene records software and system activity that can
    affect battery life, then produces native HTML, JSON and ZIP reports.

    HOBL lifecycle:
    1. Before: validate the durations and detect the DUT power source. Prepare the
       standard BLDT edition, or the AI edition only when AI analysis is requested.
    2. Run: invoke SWHygiene with no charge threshold or collection delay and use
       independent durations for SoCWatch and Windows Performance Recorder. When
       requested, run AIAnalysis on the generated JSON and collect its native reports.
    3. After: stop HOBL measurement and retrieve the staged reports and logs.

    This scenario does not control the charger or require a minimum charge level.
    """

    module = __module__.split('.')[-1]
    prep_version = '5'

    Params.setDefault(module, 'collection_duration', '600', desc='Intel Software Hygiene SoCWatch collection duration in seconds (10-3600).')
    Params.setDefault(module, 'windows_performance_recorder_duration', '600', desc='Intel Software Hygiene Windows Performance Recorder duration in seconds (10-3600).')
    Params.setDefault(module, 'run_ai_analysis', '0', desc='Run Intel AI analysis after the Software Hygiene collection (0 or 1).', valOptions=['0', '1'])

    def setUp(self):
        """Read settings, prepare BLDT, and enter HOBL setup."""

        self.collection_duration = int(Params.get(self.module, 'collection_duration'))
        self.windows_performance_recorder_duration = int(
            Params.get(self.module, 'windows_performance_recorder_duration')
        )
        if not 10 <= self.collection_duration <= 3600:
            raise ValueError('bldt_sw_hygiene:collection_duration must be between 10 and 3600.')
        if not 10 <= self.windows_performance_recorder_duration <= 3600:
            raise ValueError(
                'bldt_sw_hygiene:windows_performance_recorder_duration must be '
                'between 10 and 3600.'
            )

        ai_value = str(Params.get(self.module, 'run_ai_analysis')).strip()
        if ai_value not in ('0', '1'):
            raise ValueError('bldt_sw_hygiene:run_ai_analysis must be 0 or 1.')

        self.run_ai_analysis = ai_value == '1'
        self.execution_timeout = (
            self.collection_duration
            + self.windows_performance_recorder_duration
            + 300
        )
        self.hygiene_source_json = None

        if not self.prep_run_only:
            self.power_source = self._get_power_source()

        self.prep()
        super().setUp()

    def prep(self):
        """Install the required BLDT edition once and locate its executable."""

        marker = self.module + ('_ai' if self.run_ai_analysis else '')
        prep_suffix = f'_{self.prep_version}'

        if self.checkPrepStatus([marker + prep_suffix]):
            self._install_bldt(require_ai=self.run_ai_analysis)
            self.createPrepStatusControlFile(prep_suffix, module=marker)

        self.bldt_executable = self._discover_bldt(require_ai=self.run_ai_analysis)

    def runTest(self):
        """Run the measured Software Hygiene workload and stage its reports."""

        if self.prep_run_only:
            return

        logging.info(
            'Running BLDT Software Hygiene on %s; collection_duration is %d seconds; '
            'windows_performance_recorder_duration is %d seconds.',
            self.power_source,
            self.collection_duration,
            self.windows_performance_recorder_duration,
        )
        result = self._run_hygiene()
        reports = self._copy_reports(result['started_utc'], 'SWHygiene')

        self.hygiene_source_json = reports.get('source_json')
        logging.info('Collected BLDT Software Hygiene reports: %s', reports['reports'])

        if result['exit_code'] != 0:
            raise RuntimeError(f"BLDT Software Hygiene failed ({result['exit_code']}); see its logs.")
        if not reports['reports']:
            raise RuntimeError('No BLDT Software Hygiene reports were collected.')
        if self.run_ai_analysis and not self.hygiene_source_json:
            raise RuntimeError('BLDT Software Hygiene did not produce a JSON report for AI analysis.')

        if self.run_ai_analysis:
            logging.info('Running BLDT AI analysis.')

            ai_result = self._run_ai_analysis()
            ai_reports = self._copy_reports(ai_result['started_utc'], 'AIAnalysis')

            logging.info('Collected BLDT AI Analysis reports: %s', ai_reports['reports'])

            if ai_result['exit_code'] != 0:
                raise RuntimeError(f"BLDT AI Analysis failed ({ai_result['exit_code']}); see its logs.")
            if not ai_reports['reports']:
                raise RuntimeError('No BLDT AI Analysis reports were collected.')

    def tearDown(self):
        """Stop measurement and retrieve the staged reports and logs."""

        if self.prep_run_only:
            return

        logging.info('Stopping measurement and collecting BLDT Software Hygiene results.')
        super().tearDown()

        if self.run_ai_analysis:
            self._normalize_ai_reports()

    def kill(self):
        """Stop BLDT if the scenario is cancelled."""

        try:
            self._kill('BatteryLifeDiagnosticTool.exe')
        except Exception:
            pass


    def _get_power_source(self):
        """Return AC or DC from the DUT's current power state."""

        state = int(
            self._call(
                ['powershell', '(Get-WmiObject -Class Win32_Battery -ea 0).BatteryStatus'],
                timeout=10,
            )
        )

        if state == 1:
            return 'DC'
        if state == 2:
            return 'AC'
        raise RuntimeError(f'Could not determine the DUT power source: {state}.')

    def _install_bldt(self, require_ai=False):
        """Upload the helper and install a suitable BLDT edition if needed."""

        local_script = os.path.join(
            os.path.dirname(__file__),
            'bldt_sw_hygiene_resources\\bldt_sw_hygiene_helper.ps1',
        )
        remote_script = f'{self.dut_exec_path}\\bldt_sw_hygiene_helper.ps1'
        require_ai_argument = ' -RequireAi' if require_ai else ''

        self._upload(local_script, self.dut_exec_path, check_modified=False)

        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action Install'
            f'{require_ai_argument} '
            f'-DataRoot "{self.dut_data_path}"'
        )
        self._call(['powershell.exe', arguments], timeout=10860)

    def _discover_bldt(self, require_ai=False):
        """Return a suitable installed BLDT executable path."""

        remote_script = f'{self.dut_exec_path}\\bldt_sw_hygiene_helper.ps1'
        require_ai_argument = ' -RequireAi' if require_ai else ''
        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action Discover'
            f'{require_ai_argument} '
            f'-DataRoot "{self.dut_data_path}"'
        )
        executable = self._call(
            ['powershell.exe', arguments],
            timeout=30,
        ).strip()

        logging.info('Using BLDT executable: %s', executable)
        return executable

    def _normalize_ai_reports(self):
        """Replace Intel's nonstandard NaN values in collected AI reports."""

        report_files = []
        for root, _, files in os.walk(self.result_dir):
            report_files.extend(os.path.join(root, name) for name in files)

        for report in (
            path for path in report_files if path.lower().endswith('.aianalysis.html')
        ):
            with open(report, encoding='utf-8-sig') as stream:
                text = stream.read()
            if 'NaN' in text:
                with open(report, 'w', encoding='utf-8') as stream:
                    stream.write(text.replace('NaN', 'null'))

        for report in (
            path for path in report_files if path.lower().endswith('.aianalysis.json')
        ):
            with open(report, encoding='utf-8-sig') as stream:
                text = stream.read()
            if 'NaN' in text:
                with open(report, 'w', encoding='utf-8') as stream:
                    stream.write(text.replace('NaN', 'null'))

        for report in (
            path for path in report_files if path.lower().endswith('.aianalysis.zip')
        ):
            temporary_path = None
            with zipfile.ZipFile(report, 'r') as source:
                if not any(
                    name.lower().endswith(('.html', '.json'))
                    and b'NaN' in source.read(name)
                    for name in source.namelist()
                ):
                    continue

                with tempfile.NamedTemporaryFile(
                    dir=os.path.dirname(report), suffix='.zip', delete=False
                ) as temporary:
                    temporary_path = temporary.name

                with zipfile.ZipFile(temporary_path, 'w') as destination:
                    destination.comment = source.comment
                    for entry in source.infolist():
                        content = source.read(entry)
                        if entry.filename.lower().endswith(('.html', '.json')):
                            content = content.replace(b'NaN', b'null')
                        destination.writestr(entry, content)

            try:
                if temporary_path is not None:
                    with zipfile.ZipFile(temporary_path, 'r') as repaired:
                        if repaired.testzip() is not None:
                            raise RuntimeError(f'Failed to rebuild {report.name}.')

                    os.replace(temporary_path, report)
                    temporary_path = None
            finally:
                if temporary_path is not None and os.path.exists(temporary_path):
                    os.remove(temporary_path)

    def _run_hygiene(self):
        """Run Intel's Software Hygiene workload."""

        remote_script = f'{self.dut_exec_path}\\bldt_sw_hygiene_helper.ps1'
        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action RunHygiene '
            f'-CollectionDurationSeconds {self.collection_duration} '
            f'-WindowsPerformanceRecorderDurationSeconds '
            f'{self.windows_performance_recorder_duration} '
            f'-PowerSource {self.power_source} '
            f'-DataRoot "{self.dut_data_path}"'
        )
        output = self._call(
            ['powershell.exe', arguments],
            timeout=self.execution_timeout + 60,
        )
        return json.loads(output)

    def _run_ai_analysis(self):
        """Run AI analysis and return its native process result."""

        remote_script = f'{self.dut_exec_path}\\bldt_sw_hygiene_helper.ps1'
        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action RunAi '
            f'-InputFile "{self.hygiene_source_json}" '
            f'-DataRoot "{self.dut_data_path}"'
        )
        output = self._call(['powershell.exe', arguments], timeout=10860)
        return json.loads(output)

    def _copy_reports(self, started_utc, report_kind):
        """Copy current native reports into the DUT result directory."""

        remote_script = f'{self.dut_exec_path}\\bldt_sw_hygiene_helper.ps1'
        arguments = (
            f'-NoProfile -NonInteractive -ExecutionPolicy Bypass '
            f'-File "{remote_script}" -Action CopyReports '
            f'-ReportKind {report_kind} '
            f'-StartedUtc "{started_utc}" '
            f'-DataRoot "{self.dut_data_path}"'
        )
        return json.loads(self._call(['powershell.exe', arguments], timeout=120))
