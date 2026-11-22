# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Build-option tests without RPC, SDK installs, or Aspire builds."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


SCENARIO_DIR = Path(__file__).resolve().parents[1]
MAC_SCENARIO_DIR = SCENARIO_DIR.parents[1] / 'macos' / 'mac_net_aspire'
SHELL = shutil.which('zsh') or shutil.which('bash')


class ScenarioConfigurationTestCase(unittest.TestCase):
    scenario_dir = SCENARIO_DIR
    scenario_class = 'NetAspire'
    platform = 'Windows'
    resource_platform = 'windows'
    dut_exec_path = r'D:\hobl_bin'
    binlog_switch = '-binlog'

    def setUp(self):
        core = types.ModuleType('core')
        app = types.ModuleType('core.app_scenario')
        app.Scenario = type('Scenario', (), {'setUp': lambda self: None})
        core.app_scenario = app
        parameters = types.ModuleType('core.parameters')
        parameters.Params = types.SimpleNamespace(setDefault=Mock(), get=Mock())
        module_name = self.scenario_dir.name
        spec = importlib.util.spec_from_file_location(module_name, self.scenario_dir / f'{module_name}.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'core': core, 'core.app_scenario': app, 'core.parameters': parameters}):
            spec.loader.exec_module(module)
        defaults = {(section, key): value for (section, key, value), _ in parameters.Params.setDefault.call_args_list}
        self.values = {'platform': self.platform, 'loops': '2'}
        parameters.Params.get.side_effect = lambda section, key: self.values.get(key, defaults.get((section, key)))
        self.scenario = getattr(module, self.scenario_class)()
        self.scenario.dut_exec_path = self.dut_exec_path
        self.scenario.password = 'unused'
        self.scenario.result_dir = 'unused'
        self.scenario.checkPrepStatus = Mock(return_value='')
        for name in ('_upload', '_call', '_copy_data_from_remote', 'createPrepStatusControlFile'):
            setattr(self.scenario, name, Mock())


class BinlogConfigurationTests(ScenarioConfigurationTestCase):
    def test_default_preserves_existing_run_command_and_prep(self):
        self.scenario.setUp()
        self.scenario._call.reset_mock()
        self.scenario.runTest()
        self.scenario._upload.assert_not_called()
        self.assertEqual(self.scenario._call.call_count, 2)
        for call in self.scenario._call.call_args_list:
            self.assertNotIn(self.binlog_switch, call.args[0][1])

    def test_enabled_refreshes_prepared_dut_script_and_forwards_each_loop(self):
        self.values['binlog'] = '1'
        self.scenario.setUp()
        extension = 'ps1' if self.platform == 'Windows' else 'sh'
        self.scenario._upload.assert_called_once_with(
            f'scenarios\\{self.resource_platform}\\{self.scenario.module}\\{self.scenario.resources}\\{self.scenario.module}_run.{extension}',
            self.scenario.target, check_modified=False)
        self.scenario.createPrepStatusControlFile.assert_not_called()
        self.scenario._call.reset_mock()
        self.scenario.runTest()
        self.assertEqual(self.scenario._call.call_count, 2)
        for call in self.scenario._call.call_args_list:
            self.assertTrue(call.args[0][1].endswith(f' {self.binlog_switch}'))

    def test_enabled_first_prep_does_not_duplicate_resource_upload(self):
        self.values['binlog'] = '1'
        self.scenario.checkPrepStatus.return_value = 'missing'
        self.scenario.setUp()
        self.scenario._upload.assert_called_once_with(
            f'scenarios\\{self.resource_platform}\\{self.scenario.module}\\{self.scenario.resources}',
            self.scenario.dut_exec_path)
        self.scenario.createPrepStatusControlFile.assert_called_once()


class MacBinlogConfigurationTests(BinlogConfigurationTests):
    scenario_dir = MAC_SCENARIO_DIR
    scenario_class = 'MacNetAspire'
    platform = 'MacOS'
    resource_platform = 'MacOS'
    dut_exec_path = '/Users/Shared/hobl_bin'
    binlog_switch = '--binlog'


class WindowsBuildExperimentConfigurationTests(ScenarioConfigurationTestCase):
    def test_experiments_refresh_the_script_and_forward_independent_options(self):
        for skip, max_cpu_count, binlog in (('1', '0', '0'), ('0', '12', '0'), ('1', '12', '1')):
            with self.subTest(skip=skip, max_cpu_count=max_cpu_count, binlog=binlog):
                self.setUp()
                self.values.update(skip_playwright_browser_install=skip, max_cpu_count=max_cpu_count, binlog=binlog)
                self.scenario.setUp()
                self.scenario._upload.assert_called_once_with(
                    r'scenarios\windows\net_aspire\net_aspire_resources\net_aspire_run.ps1',
                    self.scenario.target, check_modified=False)
                self.scenario.createPrepStatusControlFile.assert_not_called()
                self.scenario._call.reset_mock()
                self.scenario.runTest()
                self.assertEqual(self.scenario._call.call_count, 2)
                for call in self.scenario._call.call_args_list:
                    command = call.args[0][1]
                    self.assertEqual('-skipPlaywrightBrowserInstall' in command, skip == '1')
                    self.assertEqual('-maxCpuCount 12' in command, max_cpu_count == '12')
                    self.assertEqual('-binlog' in command, binlog == '1')

    def test_invalid_parallelism_fails_before_upload_or_prep(self):
        for value in ('-1', '12.5', 'twelve', '2147483648'):
            with self.subTest(value=value):
                self.values['max_cpu_count'] = value
                with self.assertRaisesRegex(ValueError, 'max_cpu_count'):
                    self.scenario.setUp()
                self.scenario._upload.assert_not_called()
                self.scenario._call.assert_not_called()


@unittest.skipUnless(os.name == 'nt' and shutil.which('pwsh'), 'Requires Windows PowerShell 7')
class BinlogScriptTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='hobl aspire binlog ')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for folder in ('hobl_data', 'hobl_bin', 'aspire'):
            (self.root / folder).mkdir()
        (self.root / 'aspire' / 'Aspire.slnx').touch()
        self.wrapper = self.root / 'invoke-test.ps1'
        self.wrapper.write_text(r'''
param([string]$RunScript, [string]$TestRoot, [switch]$Binlog, [int]$BuildExitCode,
      [switch]$SkipPlaywrightBrowserInstall, [int]$MaxCpuCount = 0)
$ErrorActionPreference = 'Stop'
function Split-Path {
    param([string]$Path, [switch]$Qualifier, [switch]$Parent)
    if ($Qualifier) { return $TestRoot }
    Microsoft.PowerShell.Management\Split-Path -Path $Path -Parent:$Parent
}
function dotnet {
    ConvertTo-Json -InputObject @($args) -Compress |
        Add-Content -LiteralPath (Join-Path $TestRoot 'dotnet-calls.jsonl')
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'build') {
        foreach ($arg in $args) {
            if ($arg.StartsWith('-bl:')) {
                Set-Content -LiteralPath $arg.Substring(4) -Value 'mock binary log'
            }
        }
        $global:LASTEXITCODE = $BuildExitCode
    }
}
& $RunScript -binlog:$Binlog -skipPlaywrightBrowserInstall:$SkipPlaywrightBrowserInstall -maxCpuCount $MaxCpuCount
exit $LASTEXITCODE
''', encoding='utf-8')

    def run_script(self, enabled=False, build_exit_code=0, skip_playwright=False, max_cpu_count=0):
        command = [shutil.which('pwsh'), '-NoProfile', '-NonInteractive', '-File', str(self.wrapper),
                   '-RunScript', str(SCENARIO_DIR / 'net_aspire_resources' / 'net_aspire_run.ps1'),
                   '-TestRoot', str(self.root), '-BuildExitCode', str(build_exit_code)]
        if enabled:
            command.append('-Binlog')
        if skip_playwright:
            command.append('-SkipPlaywrightBrowserInstall')
        if max_cpu_count:
            command.extend(['-MaxCpuCount', str(max_cpu_count)])
        return subprocess.run(command, capture_output=True, text=True, timeout=60)

    def dotnet_calls(self):
        return [json.loads(line) for line in (self.root / 'dotnet-calls.jsonl').read_text(encoding='utf-8').splitlines()]

    def test_disabled_build_has_no_binary_logger(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        build = next(call for call in self.dotnet_calls() if call[0] == 'build')
        self.assertEqual(build, ['build', 'Aspire.slnx', '--no-restore'])
        self.assertEqual(list((self.root / 'hobl_data').glob('*.binlog')), [])

    def test_enabled_builds_keep_separate_logs_in_results_directory(self):
        for _ in range(2):
            result = self.run_script(enabled=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = self.dotnet_calls()
        builds = [call for call in calls if call[0] == 'build']
        self.assertEqual(len(builds), 2)
        paths = []
        for build in builds:
            self.assertEqual(build[:3], ['build', 'Aspire.slnx', '--no-restore'])
            self.assertEqual(len(build), 4)
            self.assertTrue(build[3].startswith('-bl:'))
            path = Path(build[3][4:])
            self.assertEqual(path.parent, self.root / 'hobl_data')
            self.assertTrue(path.is_file())
            paths.append(path)
        self.assertNotEqual(paths[0], paths[1])
        for call in calls:
            if call[0] in ('clean', 'restore'):
                self.assertFalse(any(arg.startswith('-bl:') for arg in call))

    def test_binary_logging_preserves_build_failure(self):
        result = self.run_script(enabled=True, build_exit_code=37)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / 'hobl_data' / 'net_aspire_results.csv').exists())

    def test_experiments_change_only_the_requested_build_argument(self):
        for skip, max_cpu_count, expected in (
                (True, 0, '-p:InstallBrowsersForPlaywright=false'),
                (False, 12, '-m:12')):
            with self.subTest(skip=skip, max_cpu_count=max_cpu_count):
                result = self.run_script(skip_playwright=skip, max_cpu_count=max_cpu_count)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                build = self.dotnet_calls()[-1]
                self.assertEqual(build, ['build', 'Aspire.slnx', '--no-restore', expected])
        for call in self.dotnet_calls():
            if call[0] in ('clean', 'restore'):
                self.assertEqual(len(call), 2)

    def test_experiment_options_can_be_combined_with_binary_logging(self):
        result = self.run_script(enabled=True, skip_playwright=True, max_cpu_count=12)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        build = self.dotnet_calls()[-1]
        self.assertEqual(build[:5], ['build', 'Aspire.slnx', '--no-restore',
                                    '-p:InstallBrowsersForPlaywright=false', '-m:12'])
        self.assertEqual(len(build), 6)
        self.assertTrue(build[5].startswith('-bl:'))
        self.assertTrue(Path(build[5][4:]).is_file())

    def test_invalid_parallelism_is_rejected_before_running_dotnet(self):
        for value in (-1, 'twelve', 2147483648):
            with self.subTest(value=value):
                result = self.run_script(max_cpu_count=value)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse((self.root / 'dotnet-calls.jsonl').exists())


