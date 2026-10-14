# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""mac_pytorch_inf_v2 macOS inference benchmark.

GPU-first Qwen3 benchmark replacing mac_pytorch_inf. Two model tiers:
  - portable: Qwen/Qwen3-1.7B, eager (or compiled) BF16 on torch/MPS, fits an
    8 GB GPU budget.
  - quantized: Qwen/Qwen3-8B. The unquantized baseline (quant=none) runs on
    torch/MPS like the portable tier; the INT4/MXFP4 quantized headline
    lanes run on MLX (mlx + mlx-lm), which is where those kernels actually
    live on Apple Silicon -- see capability.select_framework().

All heavy imports (torch/transformers/mlx/mlx_lm) are deferred into
functions so `--probe-only` and unit-testable helpers (config.py,
capability.py, metrics.py) keep working on hosts without those packages.
"""

import argparse
import csv
import gc
import json
import math
import os
import platform
import sys
import time

import capability
import config
import metrics


def _log(message: str) -> None:
    print(message, flush=True)


def probe_gpu() -> capability.GpuProbe:
    """Query torch/mlx for what's genuinely available on this box."""
    has_mps = False
    torch_version = ""
    try:
        import torch

        has_mps = bool(torch.backends.mps.is_available())
        torch_version = getattr(torch, "__version__", "")
    except ImportError:
        pass

    has_mlx = False
    mlx_version = ""
    has_mlx_quantize = False
    try:
        import mlx.core as mx
        import mlx.nn as nn

        has_mlx = True
        mlx_version = getattr(mx, "__version__", "")
        # A genuine capability probe, not a version-string guess: confirm
        # mlx.nn exposes the quantize entry point this scenario depends on.
        has_mlx_quantize = callable(getattr(nn, "quantize", None))
    except ImportError:
        pass

    # MXFP4 (E2M1, block-scaled micro-exponent) has no confirmed, genuine
    # kernel path in the MLX versions pinned by this scenario (mlx==0.32.3).
    # This is intentionally hardcoded to False rather than guessed from a
    # version string: the design requires explicit proof of support, and
    # claiming MXFP4 support here without a real kernel would silently
    # produce INT4 (or unquantized) results mislabeled as MXFP4. Flip this
    # to a real probe (e.g. checking for a documented MLX MXFP4 dtype/kernel
    # entry point) once one exists and has been validated on hardware.
    has_mlx_mxfp4 = False

    return capability.GpuProbe(
        has_mps=has_mps,
        torch_version=torch_version,
        has_mlx=has_mlx,
        mlx_version=mlx_version,
        has_mlx_quantize=has_mlx_quantize,
        has_mlx_mxfp4=has_mlx_mxfp4,
    )


def _build_prompt_ids(tokenizer, prompt_tokens: int):
    """Build a deterministic prompt that tokenizes to exactly `prompt_tokens`."""
    chat = [{"role": "user", "content": "Describe the water cycle in detail."}]
    text = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    ids = tokenizer(text)["input_ids"] if hasattr(tokenizer, "__call__") else tokenizer.encode(text)
    if len(ids) >= prompt_tokens:
        ids = ids[:prompt_tokens]
    else:
        # Pad deterministically with a repeated filler token id (not EOS/PAD)
        # drawn from the tokenized text itself, so every run has the exact
        # same token count for a fair, comparable measurement.
        filler = ids[-1] if ids else tokenizer.eos_token_id
        ids = ids + [filler] * (prompt_tokens - len(ids))
    return ids


# --- torch/MPS lane (portable tier + quantized tier's unquantized baseline) --

def _device_of_torch(model) -> set:
    return {str(p.device) for p in model.parameters()}


def _load_torch_model_and_tokenizer(model_id: str, revision: str, device: str, dtype):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    model = AutoModelForCausalLM.from_pretrained(model_id, revision=revision, torch_dtype=dtype)
    model.to(device)
    model.eval()

    observed = _device_of_torch(model)
    capability.assert_model_residency(expected_device=device, observed_devices=frozenset(observed))

    return model, tokenizer


