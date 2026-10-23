# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Hardware-free device/lane/quant capability-gating tests for pytorch_inf_v2
(Windows). No torch/CUDA/GPU access; every GpuProbe here is hand-constructed.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

RESOURCES_DIR = Path(__file__).parents[1] / "pytorch_inf_v2_resources"


def _load(module_name):
    path = RESOURCES_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        _load("config")
        self.capability = _load("capability")

    def test_select_device_gpu_requested_and_present(self):
        probe = self.capability.GpuProbe(has_cuda=True)
        self.assertEqual(self.capability.select_device(use_gpu=True, probe=probe), "cuda")

    def test_select_device_gpu_requested_but_absent_raises(self):
        probe = self.capability.GpuProbe(has_cuda=False)
        with self.assertRaises(self.capability.CapabilityError):
            self.capability.select_device(use_gpu=True, probe=probe)

    def test_select_device_cpu_is_explicit_opt_in_never_a_silent_fallback(self):
        probe = self.capability.GpuProbe(has_cuda=True)
        # Even with a GPU present, explicitly requesting CPU returns CPU --
        # the two paths are never blended based on availability.
        self.assertEqual(self.capability.select_device(use_gpu=False, probe=probe), "cpu")

    def test_gate_lane_rejects_unknown_lane(self):
        with self.assertRaises(ValueError):
            self.capability.gate_lane(lane="bogus", use_gpu=True)

    def test_gate_lane_compiled_requires_gpu(self):
        with self.assertRaises(self.capability.CapabilityError):
            self.capability.gate_lane(lane="compiled", use_gpu=False)
        # Should not raise:
        self.capability.gate_lane(lane="compiled", use_gpu=True)
        self.capability.gate_lane(lane="eager", use_gpu=False)

    def test_gate_quant_lane_none_always_available(self):
        probe = self.capability.GpuProbe()
        available, reason = self.capability.gate_quant_lane(quant="none", probe=probe)
        self.assertTrue(available)
        self.assertTrue(reason)

    def test_gate_quant_lane_rejects_unknown_quant(self):
        with self.assertRaises(ValueError):
            self.capability.gate_quant_lane(quant="bogus", probe=self.capability.GpuProbe())

    def test_gate_quant_lane_int4_requires_cuda(self):
        probe = self.capability.GpuProbe(has_cuda=False)
        available, reason = self.capability.gate_quant_lane(quant="int4", probe=probe)
        self.assertFalse(available)
        self.assertIn("CUDA", reason)

    def test_gate_quant_lane_int4_requires_torchao_and_triton(self):
        probe = self.capability.GpuProbe(has_cuda=True, has_torchao=False, has_triton=True)
        available, reason = self.capability.gate_quant_lane(quant="int4", probe=probe)
        self.assertFalse(available)
        self.assertIn("torchao", reason)

        probe = self.capability.GpuProbe(has_cuda=True, has_torchao=True, has_triton=False)
        available, reason = self.capability.gate_quant_lane(quant="int4", probe=probe)
        self.assertFalse(available)
        self.assertIn("triton", reason)

    def test_gate_quant_lane_int4_available_when_fully_supported(self):
        probe = self.capability.GpuProbe(has_cuda=True, has_torchao=True, has_triton=True)
        available, reason = self.capability.gate_quant_lane(quant="int4", probe=probe)
        self.assertTrue(available)

    def test_gate_quant_lane_nvfp4_requires_blackwell_compute_capability(self):
        # Ada Lovelace (sm_89) is below the sm_100 Blackwell floor.
        probe = self.capability.GpuProbe(has_cuda=True, cuda_compute_capability=(8, 9), has_torchao=True)
        available, reason = self.capability.gate_quant_lane(quant="nvfp4", probe=probe)
        self.assertFalse(available)
        self.assertIn("Blackwell", reason)

    def test_gate_quant_lane_nvfp4_available_on_blackwell_with_torchao(self):
        probe = self.capability.GpuProbe(has_cuda=True, cuda_compute_capability=(10, 0), has_torchao=True)
        available, reason = self.capability.gate_quant_lane(quant="nvfp4", probe=probe)
        self.assertTrue(available)

    def test_gate_quant_lane_nvfp4_unknown_compute_capability_is_not_available(self):
        probe = self.capability.GpuProbe(has_cuda=True, cuda_compute_capability=None, has_torchao=True)
        available, reason = self.capability.gate_quant_lane(quant="nvfp4", probe=probe)
        self.assertFalse(available)

    def test_assert_model_residency_accepts_matching_device_kind_with_index(self):
        # Real torch per-parameter device strings carry an index (e.g. 'cuda:0');
        # this must be accepted as matching the bare 'cuda' expectation.
        self.capability.assert_model_residency(expected_device="cuda", observed_devices=frozenset({"cuda:0"}))

    def test_assert_model_residency_rejects_mixed_devices(self):
        with self.assertRaises(self.capability.CapabilityError):
            self.capability.assert_model_residency(
                expected_device="cuda", observed_devices=frozenset({"cuda:0", "cpu"})
            )

    def test_assert_model_residency_rejects_wrong_device(self):
        with self.assertRaises(self.capability.CapabilityError):
            self.capability.assert_model_residency(expected_device="cuda", observed_devices=frozenset({"cpu"}))


if __name__ == "__main__":
    unittest.main()
