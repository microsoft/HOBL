# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Host orchestration tests. No RPC, installers, or DUT access is performed."""
import base64
import hashlib
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


def load_scenario():
    framework = types.ModuleType('scenarios')
    app = types.ModuleType('scenarios.app_scenario')
    app.Scenario = type('Scenario', (), {'setUp': lambda self: None})
    framework.app_scenario = app
    parameters = types.ModuleType('parameters')
    parameters.Params = type('Params', (), {'setDefault': staticmethod(lambda *a, **k: None), 'get': Mock()})
    path = Path(__file__).parents[1] / 'llvm.py'
    spec = importlib.util.spec_from_file_location('llvm', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'scenarios': framework, 'scenarios.app_scenario': app, 'parameters': parameters}):
        spec.loader.exec_module(module)
    return module


def decode(command):
    return base64.b64decode(command[1].split()[-1]).decode('utf-16-le')


class MsiPrepTests(unittest.TestCase):
    def setUp(self):
        self.module = load_scenario()
        self.temp = tempfile.TemporaryDirectory(prefix='hobl-llvm-test-')
        self.addCleanup(self.temp.cleanup)
        self.msi = Path(self.temp.name) / "approved compiler's build.msi"
        self.msi.write_bytes(b'fake MSI bytes - never installed')
        self.sha = hashlib.sha256(self.msi.read_bytes()).hexdigest()
        self.values = {'platform': 'Windows', 'loops': '1', 'installer_path': str(self.msi),
                       'installer_sha256': self.sha, 'compiler_version': '24.0.0', 'allow_unsigned_installer': '1'}
        self.module.Params.get.side_effect = lambda section, key: self.values[key]
        self.scenario = self.module.Llvm()
        self.scenario.dut_exec_path = r'D:\hobl_bin'
        self.scenario.result_dir = 'unused'
        self.scenario.prep_status_enable = True
        self.scenario.checkPrepStatus = Mock(return_value='missing')
        self.scenario._check_remote_file_exists = Mock(return_value=True)
        for name in ('_upload', '_call', '_copy_data_from_remote', '_remote_make_dir', 'createPrepStatusControlFile'):
            setattr(self.scenario, name, Mock())

    def test_selected_msi_is_uploaded_and_passed_safely(self):
        self.scenario.setUp()
        self.assertEqual(self.scenario.prep_version, '10')
        self.scenario._upload.assert_any_call(str(self.msi), self.scenario.target, check_modified=False)
        command = decode(self.scenario._call.call_args.args[0])
        self.assertIn("compiler''s build.msi'", command)
        self.assertIn(f"-InstallerSha256 '{self.sha}'", command)
        self.assertIn('-AllowUnsignedInstaller', command)
        self.scenario.createPrepStatusControlFile.assert_called_once_with('10')

    def test_bad_hash_fails_before_upload(self):
        self.values['installer_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.scenario.setUp()
        self.scenario._upload.assert_not_called()
        self.scenario._call.assert_not_called()

    def test_unsigned_requires_explicit_switch(self):
        self.values['allow_unsigned_installer'] = '0'
        self.scenario.setUp()
        self.assertNotIn('-AllowUnsignedInstaller', decode(self.scenario._call.call_args.args[0]))

    def test_matching_selection_reuses_prep(self):
        self.scenario.checkPrepStatus.return_value = ''
        self.scenario.setUp()
        self.scenario._upload.assert_not_called()
        self.scenario._call.assert_not_called()

    def test_selection_change_forces_prep_even_with_base_marker(self):
        self.scenario.checkPrepStatus.return_value = ''
        self.scenario._check_remote_file_exists.side_effect = [False, True]
        self.scenario.setUp()
        self.scenario._upload.assert_any_call(str(self.msi), self.scenario.target, check_modified=False)

    def test_selection_marker_failure_is_not_prep_success(self):
        self.scenario._check_remote_file_exists.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'marker could not be created'):
            self.scenario.setUp()
        self.scenario.createPrepStatusControlFile.assert_not_called()

    def test_switch_a_b_a_repreps_each_selection(self):
        markers = set()
        self.scenario.checkPrepStatus.return_value = ''
        self.scenario._check_remote_file_exists.side_effect = lambda path: path in markers
        self.scenario._remote_make_dir.side_effect = lambda path: markers.add(path[len(self.scenario.dut_exec_path) + 1:])
        # Actual framework directory uploads remove and recreate resources in
        # both remote and local_execution modes; file uploads leave them alone.
        self.scenario._upload.side_effect = lambda source, *a, **kw: markers.clear() if source.endswith('llvm_resources') else None
        other = Path(self.temp.name) / 'other.msi'
        other.write_bytes(b'another fake MSI - never installed')
        for path in (self.msi, other, self.msi):
            self.values.update(installer_path=str(path), installer_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            self.scenario.setUp()
            self.assertEqual(len(markers), 1)
        self.assertEqual(self.scenario._call.call_count, 3)

    def test_invalid_options_fail_before_upload(self):
        for updates in ({'installer_sha256': ''}, {'compiler_version': '24'},
                        {'installer_path': 'compiler.exe'}, {'installer_path': ''}):
            original = self.values.copy()
            with self.subTest(updates=updates):
                self.values.update(updates)
                with self.assertRaises(ValueError):
                    self.scenario.setUp()
                self.scenario._upload.assert_not_called()
                self.scenario._call.assert_not_called()
            self.values = original

    def test_missing_package_fails_before_upload(self):
        self.msi.unlink()
        with self.assertRaises(FileNotFoundError):
            self.scenario.setUp()
        self.scenario._upload.assert_not_called()

    def test_upload_failure_does_not_run_installer_or_write_markers(self):
        self.scenario._upload.side_effect = [None, RuntimeError('transfer failed')]
        with self.assertRaisesRegex(RuntimeError, 'transfer failed'):
            self.scenario.setUp()
        self.scenario._call.assert_not_called()
        self.scenario._remote_make_dir.assert_not_called()
        self.scenario.createPrepStatusControlFile.assert_not_called()

    @unittest.skipUnless(os.name == 'nt' and shutil.which('pwsh'), 'Requires Windows PowerShell 7')
    def test_encoded_command_roundtrips_literals_and_failure_status(self):
        script = Path(self.temp.name) / "echo arguments' & test.ps1"
        script.write_text('param([string]$InstallerPath, [switch]$AllowUnsignedInstaller, [int]$ExitCode)\n'
                          '@{ Path=$InstallerPath; Unsigned=[bool]$AllowUnsignedInstaller } | ConvertTo-Json -Compress\n'
                          'exit $ExitCode\n', encoding='utf-8')
        value = "D:\\approved package's & $(not-a-command);` MSI.msi"
        for exit_code in (0, 37):
            with self.subTest(exit_code=exit_code):
                command = self.module.Llvm._powershell_command(str(script), InstallerPath=value,
                                                               AllowUnsignedInstaller=True, ExitCode=exit_code)
                # RPC uses executable + one argument STRING, equivalent to
                # Windows CreateProcess (not shell=True). EncodedCommand
                # normalizes a called script's nonzero exit to 1; HOBL needs
                # the success/failure distinction, not the original MSI code.
                command_line = subprocess.list2cmdline([shutil.which('pwsh')]) + ' ' + command[1]
                result = subprocess.run(command_line, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0 if exit_code == 0 else 1, result.stderr)
                self.assertEqual(json.loads(result.stdout), {'Path': value, 'Unsigned': True})

    def test_failed_prep_does_not_write_success_markers(self):
        self.scenario._call.side_effect = RuntimeError('reboot required')
        with self.assertRaisesRegex(RuntimeError, 'reboot required'):
            self.scenario.setUp()
        self.scenario._copy_data_from_remote.assert_called_once()
        self.scenario.createPrepStatusControlFile.assert_not_called()
        self.scenario._remote_make_dir.assert_not_called()

    def test_default_keeps_existing_install_path(self):
        self.values.update(installer_path='', installer_sha256='', compiler_version='', allow_unsigned_installer='0')
        self.scenario.setUp()
        self.assertEqual(self.scenario.compiler_version, '21.1.8')
        self.assertNotIn('-InstallerPath', decode(self.scenario._call.call_args.args[0]))
        self.assertEqual(self.scenario._upload.call_count, 1)

    def test_run_passes_expected_compiler_identity(self):
        self.scenario.setUp()
        self.scenario._call.reset_mock()
        self.scenario.runTest()
        command = decode(self.scenario._call.call_args.args[0])
        self.assertIn("-CompilerVersion '24.0.0'", command)
        self.assertIn(f"-InstallerSha256 '{self.sha}'", command)
        self.assertNotIn('-InstallerPath', command)

    def test_disabled_prep_check_does_not_force_prep(self):
        self.scenario.checkPrepStatus.return_value = ''
        self.scenario.prep_status_enable = False
        self.scenario.setUp()
        self.scenario._check_remote_file_exists.assert_not_called()
        self.scenario._upload.assert_not_called()


if __name__ == '__main__':
    unittest.main()