def _synchronize_torch(device: str):
    import torch

    if device == "mps":
        torch.mps.synchronize()


def run_once_torch(model, tokenizer, input_ids, device: str, max_new_tokens: int):
    """Run a single timed generation on torch/MPS; returns a metrics.TokenTiming."""
    import torch

    input_tensor = torch.tensor([input_ids], device=device)
    prompt_tokens = input_tensor.shape[1]

    with torch.inference_mode():
        _synchronize_torch(device)
        t_start = time.perf_counter()

        # Prefill: a single forward pass over the prompt, producing the first
        # token. Measured separately from the rest of decode.
        prefill_out = model(input_tensor, use_cache=True)
        _synchronize_torch(device)
        t_prefill_done = time.perf_counter()

        logits = prefill_out.logits[:, -1, :]
        has_nan = bool(torch.isnan(logits).any().item())
        has_inf = bool(torch.isinf(logits).any().item())
        metrics.assert_finite(has_nan=has_nan, has_inf=has_inf, where="prefill logits")

        next_token = torch.argmax(logits, dim=-1, keepdim=True)
        generated = [next_token.item()]
        past_key_values = prefill_out.past_key_values
        current = next_token

        t_first_token = t_prefill_done  # TTFT is measured at the prefill boundary

        for _ in range(max_new_tokens - 1):
            out = model(current, past_key_values=past_key_values, use_cache=True)
            logits = out.logits[:, -1, :]
            has_nan = bool(torch.isnan(logits).any().item())
            has_inf = bool(torch.isinf(logits).any().item())
            metrics.assert_finite(has_nan=has_nan, has_inf=has_inf, where="decode logits")
            current = torch.argmax(logits, dim=-1, keepdim=True)
            generated.append(current.item())
            past_key_values = out.past_key_values

        _synchronize_torch(device)
        t_end = time.perf_counter()

    ttft_s = t_first_token - t_start
    prefill_s = t_prefill_done - t_start
    decode_s = t_end - t_prefill_done
    total_s = t_end - t_start

    return metrics.TokenTiming(
        prompt_tokens=prompt_tokens,
        output_tokens=len(generated),
        ttft_s=ttft_s,
        prefill_s=prefill_s,
        decode_s=decode_s,
        total_s=total_s,
    )


