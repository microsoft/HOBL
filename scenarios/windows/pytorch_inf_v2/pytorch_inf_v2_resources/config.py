# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Pinned configuration for the pytorch_inf_v2 (Windows) LLM inference scenario.

This module intentionally has zero third-party imports so it can be loaded
(and unit tested) on a host with no GPU, no torch, and no network access.
All exact pins below come from the confirmed design for the pytorch_inf
replacement; do not change a pin without updating this single source of
truth and bumping prep_version in pytorch_inf_v2.py.
"""

# -- Interpreter -------------------------------------------------------------
PYTHON_VERSION = "3.14.8"

# -- Portable BF16 lane (fits an 8 GB GPU budget) -----------------------------
PORTABLE_MODEL = "Qwen/Qwen3-1.7B"
PORTABLE_REVISION = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"

# -- Quantized headline lane ---------------------------------------------------
QUANT_MODEL = "Qwen/Qwen3-8B"
QUANT_REVISION = "b968826d9c46dd6066d109eabc6255188de91218"

# -- Windows x64 package pins (standard PyTorch CUDA wheel index) ------------
TORCH_VERSION_X64 = "2.14.0+cu134"
TORCHVISION_VERSION_X64 = "0.29.0+cu134"  # optional; only needed if vision ops are exercised
PYTORCH_CUDA_INDEX_URL = "https://download.pytorch.org/whl/cu134"

# -- Windows Arm64 (N1X) package pins -----------------------------------------
# N1X ships an NVIDIA GPU; CPU-only Arm64 wheels are not an acceptable
# substitute for the GPU-first design, so we pull NVIDIA's out-of-tree CUDA
# build for Arm64 and verify its SHA256 before installation (see
# pytorch_inf_v2_prep.ps1). This is NOT a standard PyPI/pytorch.org index.
TORCH_VERSION_ARM64 = "2.14.0+cu134"
TORCH_ARM64_INDEX_URL = "https://pypi.nvidia.com/nvtorch_oot/torch/"
TORCH_ARM64_SHA256_CP314 = "628b98e48595e1055942d697015ade14ea06d4a75a64720787e53d94dcc98c27"
# CP314 == CPython 3.14 ABI tag used in the wheel filename pyenv-win's
# "3.14.8-arm" build produces (cp314-cp314-win_arm64).
TORCH_ARM64_WHEEL_NAME = "torch-2.14.0+cu134-cp314-cp314-win_arm64.whl"

# -- Shared Windows package pins ----------------------------------------------
# NOTE: design target was transformers==5.19.0, but the Microsoft-managed
# package feed proxy (packagefeedproxy.microsoft.io, required by CISO Central
# Feed Services policy -- direct public PyPI is blocked on managed devices)
# had not mirrored 5.19.0 as of the last real hardware validation pass, and
# tops out at 5.18.0 (confirmed via `pip index versions transformers` against
# the proxy). 5.18.0 fully supports the Qwen3 architecture used by this
# scenario, so it is used as the closest proxy-available substitute. Revisit
# this pin once 5.19.0 is mirrored.
TRANSFORMERS_VERSION = "5.18.0"
TRITON_WINDOWS_VERSION = "3.8.0.post29"
TORCHAO_VERSION = "0.18.0"

# -- Explicit, separate CPU fallback (never blended with the GPU lane) -------
CPU_FALLBACK_TORCH_INDEX_URL = "https://download.pytorch.org/whl/cpu"

# -- Workload shapes -----------------------------------------------------------
BATCH_SIZE = 1
SHAPES = {
    "short": {"prompt_tokens": 128, "max_new_tokens": 128},
    "long": {"prompt_tokens": 4096, "max_new_tokens": 128},
    "sustained": {"duration_seconds": 900},  # HOBL-compatible 15-minute sustained option
}

# -- Lanes / tiers / quantization options -------------------------------------
MODEL_TIERS = ("portable", "quantized")
LANES = ("eager", "compiled")
QUANT_MODES = ("none", "int4", "nvfp4")  # Windows side: TorchAO/Inductor INT4, NVFP4 micro-exponent
DEFAULT_WARMUP_ITERATIONS = 2
DEFAULT_TIMED_REPETITIONS = 5

# Minimum NVIDIA compute capability (sm_100 == Blackwell) required for a
# genuine NVFP4 (E2M1) kernel path. Below this, the lane must be gated off
# rather than silently emulated or run on CPU.
NVFP4_MIN_COMPUTE_CAPABILITY = (10, 0)
