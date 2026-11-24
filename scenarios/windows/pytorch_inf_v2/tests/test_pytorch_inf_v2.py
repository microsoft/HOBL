# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Host orchestration tests for the PytorchInfV2 scenario class.

No RPC, GPU, model download, or DUT access is performed -- `_upload`, `_call`,
`_copy_data_from_remote`, `createPrepStatusControlFile`, and
`checkPrepStatusNew` are all mocked.
"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


def load_scenario():
    core = types.ModuleType('core')
    app_scenario = types.ModuleType('core.app_scenario')
    app_scenario.Scenario = type('Scenario', (), {
        'setUp': lambda self: None,
        'tearDown': lambda self: None,
    })
    core.app_scenario = app_scenario
    parameters = types.ModuleType('core.parameters')
    parameters.Params = type('Params', (), {
        'setDefault': staticmethod(lambda *a, **k: None),
        'get': Mock(),
    })
    core.parameters = parameters
    path = Path(__file__).parents[1] / 'pytorch_inf_v2.py'
    spec = importlib.util.spec_from_file_location('pytorch_inf_v2', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {
        'core': core,
        'core.app_scenario': app_scenario,
        'core.parameters': parameters,
    }):
        spec.loader.exec_module(module)
    return module


class PytorchInfV2Tests(unittest.TestCase):
    def setUp(self):
        self.module = load_scenario()
        self.values = {
            'platform': 'Windows',
            'loops': '2',
            'use_gpu': 'true',
            'model_tier': 'portable',
            'lane': 'eager',
            'quant': 'none',
            'shape': 'short',
        }
        self.module.Params.get.side_effect = lambda section, key: self.values[key]
        self.scenario = self.module.PytorchInfV2()
        self.scenario.dut_exec_path = r'D:\hobl_bin'
        self.scenario.result_dir = 'unused'
        self.scenario.checkPrepStatusNew = Mock(return_value=True)
        for name in ('_upload', '_call', '_copy_data_from_remote', 'createPrepStatusControlFile', '_kill'):
            setattr(self.scenario, name, Mock())

    def test_prep_version_is_one_for_new_scenario(self):
        # A deliberately distinct, reset prep_version -- this is a new,
        # additive scenario, not an in-place bump of pytorch_inf's.
        self.assertEqual(self.scenario.prep_version, "1")

    def test_module_and_resources_naming(self):
        self.assertEqual(self.scenario.module, 'pytorch_inf_v2')
        self.assertEqual(self.scenario.resources, 'pytorch_inf_v2_resources')

    def test_setup_uploads_resources_and_runs_prep_when_not_prepped(self):
        self.scenario.setUp()
        self.scenario._upload.assert_called_once_with(
            r'scenarios\windows\pytorch_inf_v2\pytorch_inf_v2_resources', r'D:\hobl_bin'
        )
        self.scenario._call.assert_called_once()
        args = self.scenario._call.call_args.args[0]
        self.assertEqual(args, ['pwsh', r'D:\hobl_bin\pytorch_inf_v2_resources\pytorch_inf_v2_prep.ps1'])
        self.scenario._copy_data_from_remote.assert_called_once_with('unused')
        self.scenario.createPrepStatusControlFile.assert_called_once_with('1')

    def test_setup_skips_prep_when_already_prepped(self):
        self.scenario.checkPrepStatusNew.return_value = False
        self.scenario.setUp()
        self.scenario._upload.assert_not_called()
        self.scenario._call.assert_not_called()
        self.scenario.createPrepStatusControlFile.assert_not_called()

    def test_prep_failure_does_not_write_success_marker(self):
        self.scenario._call.side_effect = RuntimeError('prep script failed')
        with self.assertRaisesRegex(RuntimeError, 'prep script failed'):
            self.scenario.setUp()
        self.scenario._copy_data_from_remote.assert_called_once()
        self.scenario.createPrepStatusControlFile.assert_not_called()

    def test_macos_platform_calls_shell_script_via_zsh(self):
        self.values['platform'] = 'macOS'
        self.scenario.setUp()
        args = self.scenario._call.call_args.args[0]
        self.assertEqual(args, ['zsh', 'D:\\hobl_bin\\pytorch_inf_v2_resources/pytorch_inf_v2_prep.sh'])

    def test_run_test_passes_tier_lane_quant_shape_for_each_loop(self):
        self.scenario.checkPrepStatusNew.return_value = False
        self.scenario.setUp()
        self.scenario._call.reset_mock()
        self.values.update(model_tier='quantized', lane='compiled', quant='int4', shape='long')
        self.scenario.model_tier = 'quantized'
        self.scenario.lane = 'compiled'
        self.scenario.quant = 'int4'
        self.scenario.shape = 'long'
        self.scenario.loops = '2'
        self.scenario.runTest()
        self.assertEqual(self.scenario._call.call_count, 2)
        command = self.scenario._call.call_args.args[0][1]
        self.assertIn('-modelTier quantized', command)
        self.assertIn('-lane compiled', command)
        self.assertIn('-quant int4', command)
        self.assertIn('-shape long', command)
        self.assertNotIn('-noGpu', command)

    def test_run_test_passes_no_gpu_flag_when_requested(self):
        self.scenario.checkPrepStatusNew.return_value = False
        self.scenario.setUp()
        self.scenario._call.reset_mock()
        self.scenario.use_gpu = False
        self.scenario.loops = '1'
        self.scenario.runTest()
        command = self.scenario._call.call_args.args[0][1]
        self.assertIn('-noGpu', command)

    def test_teardown_calls_teardown_script(self):
        self.scenario.setUp()
        self.scenario.tearDown()
        args = self.scenario._call.call_args.args[0]
        self.assertEqual(args, ['pwsh', r'D:\hobl_bin\pytorch_inf_v2_resources\pytorch_inf_v2_teardown.ps1'])

    def test_kill_swallows_exceptions(self):
        self.scenario._kill.side_effect = RuntimeError('no such process')
        self.scenario.kill()  # must not raise
        self.scenario._kill.assert_called_once_with('python.exe')


if __name__ == '__main__':
    unittest.main()