def _run_benchmark_torch(args, probe, model_id, revision, max_new_tokens) -> dict:
    import torch

    device = capability.select_device(use_gpu=args.use_gpu, probe=probe)
    capability.gate_lane(lane=args.lane, use_gpu=args.use_gpu)
    dtype = torch.bfloat16

    t_load_start = time.perf_counter()
    model, tokenizer = _load_torch_model_and_tokenizer(model_id, revision, device, dtype)
    _synchronize_torch(device)
    cold_load_s = time.perf_counter() - t_load_start

    shape = config.SHAPES[args.shape]
    prompt_tokens = shape.get("prompt_tokens", 128)
    input_ids = _build_prompt_ids(tokenizer, prompt_tokens)

    compile_time_s = None
    if args.lane == "compiled":
        t_compile_start = time.perf_counter()
        model = torch.compile(model)
        # Trigger compilation with a warmup call outside the timed inference loop.
        run_once_torch(model, tokenizer, input_ids, device, max_new_tokens=1)
        _synchronize_torch(device)
        compile_time_s = time.perf_counter() - t_compile_start

    # First-inference timing (includes any lazy MPS graph / kernel warm-up)
    # kept separate from both cold load and the timed repetitions.
    t_first_inf_start = time.perf_counter()
    first_timing = run_once_torch(model, tokenizer, input_ids, device, max_new_tokens)
    first_inference_s = time.perf_counter() - t_first_inf_start

    for _ in range(config.DEFAULT_WARMUP_ITERATIONS - 1):
        run_once_torch(model, tokenizer, input_ids, device, max_new_tokens)

    timings = [
        run_once_torch(model, tokenizer, input_ids, device, max_new_tokens)
        for _ in range(config.DEFAULT_TIMED_REPETITIONS)
    ]

    peak_memory_bytes = None
    if device == "mps":
        peak_memory_bytes = int(torch.mps.driver_allocated_memory())

    total_latency_summary = metrics.summarize([t.total_s for t in timings])
    ttft_summary = metrics.summarize([t.ttft_s for t in timings])
    prefill_tps_summary = metrics.summarize([t.prefill_tokens_per_second for t in timings])
    decode_tps_summary = metrics.summarize([t.decode_tokens_per_second for t in timings])

    serialized_bytes = metrics.serialized_bytes_of([p.numel() * p.element_size() for p in model.parameters()])

    return {
        "ai_device": device,
        "framework": "torch",
        "cold_load_s": cold_load_s,
        "first_inference_s": first_inference_s,
        "compile_time_s": compile_time_s,
        "time_to_first_token_ms": ttft_summary["median"] * 1000,
        "time_to_first_token_s": ttft_summary["median"],
        "ttft_p95_s": ttft_summary["p95"],
        "ttft_cv": ttft_summary["cv"],
        "prefill_tokens_per_second": prefill_tps_summary["median"],
        "decode_tokens_per_second": decode_tps_summary["median"],
        "tokens_per_second": decode_tps_summary["median"],  # canonical HOBL key
        "total_generation_time_s": total_latency_summary["median"],
        "total_generation_time_p95_s": total_latency_summary["p95"],
        "total_generation_time_cv": total_latency_summary["cv"],
        "total_tokens_generated": first_timing.output_tokens,
        "serialized_bytes": serialized_bytes,
        "peak_memory_bytes": peak_memory_bytes,
    }


# --- MLX lane (quantized headline tier's INT4/MXFP4 lanes) ------------------

