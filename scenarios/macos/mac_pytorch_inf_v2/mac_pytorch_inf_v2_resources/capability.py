# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Pure device/lane/quantization capability-gating logic for mac_pytorch_inf_v2.

No torch/mlx imports here on purpose: every decision function takes
already-probed facts (booleans, version strings) as arguments so this module
-- and its gating rules -- can be unit tested on a host with no GPU and no ML
packages installed. The actual probing (querying torch.backends.mps, mlx,
etc.) lives in run_benchmark.py.
"""

from dataclasses import dataclass

import config


class CapabilityError(RuntimeError):
    """Raised when a requested lane/device/framework combination cannot run as asked.

    The design mandates explicit failure over silent CPU fallback or
    pretending a lane ran, so callers should let this propagate (and the
    scenario is expected to surface it as a failed run, not a degraded one).
    """


@dataclass(frozen=True)
class GpuProbe:
    """Snapshot of what the current process observed about the machine."""

    has_mps: bool = False
    torch_version: str = ""
    has_mlx: bool = False
    mlx_version: str = ""
    # Whether MLX can quantize/load an INT4 model on this build.
    has_mlx_quantize: bool = False
    # Whether MLX exposes a genuine MXFP4 (E2M1 micro-exponent, block-scaled)
    # kernel path on this build -- distinct from has_mlx_quantize (INT4) and
    # from NVFP4 (see the "do not call them identical" note on Windows'
    # gate_quant_lane for nvfp4). Defaults to False: this must be proven by a
    # real runtime probe, never assumed from chip-name guessing.
    has_mlx_mxfp4: bool = False


def select_device(*, use_gpu: bool, probe: GpuProbe) -> str:
    """Select the torch device string for Mac, GPU-first.

    GPU and CPU are never blended: a request for the GPU lane either returns
    'mps' or raises; CPU is an entirely separate, explicitly-requested path.
    """
    if use_gpu:
        if not probe.has_mps:
            raise CapabilityError(
                "GPU lane requested (use_gpu=true) but no Metal Performance "
                "Shaders (MPS) device was detected. This scenario requires "
                "Apple Silicon MPS for the GPU lane; CPU is a separate, "
                "explicitly-opted-in fallback and will not be silently "
                "substituted."
            )
        return "mps"
    return "cpu"


def gate_lane(*, lane: str, use_gpu: bool) -> None:
    """Validate the eager/compiled lane selection itself."""
    if lane not in config.LANES:
        raise ValueError(f"Unknown lane '{lane}'; expected one of {config.LANES}")
    if lane == "compiled" and not use_gpu:
        raise CapabilityError(
            "The compiled (torch.compile) lane is only defined for the GPU "
            "path in this scenario; request use_gpu=true or lane=eager. "
            "torch.compile on MPS is experimental; compile time is measured "
            "and reported separately from the eager baseline."
        )


def select_framework(*, model_tier: str, quant: str) -> str:
    """Pick 'torch' (MPS) or 'mlx' for a given tier/quant combination.

    The portable tier always runs on torch/MPS. The quantized headline tier
    runs its unquantized baseline on torch/MPS too (quant='none'); a real
    INT4 or MXFP4 request switches to the MLX-optimized stack, which is
    where those kernels actually live on Apple Silicon.
    """
    if model_tier not in config.MODEL_TIERS:
        raise ValueError(f"Unknown model tier '{model_tier}'; expected one of {config.MODEL_TIERS}")
    if quant not in config.QUANT_MODES:
        raise ValueError(f"Unknown quant mode '{quant}'; expected one of {config.QUANT_MODES}")
    if model_tier == "portable" and quant != "none":
        raise CapabilityError(
            "Quantized lanes (int4/mxfp4) are only defined for the "
            "'quantized' model tier (Qwen3-8B); the portable tier "
            "(Qwen3-1.7B) always runs BF16 on torch/MPS."
        )
    if quant == "none":
        return "torch"
    return "mlx"


def gate_quant_lane(*, quant: str, probe: GpuProbe) -> tuple[bool, str]:
    """Decide whether a requested quantized kernel path is genuinely available.

    Returns (available, reason). `reason` is always populated: either why the
    lane is unavailable, or a short confirmation of what was matched.
    Unsupported/unavailable lanes must be reported, never silently run on CPU
    or claimed as having executed.
    """
    if quant not in config.QUANT_MODES:
        raise ValueError(f"Unknown quant mode '{quant}'; expected one of {config.QUANT_MODES}")

    if quant == "none":
        return True, "no quantization requested"

    if not probe.has_mps:
        return False, "quantized kernels require Apple Silicon (MPS); none detected"

    if not probe.has_mlx:
        return False, "quantized lanes require the mlx package; not importable"

    if quant == "int4":
        if not probe.has_mlx_quantize:
            return False, "INT4 lane requires MLX quantization support; capability probe failed"
        return True, "MLX INT4 kernels available"

    if quant == "mxfp4":
        if not probe.has_mlx_mxfp4:
            return False, (
                "MXFP4 (E2M1 micro-exponent, block-scaled) lane requires an "
                "MLX build that exposes a genuine MXFP4 kernel path; the "
                "runtime capability probe did not confirm this. "
                "Capability-gated off rather than emulated or approximated "
                "with INT4. MLX MXFP4 is not claimed to be identical to "
                "NVIDIA NVFP4 -- block/scale formats differ and both must "
                "be reported, not conflated, when both are measured."
            )
        return True, "MLX MXFP4 (E2M1) kernels available"

    raise AssertionError("unreachable")  # pragma: no cover


def assert_model_residency(*, expected_device: str, observed_devices: frozenset[str]) -> None:
    """Fail loudly if any model parameter/buffer is not on the expected device.

    This enforces the "no device_map='auto', no CPU offload, no disk offload
    in GPU lanes" requirement: a GPU lane must observe exactly one device.

    torch may report per-parameter device strings with an index suffix (e.g.
    'mps:0'), while the expected device is the bare kind ('mps'/'cpu'), so
    device strings are matched by their kind (the part before ':') rather
    than exact equality -- mirrors the Windows CUDA residency check.
    """
    observed_kinds = {d.split(":", 1)[0] for d in observed_devices}
    if observed_kinds != {expected_device}:
        raise CapabilityError(
            f"Model residency check failed: expected all parameters on "
            f"'{expected_device}', observed devices {sorted(observed_devices)}. "
            f"device_map='auto' / CPU / disk offload is not permitted in GPU lanes."
        )
