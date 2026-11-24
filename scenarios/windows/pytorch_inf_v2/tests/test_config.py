# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Hardware-free config/pin tests for pytorch_inf_v2 (Windows).

No torch/transformers import, no DUT access, no network access.
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


class ConfigPinTests(unittest.TestCase):
    def setUp(self):
        self.config = _load("config")

    def test_python_version_pin(self):
        self.assertEqual(self.config.PYTHON_VERSION, "3.14.8")

    def test_portable_model_pin(self):
        self.assertEqual(self.config.PORTABLE_MODEL, "Qwen/Qwen3-1.7B")
        self.assertEqual(self.config.PORTABLE_REVISION, "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e")

    def test_quant_model_pin(self):
        self.assertEqual(self.config.QUANT_MODEL, "Qwen/Qwen3-8B")
        self.assertEqual(self.config.QUANT_REVISION, "b968826d9c46dd6066d109eabc6255188de91218")

    def test_torch_pins(self):
        self.assertEqual(self.config.TORCH_VERSION_X64, "2.14.0+cu134")
        self.assertEqual(self.config.TORCH_VERSION_ARM64, "2.14.0+cu134")
        self.assertEqual(self.config.TORCHVISION_VERSION_X64, "0.29.0+cu134")
        self.assertEqual(self.config.TRANSFORMERS_VERSION, "5.18.0")
        self.assertEqual(self.config.TRITON_WINDOWS_VERSION, "3.8.0.post29")
        self.assertEqual(self.config.TORCHAO_VERSION, "0.18.0")

    def test_torch_arm64_wheel_sha256_pin(self):
        self.assertEqual(
            self.config.TORCH_ARM64_SHA256_CP314,
            "628b98e48595e1055942d697015ade14ea06d4a75a64720787e53d94dcc98c27",
        )
        self.assertTrue(self.config.TORCH_ARM64_WHEEL_NAME.endswith(".whl"))
        self.assertIn("cp314", self.config.TORCH_ARM64_WHEEL_NAME)
        self.assertIn("win_arm64", self.config.TORCH_ARM64_WHEEL_NAME)

    def test_shapes_defined(self):
        self.assertIn("short", self.config.SHAPES)
        self.assertIn("long", self.config.SHAPES)
        self.assertIn("sustained", self.config.SHAPES)
        self.assertEqual(self.config.SHAPES["short"]["prompt_tokens"], 128)
        self.assertEqual(self.config.SHAPES["short"]["max_new_tokens"], 128)
        self.assertEqual(self.config.SHAPES["long"]["prompt_tokens"], 4096)
        self.assertEqual(self.config.SHAPES["long"]["max_new_tokens"], 128)

    def test_model_tiers_and_lanes_and_quant_modes(self):
        self.assertEqual(set(self.config.MODEL_TIERS), {"portable", "quantized"})
        self.assertEqual(set(self.config.LANES), {"eager", "compiled"})
        self.assertEqual(set(self.config.QUANT_MODES), {"none", "int4", "nvfp4"})


if __name__ == "__main__":
    unittest.main()