def _run_benchmark_mlx(args, probe, model_id, revision, max_new_tokens) -> dict:
    if not args.use_gpu:
        raise capability.CapabilityError(
            "The MLX quantized lane runs on Apple Silicon's unified memory "
            "GPU path by construction; CPU-only is not a meaningful request "
            "here (request --quant none to run the torch/MPS or torch/CPU "
            "baseline instead)."
        )

    available, reason = capability.gate_quant_lane(quant=args.quant, probe=probe)
    if not available:
        raise capability.CapabilityError(f"{args.quant.upper()} lane unavailable: {reason}")

    if args.quant == "mxfp4":
        # Capability-gated off: see probe_gpu()'s has_mlx_mxfp4 note. This
        # mirrors how Windows treats NVFP4 when gate_quant_lane() passes but
        # the kernel wiring itself has not been validated on hardware; here
        # the gate above is actually what blocks this path (has_mlx_mxfp4 is
        # hardcoded False), so reaching this branch would mean the probe was
        # changed without the kernel path being implemented.
        raise capability.CapabilityError(
            "MLX MXFP4 (E2M1) execution is capability-gated: no genuine "
            "MXFP4 kernel path has been confirmed available in the pinned "
            "mlx==0.32.3 build, so it is not wired up. Revisit once a "
            "validated MLX MXFP4 release exists."
        )

    import mlx.core as mx
    import mlx.nn as nn
    from mlx.utils import tree_flatten
    from mlx_lm import load as mlx_load
    from mlx_lm import stream_generate

    t_load_start = time.perf_counter()
    model, tokenizer = mlx_load(model_id, revision=revision)
    if args.quant == "int4":
        # On-the-fly quantization from the same unquantized source checkpoint
        # used by the torch/MPS baseline and by Windows' TorchAO INT4 lane --
        # matched source checkpoint, per the design. mlx.nn.quantize is the
        # stable, version-independent entry point (vs. mlx_lm's internal
        # conversion helpers, which have changed signatures across releases).
        nn.quantize(model, group_size=64, bits=4)
    mx.eval(model.parameters())
    cold_load_s = time.perf_counter() - t_load_start

    shape = config.SHAPES[args.shape]
    prompt_tokens = shape.get("prompt_tokens", 128)
    input_ids = _build_prompt_ids(tokenizer, prompt_tokens)

    def _run_once():
        t_start = time.perf_counter()
        t_first_token = None
        generated_tokens = 0
        last_response = None
        for response in stream_generate(model, tokenizer, input_ids, max_tokens=max_new_tokens):
            if t_first_token is None:
                t_first_token = time.perf_counter()
            if response.logprobs is not None:
                lp = response.logprobs
                has_nan = bool(mx.any(mx.isnan(lp)).item()) if hasattr(lp, "shape") else math.isnan(float(lp))
                has_inf = bool(mx.any(mx.isinf(lp)).item()) if hasattr(lp, "shape") else math.isinf(float(lp))
                metrics.assert_finite(has_nan=has_nan, has_inf=has_inf, where="mlx decode logprobs")
            generated_tokens += 1
            last_response = response
        t_end = time.perf_counter()

        ttft_s = (t_first_token or t_end) - t_start
        total_s = t_end - t_start
        # mlx_lm's stream_generate already synchronizes (mx.eval) per step
        # and reports its own prompt/generation throughput; using the
        # library's own measured rates avoids re-implementing MLX's lazy
        # evaluation/cache bookkeeping by hand.
        prefill_tps = getattr(last_response, "prompt_tps", 0.0) or 0.0
        decode_tps = getattr(last_response, "generation_tps", 0.0) or 0.0
        prefill_s = (prompt_tokens / prefill_tps) if prefill_tps else 0.0
        decode_s = max(total_s - prefill_s, 0.0)

        return metrics.TokenTiming(
            prompt_tokens=prompt_tokens,
            output_tokens=max(generated_tokens, 1),
            ttft_s=ttft_s,
            prefill_s=prefill_s,
            decode_s=decode_s,
            total_s=total_s,
        ), last_response

    t_first_inf_start = time.perf_counter()
    first_timing, first_response = _run_once()
    first_inference_s = time.perf_counter() - t_first_inf_start

    for _ in range(config.DEFAULT_WARMUP_ITERATIONS - 1):
        _run_once()

    results = [_run_once() for _ in range(config.DEFAULT_TIMED_REPETITIONS)]
    timings = [t for t, _ in results]
    responses = [r for _, r in results]

    peak_memory_bytes = None
    peaks = [getattr(r, "peak_memory", None) for r in responses if getattr(r, "peak_memory", None) is not None]
    if peaks:
        # mlx_lm reports peak_memory in GB; convert to bytes for the
        # canonical HOBL metric unit used throughout this scenario.
        peak_memory_bytes = int(max(peaks) * (1024 ** 3))

    total_latency_summary = metrics.summarize([t.total_s for t in timings])
    ttft_summary = metrics.summarize([t.ttft_s for t in timings])
    prefill_tps_summary = metrics.summarize([t.prefill_tokens_per_second for t in timings])
    decode_tps_summary = metrics.summarize([t.decode_tokens_per_second for t in timings])

    serialized_bytes = metrics.serialized_bytes_of(
        [p.nbytes for _, p in tree_flatten(model.parameters())]
    )

    return {
        "ai_device": "mlx",
        "framework": "mlx",
        "cold_load_s": cold_load_s,
        "first_inference_s": first_inference_s,
        "compile_time_s": None,
        "time_to_first_token_ms": ttft_summary["median"] * 1000,
        "time_to_first_token_s": ttft_summary["median"],
        "ttft_p95_s": ttft_summary["p95"],
        "ttft_cv": ttft_summary["cv"],
        "prefill_tokens_per_second": prefill_tps_summary["median"],
        "decode_tokens_per_second": decode_tps_summary["median"],
        "tokens_per_second": decode_tps_summary["median"],  # canonical HOBL key
        "total_generation_time_s": total_latency_summary["median"],
        "total_generation_time_p95_s": total_latency_summary["p95"],
        "total_generation_time_cv": total_latency_summary["cv"],
        "total_tokens_generated": first_timing.output_tokens,
        "serialized_bytes": serialized_bytes,
        "peak_memory_bytes": peak_memory_bytes,
    }


