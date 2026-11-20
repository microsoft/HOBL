# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Binlog configuration tests without RPC, SDK installs, or Aspire builds."""

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


class BinlogConfigurationTests(unittest.TestCase):
    def setUp(self):
        core = types.ModuleType('core')
        app = types.ModuleType('core.app_scenario')
        app.Scenario = type('Scenario', (), {'setUp': lambda self: None})
        core.app_scenario = app
        parameters = types.ModuleType('core.parameters')
        parameters.Params = types.SimpleNamespace(setDefault=Mock(), get=Mock())
        spec = importlib.util.spec_from_file_location('net_aspire', SCENARIO_DIR / 'net_aspire.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'core': core, 'core.app_scenario': app, 'core.parameters': parameters}):
            spec.loader.exec_module(module)
        defaults = {(section, key): value for (section, key, value), _ in parameters.Params.setDefault.call_args_list}
        self.values = {'platform': 'Windows', 'loops': '2'}
        parameters.Params.get.side_effect = lambda section, key: self.values.get(key, defaults.get((section, key)))
        self.scenario = module.NetAspire()
        self.scenario.dut_exec_path = r'D:\hobl_bin'
        self.scenario.result_dir = 'unused'
        self.scenario.checkPrepStatus = Mock(return_value='')
        for name in ('_upload', '_call', '_copy_data_from_remote', 'createPrepStatusControlFile'):
            setattr(self.scenario, name, Mock())

    def test_default_preserves_existing_run_command_and_prep(self):
        self.scenario.setUp()
        self.scenario.runTest()
        self.scenario._upload.assert_not_called()
        self.assertEqual(self.scenario._call.call_count, 2)
        for call in self.scenario._call.call_args_list:
            self.assertNotIn('-binlog', call.args[0][1])

    def test_enabled_refreshes_prepared_dut_script_and_forwards_each_loop(self):
        self.values['binlog'] = '1'
        self.scenario.setUp()
        self.scenario._upload.assert_called_once_with(
            r'scenarios\windows\net_aspire\net_aspire_resources\net_aspire_run.ps1',
            self.scenario.target, check_modified=False)
        self.scenario._call.assert_not_called()
        self.scenario.createPrepStatusControlFile.assert_not_called()
        self.scenario.runTest()
        self.assertEqual(self.scenario._call.call_count, 2)
        for call in self.scenario._call.call_args_list:
            self.assertTrue(call.args[0][1].endswith(' -binlog'))

    def test_enabled_first_prep_does_not_duplicate_resource_upload(self):
        self.values['binlog'] = '1'
        self.scenario.checkPrepStatus.return_value = 'missing'
        self.scenario.setUp()
        self.scenario._upload.assert_called_once_with(
            r'scenarios\windows\net_aspire\net_aspire_resources', self.scenario.dut_exec_path)
        self.scenario.createPrepStatusControlFile.assert_called_once()


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
param([string]$RunScript, [string]$TestRoot, [switch]$Binlog, [int]$BuildExitCode)
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
& $RunScript -binlog:$Binlog
exit $LASTEXITCODE
''', encoding='utf-8')

    def run_script(self, enabled=False, build_exit_code=0):
        command = [shutil.which('pwsh'), '-NoProfile', '-NonInteractive', '-File', str(self.wrapper),
                   '-RunScript', str(SCENARIO_DIR / 'net_aspire_resources' / 'net_aspire_run.ps1'),
                   '-TestRoot', str(self.root), '-BuildExitCode', str(build_exit_code)]
        if enabled:
            command.append('-Binlog')
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


if __name__ == '__main__':
    unittest.main()
