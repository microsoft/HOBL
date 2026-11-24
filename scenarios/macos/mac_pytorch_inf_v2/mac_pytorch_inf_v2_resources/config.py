# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Pinned configuration for the mac_pytorch_inf_v2 (macOS) LLM inference scenario.

This module intentionally has zero third-party imports so it can be loaded
(and unit tested) on a host with no GPU, no torch/mlx, and no network access.
All exact pins below come from the confirmed design for the pytorch_inf
replacement; do not change a pin without updating this single source of
truth and bumping prep_version in mac_pytorch_inf_v2.py.
"""

# -- Interpreter -------------------------------------------------------------
PYTHON_VERSION = "3.14.8"

# -- Portable BF16 lane (fits an 8 GB GPU budget) -----------------------------
PORTABLE_MODEL = "Qwen/Qwen3-1.7B"
PORTABLE_REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"

# -- Quantized headline lane ---------------------------------------------------
QUANT_MODEL = "Qwen/Qwen3-8B"
QUANT_REVISION = "b968826d9c46dd6066d109eabc6255188de91218"

# -- Mac package pins ----------------------------------------------------------
# Portable lane runs on torch/MPS (standard PyTorch macOS wheel, Metal by
# default). Quantized headline INT4/MXFP4 lanes run on the MLX-optimized
# stack instead of torch -- see select_framework() in capability.py.
TORCH_VERSION = "2.14.0"
TRANSFORMERS_VERSION = "5.19.0"
MLX_VERSION = "0.32.3"
MLX_LM_VERSION = "0.32.0"

# Microsoft-managed devices resolve base packages through the approved feed
# proxy (CISO Central Feed Services policy); torch wheels still come from the
# standard PyPI/pytorch.org distribution for macOS (Metal/MPS support is
# built into the default macOS wheel, no special index needed).
PYPI_INDEX_URL = "https://packagefeedproxy.microsoft.io/pypi/simple"

# -- Workload shapes -----------------------------------------------------------
BATCH_SIZE = 1
SHAPES = {
    "short": {"prompt_tokens": 128, "max_new_tokens": 128},
    "long": {"prompt_tokens": 4096, "max_new_tokens": 128},
    "sustained": {"duration_seconds": 900},  # HOBL-compatible 15-minute sustained option
}

# -- Lanes / tiers / quantization options / frameworks ------------------------
MODEL_TIERS = ("portable", "quantized")
LANES = ("eager", "compiled")
# Mac side: MLX INT4 and MLX MXFP4 (E2M1 micro-exponent) are the quantized
# headline peers to Windows TorchAO INT4 / NVFP4. Named "mxfp4" (not
# "nvfp4") because the two formats are not claimed to be identical -- see
# capability.gate_quant_lane() and the README.
QUANT_MODES = ("none", "int4", "mxfp4")
# "torch" (MPS) runs the portable BF16 lane and the quantized tier's
# unquantized baseline; "mlx" runs the quantized INT4/MXFP4 lanes.
FRAMEWORKS = ("torch", "mlx")
DEFAULT_WARMUP_ITERATIONS = 2
DEFAULT_TIMED_REPETITIONS = 5