def run_benchmark(args) -> dict:
    probe = probe_gpu()

    model_id = config.PORTABLE_MODEL if args.model_tier == "portable" else config.QUANT_MODEL
    revision = config.PORTABLE_REVISION if args.model_tier == "portable" else config.QUANT_REVISION
    shape = config.SHAPES[args.shape]
    max_new_tokens = shape.get("max_new_tokens", 128)

    framework = capability.select_framework(model_tier=args.model_tier, quant=args.quant)

    if framework == "torch":
        framework_result = _run_benchmark_torch(args, probe, model_id, revision, max_new_tokens)
    else:
        framework_result = _run_benchmark_mlx(args, probe, model_id, revision, max_new_tokens)

    quant_available, quant_reason = capability.gate_quant_lane(quant=args.quant, probe=probe)

    result = {
        "ai_model": model_id,
        "ai_model_revision": revision,
        "architecture": platform.machine(),
        "model_tier": args.model_tier,
        "lane": args.lane,
        "quant": args.quant,
        "quant_available": quant_available,
        "quant_reason": quant_reason,
        "shape": args.shape,
        "prompt_tokens": shape.get("prompt_tokens", 128),
        "max_new_tokens": max_new_tokens,
    }
    result.update(framework_result)
    result["scenario_runtime"] = result["total_generation_time_s"]
    return result


def write_csv(result: dict, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        for key, value in result.items():
            writer.writerow([key, value])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="mac_pytorch_inf_v2 macOS inference benchmark")
    parser.add_argument("--model-tier", choices=config.MODEL_TIERS, default="portable")
    parser.add_argument("--lane", choices=config.LANES, default="eager")
    parser.add_argument("--quant", choices=config.QUANT_MODES, default="none")
    parser.add_argument("--shape", choices=list(config.SHAPES.keys()), default="short")
    parser.add_argument("--use-gpu", dest="use_gpu", action="store_true", default=True)
    parser.add_argument("--no-gpu", dest="use_gpu", action="store_false")
    parser.add_argument("--log-dir", default=".")
    parser.add_argument("--setup", action="store_true", help="Pre-download model/tokenizer weights only.")
    parser.add_argument("--cleanup-gpu", action="store_true", help="Release cached GPU memory and exit.")
    parser.add_argument("--probe-only", action="store_true", help="Print capability probe results as JSON and exit.")
    args = parser.parse_args(argv)

    os.makedirs(args.log_dir, exist_ok=True)

    if args.probe_only:
        probe = probe_gpu()
        print(json.dumps(probe.__dict__))
        return 0

    if args.cleanup_gpu:
        try:
            import torch

            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except ImportError:
            pass
        try:
            import mlx.core as mx

            mx.clear_cache()
        except (ImportError, AttributeError):
            pass
        gc.collect()
        _log("GPU cache cleanup complete.")
        return 0

    if args.setup:
        model_id = config.PORTABLE_MODEL if args.model_tier == "portable" else config.QUANT_MODEL
        revision = config.PORTABLE_REVISION if args.model_tier == "portable" else config.QUANT_REVISION
        from transformers import AutoModelForCausalLM, AutoTokenizer

        AutoTokenizer.from_pretrained(model_id, revision=revision)
        AutoModelForCausalLM.from_pretrained(model_id, revision=revision)
        _log(f"Downloaded {model_id}@{revision} outside of scored time.")
        return 0

    try:
        result = run_benchmark(args)
    except (capability.CapabilityError, metrics.NonFiniteOutputError) as exc:
        _log(f" ERROR - {exc}")
        return 1

    out_path = os.path.join(args.log_dir, "mac_pytorch_inf_v2_inference_info.csv")
    write_csv(result, out_path)
    _log(f"Wrote metrics to {out_path}")
    for key, value in result.items():
        _log(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
