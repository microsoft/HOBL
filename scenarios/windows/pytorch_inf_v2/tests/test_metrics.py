# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Hardware-free timing/token-accounting/statistics tests for pytorch_inf_v2
(Windows). No torch import; everything here operates on plain floats/ints.
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


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.metrics = _load("metrics")

    def test_assert_finite_passes_on_clean_values(self):
        self.metrics.assert_finite(has_nan=False, has_inf=False, where="test")

    def test_assert_finite_raises_on_nan(self):
        with self.assertRaises(self.metrics.NonFiniteOutputError):
            self.metrics.assert_finite(has_nan=True, has_inf=False, where="prefill logits")

    def test_assert_finite_raises_on_inf(self):
        with self.assertRaises(self.metrics.NonFiniteOutputError):
            self.metrics.assert_finite(has_nan=False, has_inf=True, where="decode logits")

    def test_token_timing_rejects_non_positive_token_counts(self):
        with self.assertRaises(ValueError):
            self.metrics.TokenTiming(prompt_tokens=0, output_tokens=128, ttft_s=0.1, prefill_s=0.1, decode_s=1.0, total_s=1.1)

    def test_token_timing_rejects_negative_durations(self):
        with self.assertRaises(ValueError):
            self.metrics.TokenTiming(prompt_tokens=128, output_tokens=128, ttft_s=-0.1, prefill_s=0.1, decode_s=1.0, total_s=1.1)

    def test_prefill_tokens_per_second(self):
        timing = self.metrics.TokenTiming(
            prompt_tokens=128, output_tokens=128, ttft_s=0.2, prefill_s=0.2, decode_s=1.0, total_s=1.2
        )
        self.assertAlmostEqual(timing.prefill_tokens_per_second, 128 / 0.2)

    def test_decode_tokens_per_second_excludes_the_prefill_produced_token(self):
        # 128 output tokens == 1 from prefill + 127 decode steps.
        timing = self.metrics.TokenTiming(
            prompt_tokens=128, output_tokens=128, ttft_s=0.2, prefill_s=0.2, decode_s=1.27, total_s=1.47
        )
        self.assertAlmostEqual(timing.decode_tokens_per_second, 127 / 1.27)

    def test_decode_tokens_per_second_handles_single_output_token(self):
        timing = self.metrics.TokenTiming(
            prompt_tokens=128, output_tokens=1, ttft_s=0.2, prefill_s=0.2, decode_s=0.0, total_s=0.2
        )
        self.assertEqual(timing.decode_tokens_per_second, 0.0)

    def test_summarize_rejects_empty_samples(self):
        with self.assertRaises(ValueError):
            self.metrics.summarize([])

    def test_summarize_median_odd_count(self):
        result = self.metrics.summarize([1.0, 3.0, 2.0])
        self.assertEqual(result["median"], 2.0)
        self.assertEqual(result["count"], 3)

    def test_summarize_median_even_count(self):
        result = self.metrics.summarize([1.0, 2.0, 3.0, 4.0])
        self.assertEqual(result["median"], 2.5)

    def test_summarize_p95_and_cv_zero_variance(self):
        result = self.metrics.summarize([2.0, 2.0, 2.0, 2.0])
        self.assertEqual(result["p95"], 2.0)
        self.assertEqual(result["cv"], 0.0)

    def test_summarize_single_sample_has_zero_stdev_and_cv(self):
        result = self.metrics.summarize([5.0])
        self.assertEqual(result["stdev"], 0.0)
        self.assertEqual(result["cv"], 0.0)
        self.assertEqual(result["median"], 5.0)

    def test_serialized_bytes_of_sums_positive_sizes(self):
        self.assertEqual(self.metrics.serialized_bytes_of([10, 20, 30]), 60)

    def test_serialized_bytes_of_rejects_negative_sizes(self):
        with self.assertRaises(ValueError):
            self.metrics.serialized_bytes_of([10, -1])


if __name__ == "__main__":
    unittest.main()
