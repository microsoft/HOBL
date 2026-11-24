# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""Pure metrics/statistics helpers for mac_pytorch_inf_v2.

Identical in content to the Windows pytorch_inf_v2 copy of this module --
the math is platform-agnostic, so it is duplicated (not imported across
scenarios, per repo convention) rather than shared.

Kept free of torch imports so timing/token-accounting math is unit testable
without a GPU. run_benchmark.py feeds these functions plain floats/ints that
it measured around the GPU-synchronized timed regions.
"""

import math
from dataclasses import dataclass


class NonFiniteOutputError(RuntimeError):
    """Raised when generated logits/hidden states contain NaN/Inf.

    The design requires failing loudly on NaN/Inf rather than sanitizing
    them away with a logits processor.
    """


def assert_finite(*, has_nan: bool, has_inf: bool, where: str) -> None:
    if has_nan or has_inf:
        problems = []
        if has_nan:
            problems.append("NaN")
        if has_inf:
            problems.append("Inf")
        raise NonFiniteOutputError(f"Non-finite values ({', '.join(problems)}) detected in {where}; failing run.")


@dataclass(frozen=True)
class TokenTiming:
    prompt_tokens: int
    output_tokens: int
    ttft_s: float
    prefill_s: float
    decode_s: float
    total_s: float

    def __post_init__(self):
        for name in ("prompt_tokens", "output_tokens"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive, got {getattr(self, name)}")
        for name in ("ttft_s", "prefill_s", "decode_s", "total_s"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative, got {getattr(self, name)}")

    @property
    def prefill_tokens_per_second(self) -> float:
        if self.prefill_s <= 0:
            return 0.0
        return self.prompt_tokens / self.prefill_s

    @property
    def decode_tokens_per_second(self) -> float:
        # Decode token count excludes the single prefill-produced first
        # token; a fixed max_new_tokens run with N output tokens has N-1
        # decode steps after the first token is produced via prefill.
        decode_tokens = max(self.output_tokens - 1, 0)
        if self.decode_s <= 0 or decode_tokens == 0:
            return 0.0
        return decode_tokens / self.decode_s


def summarize(samples: list[float]) -> dict:
    """Return median/p95/coefficient-of-variation for a list of timing samples."""
    if not samples:
        raise ValueError("samples must be non-empty")
    ordered = sorted(samples)
    n = len(ordered)
    median = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
    # Nearest-rank p95; fine for the small (single-digit) repetition counts
    # these scenarios use -- not a general-purpose percentile implementation.
    p95_index = min(n - 1, math.ceil(0.95 * n) - 1)
    p95 = ordered[p95_index]
    mean = sum(ordered) / n
    if n > 1:
        variance = sum((x - mean) ** 2 for x in ordered) / (n - 1)
        stdev = math.sqrt(variance)
    else:
        stdev = 0.0
    cv = (stdev / mean) if mean else 0.0
    return {"median": median, "p95": p95, "cv": cv, "mean": mean, "stdev": stdev, "count": n}


def serialized_bytes_of(tensor_nbytes: list[int]) -> int:
    """Sum raw tensor byte sizes to report a measured (not estimated) artifact size."""
    if any(n < 0 for n in tensor_nbytes):
        raise ValueError("tensor byte sizes must be non-negative")
    return sum(tensor_nbytes)