@unittest.skipUnless(SHELL, 'Requires zsh or bash')
class MacBinlogScriptTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='hobl-mac-aspire-binlog-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for folder in ('hobl_data', 'aspire'):
            (self.root / folder).mkdir()
        self.test_root = self.shell_path(self.root)
        self.runner = self.root / 'run.sh'
        source = (MAC_SCENARIO_DIR / 'mac_net_aspire_resources' / 'mac_net_aspire_run.sh').read_text(encoding='utf-8')
        for original, replacement in (
                ('/Users/Shared/hobl_data', '$TEST_ROOT/hobl_data'),
                ('/Users/Shared/hobl_bin/aspire', '$TEST_ROOT/aspire'),
                ('~/.zprofile', '"$TEST_ROOT/.zprofile"'),
                ('/usr/bin/time', '"$TEST_ROOT/time"')):
            self.assertIn(original, source)
            source = source.replace(original, replacement)
        self.runner.write_text(source, encoding='utf-8', newline='\n')
        (self.root / '.zprofile').write_text('bc() { cat >/dev/null; echo 0.30; }\n'
                                           'date() { echo 20261120_133115; }\n', encoding='utf-8', newline='\n')
        (self.root / 'time').write_text('''#!/bin/sh
time_file="$3"
shift 3
"$@"
status=$?
printf 'real 1.25\\nuser 0.20\\nsys 0.10\\n' > "$time_file"
exit "$status"
''', encoding='utf-8', newline='\n')
        (self.root / 'aspire' / 'build.sh').write_text('''#!/bin/sh
printf '%s\\t' "$@" >> "$TEST_ROOT/build-calls"
printf '\\n' >> "$TEST_ROOT/build-calls"
if [ "$1" = "--build" ]; then
    for arg in "$@"; do
        case "$arg" in
            /bl:*) printf 'mock binary log' > "${arg#/bl:}" ;;
        esac
    done
    exit "${BUILD_EXIT_CODE:-0}"
fi
''', encoding='utf-8', newline='\n')
        for path in (self.root / 'time', self.root / 'aspire' / 'build.sh'):
            path.chmod(0o755)

    def shell_path(self, path):
        if os.name != 'nt':
            return str(path)
        result = subprocess.run([SHELL, '-c', 'cygpath -u "$1"', '_', str(path)],
                                capture_output=True, text=True, timeout=30, check=True)
        return result.stdout.strip()

    def run_script(self, enabled=False, build_exit_code=0):
        command = [SHELL, self.shell_path(self.runner)]
        if enabled:
            command.append('--binlog')
        env = dict(os.environ, TEST_ROOT=self.test_root, BUILD_EXIT_CODE=str(build_exit_code))
        return subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)

    def build_calls(self):
        return [line.rstrip('\t').split('\t') for line in
                (self.root / 'build-calls').read_text(encoding='utf-8').splitlines()]

    def test_disabled_build_preserves_existing_arguments(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.build_calls(), [['--clean'], ['--restore'], ['--build']])
        self.assertEqual(list((self.root / 'hobl_data').glob('*.binlog')), [])

    def test_enabled_builds_keep_separate_logs_and_unchanged_timing(self):
        for _ in range(2):
            result = self.run_script(enabled=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        builds = [call for call in self.build_calls() if call[0] == '--build']
        self.assertEqual(len(builds), 2)
        paths = []
        for build in builds:
            self.assertEqual(len(build), 2)
            self.assertTrue(build[1].startswith('/bl:'))
            self.assertTrue(build[1][4:].startswith(f'{self.test_root}/hobl_data/'))
            path = self.root / 'hobl_data' / build[1].rsplit('/', 1)[-1]
            self.assertTrue(path.is_file())
            paths.append(path)
        self.assertNotEqual(paths[0], paths[1])
        for call in self.build_calls():
            if call[0] != '--build':
                self.assertEqual(len(call), 1)
        metrics = (self.root / 'hobl_data' / 'mac_net_aspire_results.csv').read_text(encoding='utf-8')
        self.assertIn('scenario_runtime,1.25\n', metrics)
        self.assertIn('build_real,1.25\n', metrics)

    def test_binary_logging_preserves_build_failure(self):
        result = self.run_script(enabled=True, build_exit_code=37)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / 'hobl_data' / 'mac_net_aspire_results.csv').exists())
        self.assertEqual(len(list((self.root / 'hobl_data').glob('*.binlog'))), 1)


if __name__ == '__main__':
    unittest.main()
