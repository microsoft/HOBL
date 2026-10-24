# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Hardware-free device/lane/quant/framework capability-gating tests for
mac_pytorch_inf_v2 (macOS). No torch/mlx/MPS access; every GpuProbe here is
hand-constructed.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

RESOURCES_DIR = Path(__file__).parents[1] / "mac_pytorch_inf_v2_resources"


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
        probe = self.capability.GpuProbe(has_mps=True)
        self.assertEqual(self.capability.select_device(use_gpu=True, probe=probe), "mps")

    def test_select_device_gpu_requested_but_absent_raises(self):
        probe = self.capability.GpuProbe(has_mps=False)
        with self.assertRaises(self.capability.CapabilityError):
            self.capability.select_device(use_gpu=True, probe=probe)

    def test_select_device_cpu_is_explicit_opt_in_never_a_silent_fallback(self):
        probe = self.capability.GpuProbe(has_mps=True)
        # Even with MPS present, explicitly requesting CPU returns CPU -- the
        # two paths are never blended based on availability.
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

    def test_select_framework_portable_tier_is_always_torch(self):
        self.assertEqual(
            self.capability.select_framework(model_tier="portable", quant="none"), "torch"
        )

    def test_select_framework_rejects_quant_on_portable_tier(self):
        with self.assertRaises(self.capability.CapabilityError):
            self.capability.select_framework(model_tier="portable", quant="int4")

    def test_select_framework_quantized_tier_none_is_torch_baseline(self):
        self.assertEqual(
            self.capability.select_framework(model_tier="quantized", quant="none"), "torch"
        )

    def test_select_framework_quantized_tier_int4_or_mxfp4_is_mlx(self):
        self.assertEqual(
            self.capability.select_framework(model_tier="quantized", quant="int4"), "mlx"
        )
        self.assertEqual(
            self.capability.select_framework(model_tier="quantized", quant="mxfp4"), "mlx"
        )

    def test_select_framework_rejects_unknown_tier_or_quant(self):
        with self.assertRaises(ValueError):
            self.capability.select_framework(model_tier="bogus", quant="none")
        with self.assertRaises(ValueError):
            self.capability.select_framework(model_tier="portable", quant="bogus")

    def test_gate_quant_lane_none_always_available(self):
        probe = self.capability.GpuProbe()
        available, reason = self.capability.gate_quant_lane(quant="none", probe=probe)
        self.assertTrue(available)
        self.assertTrue(reason)

    def test_gate_quant_lane_rejects_unknown_quant(self):
        with self.assertRaises(ValueError):
            self.capability.gate_quant_lane(quant="bogus", probe=self.capability.GpuProbe())

    def test_gate_quant_lane_requires_mps(self):
        probe = self.capability.GpuProbe(has_mps=False)
        available, reason = self.capability.gate_quant_lane(quant="int4", probe=probe)
        self.assertFalse(available)
        self.assertIn("Apple Silicon", reason)

    def test_gate_quant_lane_requires_mlx_package(self):
        probe = self.capability.GpuProbe(has_mps=True, has_mlx=False)
        available, reason = self.capability.gate_quant_lane(quant="int4", probe=probe)
        self.assertFalse(available)
        self.assertIn("mlx", reason)

    def test_gate_quant_lane_int4_requires_mlx_quantize_support(self):
        probe = self.capability.GpuProbe(has_mps=True, has_mlx=True, has_mlx_quantize=False)
        available, reason = self.capability.gate_quant_lane(quant="int4", probe=probe)
        self.assertFalse(available)
        self.assertIn("quantization", reason)

    def test_gate_quant_lane_int4_available_when_fully_supported(self):
        probe = self.capability.GpuProbe(has_mps=True, has_mlx=True, has_mlx_quantize=True)
        available, reason = self.capability.gate_quant_lane(quant="int4", probe=probe)
        self.assertTrue(available)

    def test_gate_quant_lane_mxfp4_defaults_unavailable(self):
        # has_mlx_mxfp4 defaults to False: no genuine MXFP4 kernel path has
        # been confirmed, so this must never be silently treated as available.
        probe = self.capability.GpuProbe(has_mps=True, has_mlx=True)
        available, reason = self.capability.gate_quant_lane(quant="mxfp4", probe=probe)
        self.assertFalse(available)
        self.assertIn("MXFP4", reason)
        self.assertIn("not claimed to be identical", reason)

    def test_gate_quant_lane_mxfp4_available_when_probe_confirms_kernel(self):
        probe = self.capability.GpuProbe(has_mps=True, has_mlx=True, has_mlx_mxfp4=True)
        available, reason = self.capability.gate_quant_lane(quant="mxfp4", probe=probe)
        self.assertTrue(available)

    def test_assert_model_residency_accepts_matching_device_kind_with_index(self):
        # Real torch per-parameter device strings may carry an index (e.g.
        # 'mps:0'); this must be accepted as matching the bare 'mps'
        # expectation, mirroring the Windows CUDA residency check.
        self.capability.assert_model_residency(expected_device="mps", observed_devices=frozenset({"mps:0"}))

    def test_assert_model_residency_rejects_mixed_devices(self):
        with self.assertRaises(self.capability.CapabilityError):
            self.capability.assert_model_residency(
                expected_device="mps", observed_devices=frozenset({"mps:0", "cpu"})
            )

    def test_assert_model_residency_rejects_wrong_device(self):
        with self.assertRaises(self.capability.CapabilityError):
            self.capability.assert_model_residency(expected_device="mps", observed_devices=frozenset({"cpu"}))


if __name__ == "__main__":
    unittest.main()
