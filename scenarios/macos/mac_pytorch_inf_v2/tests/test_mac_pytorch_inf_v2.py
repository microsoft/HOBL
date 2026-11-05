# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Host orchestration tests for the MacPytorchInfV2 scenario class.

No RPC, GPU, model download, or DUT access is performed -- `_upload`, `_call`,
`_copy_data_from_remote`, `createPrepStatusControlFile`, `checkPrepStatus`,
and `_kill` are all mocked.
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
    path = Path(__file__).parents[1] / 'mac_pytorch_inf_v2.py'
    spec = importlib.util.spec_from_file_location('mac_pytorch_inf_v2', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {
        'core': core,
        'core.app_scenario': app_scenario,
        'core.parameters': parameters,
    }):
        spec.loader.exec_module(module)
    return module


class MacPytorchInfV2Tests(unittest.TestCase):
    def setUp(self):
        self.module = load_scenario()
        self.values = {
            'platform': 'macOS',
            'loops': '2',
            'use_gpu': 'true',
            'model_tier': 'portable',
            'lane': 'eager',
            'quant': 'none',
            'shape': 'short',
        }
        self.module.Params.get.side_effect = lambda section, key: self.values[key]
        self.scenario = self.module.MacPytorchInfV2()
        self.scenario.dut_exec_path = '/Users/Shared/hobl_bin'
        self.scenario.result_dir = 'unused'
        self.scenario.password = 'testpassword'
        self.scenario.checkPrepStatus = Mock(return_value=True)
        for name in ('_upload', '_call', '_copy_data_from_remote', 'createPrepStatusControlFile', '_kill'):
            setattr(self.scenario, name, Mock())

    def test_prep_version_is_one_for_new_scenario(self):
        # A deliberately distinct, reset prep_version -- this is a new,
        # additive scenario, not an in-place bump of mac_pytorch_inf's.
        self.assertEqual(self.scenario.prep_version, "1")

    def test_module_and_resources_naming(self):
        self.assertEqual(self.scenario.module, 'mac_pytorch_inf_v2')
        self.assertEqual(self.scenario.resources, 'mac_pytorch_inf_v2_resources')

    def test_setup_uploads_resources_and_runs_prep_when_not_prepped(self):
        self.scenario.setUp()
        self.scenario.checkPrepStatus.assert_called_once_with(['mac_pytorch_inf_v21'])
        self.scenario._upload.assert_called_once_with(
            r'scenarios\MacOS\mac_pytorch_inf_v2\mac_pytorch_inf_v2_resources', '/Users/Shared/hobl_bin'
        )
        # 2 get_password.sh setup calls + 1 prep.sh call.
        self.assertEqual(self.scenario._call.call_count, 3)
        prep_call = self.scenario._call.call_args_list[-1].args[0]
        self.assertEqual(
            prep_call,
            ['zsh', '/Users/Shared/hobl_bin/mac_pytorch_inf_v2_resources/mac_pytorch_inf_v2_prep.sh'],
        )
        self.scenario._copy_data_from_remote.assert_called_once_with('unused')
        self.scenario.createPrepStatusControlFile.assert_called_once_with('1')

    def test_setup_skips_prep_when_already_prepped(self):
        self.scenario.checkPrepStatus.return_value = False
        self.scenario.setUp()
        self.scenario._upload.assert_not_called()
        self.scenario._call.assert_not_called()
        self.scenario.createPrepStatusControlFile.assert_not_called()

    def test_prep_failure_does_not_write_success_marker(self):
        # Only the prep.sh invocation (inside the try/finally) fails -- the
        # preceding get_password.sh setup calls succeed.
        def _side_effect(args, **kwargs):
            if args[0] == 'zsh' and args[1].endswith('_prep.sh'):
                raise RuntimeError('prep script failed')
        self.scenario._call.side_effect = _side_effect
        with self.assertRaisesRegex(RuntimeError, 'prep script failed'):
            self.scenario.setUp()
        self.scenario._copy_data_from_remote.assert_called_once()
        self.scenario.createPrepStatusControlFile.assert_not_called()

    def test_run_test_passes_tier_lane_quant_shape_for_each_loop(self):
        self.scenario.checkPrepStatus.return_value = False
        self.scenario.setUp()
        self.scenario._call.reset_mock()
        self.scenario.model_tier = 'quantized'
        self.scenario.lane = 'compiled'
        self.scenario.quant = 'int4'
        self.scenario.shape = 'long'
        self.scenario.loops = '2'
        self.scenario.runTest()
        self.assertEqual(self.scenario._call.call_count, 2)
        command = self.scenario._call.call_args.args[0][1]
        self.assertIn('--model-tier quantized', command)
        self.assertIn('--lane compiled', command)
        self.assertIn('--quant int4', command)
        self.assertIn('--shape long', command)
        self.assertNotIn('--no-gpu', command)
        _, kwargs = self.scenario._call.call_args
        self.assertEqual(kwargs.get('timeout'), 3600)

    def test_run_test_passes_no_gpu_flag_when_requested(self):
        self.scenario.checkPrepStatus.return_value = False
        self.scenario.setUp()
        self.scenario._call.reset_mock()
        self.scenario.use_gpu = False
        self.scenario.loops = '1'
        self.scenario.runTest()
        command = self.scenario._call.call_args.args[0][1]
        self.assertIn('--no-gpu', command)

    def test_teardown_calls_teardown_script(self):
        self.scenario.setUp()
        self.scenario.tearDown()
        args = self.scenario._call.call_args.args[0]
        self.assertEqual(
            args, ['zsh', '/Users/Shared/hobl_bin/mac_pytorch_inf_v2_resources/mac_pytorch_inf_v2_teardown.sh']
        )

    def test_kill_swallows_exceptions(self):
        self.scenario._kill.side_effect = RuntimeError('no such process')
        self.scenario.kill()  # must not raise
        self.scenario._kill.assert_called_once_with('python')


if __name__ == '__main__':
    unittest.main()
