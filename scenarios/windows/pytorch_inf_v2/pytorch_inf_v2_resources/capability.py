# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Pure device/lane/quantization capability-gating logic for pytorch_inf_v2.

No torch/transformers/triton imports here on purpose: every decision function
takes already-probed facts (booleans, version strings, tuples) as arguments so
this module -- and its gating rules -- can be unit tested on a host with no
GPU and no ML packages installed. The actual probing (querying torch.cuda,
triton, torchao, etc.) lives in run_benchmark.py.
"""

from dataclasses import dataclass

import config


class CapabilityError(RuntimeError):
    """Raised when a requested lane/device combination cannot run as asked.

    The design mandates explicit failure over silent CPU fallback or
    pretending a lane ran, so callers should let this propagate (and the
    scenario is expected to surface it as a failed run, not a degraded one).
    """


@dataclass(frozen=True)
class GpuProbe:
    """Snapshot of what the current process observed about the machine."""

    has_cuda: bool = False
    cuda_compute_capability: tuple | None = None  # e.g. (10, 0) for Blackwell
    has_triton: bool = False
    has_torchao: bool = False
    torch_version: str = ""


def select_device(*, use_gpu: bool, probe: GpuProbe) -> str:
    """Select the torch device string for Windows, GPU-first.

    GPU and CPU are never blended: a request for the GPU lane either returns
    'cuda' or raises; CPU is an entirely separate, explicitly-requested path.
    """
    if use_gpu:
        if not probe.has_cuda:
            raise CapabilityError(
                "GPU lane requested (use_gpu=true) but no NVIDIA CUDA device "
                "was detected. Windows N1X requires an NVIDIA GPU for this "
                "scenario; CPU is a separate, explicitly-opted-in fallback "
                "and will not be silently substituted."
            )
        return "cuda"
    return "cpu"


def gate_lane(*, lane: str, use_gpu: bool) -> None:
    """Validate the eager/compiled lane selection itself."""
    if lane not in config.LANES:
        raise ValueError(f"Unknown lane '{lane}'; expected one of {config.LANES}")
    if lane == "compiled" and not use_gpu:
        raise CapabilityError(
            "The compiled (torch.compile) lane is only defined for the GPU "
            "path in this scenario; request use_gpu=true or lane=eager."
        )


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

    if not probe.has_cuda:
        return False, "quantized kernels require an NVIDIA CUDA device; none detected"

    if quant == "int4":
        if not probe.has_torchao:
            return False, "INT4 lane requires torchao; not importable"
        if not probe.has_triton:
            return False, "INT4 lane requires triton-windows for Inductor codegen; not importable"
        return True, "torchao/Inductor INT4 kernels available"

    if quant == "nvfp4":
        cap = probe.cuda_compute_capability
        if cap is None or cap < config.NVFP4_MIN_COMPUTE_CAPABILITY:
            found = "unknown" if cap is None else f"sm_{cap[0]}{cap[1]}"
            required = f"sm_{config.NVFP4_MIN_COMPUTE_CAPABILITY[0]}{config.NVFP4_MIN_COMPUTE_CAPABILITY[1]}"
            return False, (
                f"NVFP4 (E2M1) requires Blackwell-class compute capability "
                f"{required}+; detected {found}. Capability-gated off rather "
                f"than emulated."
            )
        if not probe.has_torchao:
            return False, "NVFP4 lane requires torchao; not importable"
        return True, "NVFP4 (E2M1) kernels available on detected Blackwell-class GPU"

    raise AssertionError("unreachable")  # pragma: no cover


def assert_model_residency(*, expected_device: str, observed_devices: frozenset[str]) -> None:
    """Fail loudly if any model parameter/buffer is not on the expected device.

    This enforces the "no device_map='auto', no CPU offload, no disk offload
    in GPU lanes" requirement: a GPU lane must observe exactly one device.

    torch reports per-parameter device strings with an index suffix (e.g.
    'cuda:0'), while the expected device is the bare kind ('cuda'/'cpu'), so
    device strings are matched by their kind (the part before ':') rather
    than exact equality.
    """
    observed_kinds = {d.split(":", 1)[0] for d in observed_devices}
    if observed_kinds != {expected_device}:
        raise CapabilityError(
            f"Model residency check failed: expected all parameters on "
            f"'{expected_device}', observed devices {sorted(observed_devices)}. "
            f"device_map='auto' / CPU / disk offload is not permitted in GPU lanes."
        )
