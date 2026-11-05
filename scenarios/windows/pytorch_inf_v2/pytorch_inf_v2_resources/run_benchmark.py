# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""pytorch_inf_v2 Windows inference benchmark.

GPU-first Qwen3 benchmark replacing pytorch_inf. Two model tiers:
  - portable: Qwen/Qwen3-1.7B, eager (or compiled) BF16, fits an 8 GB GPU budget.
  - quantized: Qwen/Qwen3-8B, INT4 (TorchAO/Inductor) or NVFP4 (E2M1) headline lane.

All heavy imports (torch/transformers/triton/torchao) are deferred into
functions so `--probe-only` and unit-testable helpers (config.py,
capability.py, metrics.py) keep working on hosts without those packages.
"""

import argparse
import csv
import gc
import json
import os
import statistics
import sys
import time

import capability
import config
import metrics


def _log(message: str) -> None:
    print(message, flush=True)


def probe_gpu() -> capability.GpuProbe:
    """Query torch/triton/torchao for what's genuinely available on this box."""
    try:
        import torch
    except ImportError:
        return capability.GpuProbe()

    has_cuda = bool(torch.cuda.is_available())
    cuda_compute_capability = None
    if has_cuda:
        try:
            cuda_compute_capability = torch.cuda.get_device_capability(0)
        except Exception:  # pragma: no cover - defensive, driver dependent
            cuda_compute_capability = None

    has_triton = False
    try:
        import triton  # noqa: F401

        has_triton = True
    except ImportError:
        has_triton = False

    has_torchao = False
    try:
        import torchao  # noqa: F401

        has_torchao = True
    except ImportError:
        has_torchao = False

    return capability.GpuProbe(
        has_cuda=has_cuda,
        cuda_compute_capability=cuda_compute_capability,
        has_triton=has_triton,
        has_torchao=has_torchao,
        torch_version=getattr(torch, "__version__", ""),
    )


def _build_prompt(tokenizer, prompt_tokens: int):
    """Build a deterministic prompt that tokenizes to exactly `prompt_tokens`."""
    chat = [{"role": "user", "content": "Describe the water cycle in detail."}]
    text = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    ids = tokenizer(text, return_tensors=None)["input_ids"]
    if len(ids) >= prompt_tokens:
        ids = ids[:prompt_tokens]
    else:
        # Pad deterministically with a repeated filler token id (not EOS/PAD)
        # drawn from the tokenized text itself, so every run has the exact
        # same token count for a fair, comparable measurement.
        filler = ids[-1] if ids else tokenizer.eos_token_id
        ids = ids + [filler] * (prompt_tokens - len(ids))
    return ids


def _device_of(model) -> set:
    return {str(p.device) for p in model.parameters()}


def _load_model_and_tokenizer(model_id: str, revision: str, device: str, dtype, quant: str, probe):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)

    load_kwargs = dict(revision=revision, torch_dtype=dtype)
    quantization_config = None
    if quant == "int4":
        available, reason = capability.gate_quant_lane(quant=quant, probe=probe)
        if not available:
            raise capability.CapabilityError(f"INT4 lane unavailable: {reason}")
        from torchao.quantization import Int4WeightOnlyConfig
        from torchao.quantization.quant_api import Int4PackingFormat
        # torchao's default int4 packing format (PLAIN -> Int4Tensor) requires
        # the internal "mslk" kernel package, which is not a public pip
        # dependency and is unavailable in this environment. TILE_PACKED_TO_4D
        # uses torch's native tinygemm ATen kernels instead, which ship with
        # torch itself and need no extra package.
        quantization_config = Int4WeightOnlyConfig(
            group_size=128, int4_packing_format=Int4PackingFormat.TILE_PACKED_TO_4D
        )
    elif quant == "nvfp4":
        available, reason = capability.gate_quant_lane(quant=quant, probe=probe)
        if not available:
            raise capability.CapabilityError(f"NVFP4 lane unavailable: {reason}")
        raise capability.CapabilityError(
            "NVFP4 (E2M1) execution is not yet wired up: the hardware "
            "capability gate above passed, but this benchmark does not "
            "implement an NVFP4 quantization/execution path yet. The "
            "kernel wiring is intentionally not claimed as executed "
            "until it has been implemented and validated."
        )

    model = AutoModelForCausalLM.from_pretrained(model_id, **load_kwargs)
    model.to(device)
    if quantization_config is not None:
        # The tinygemm int4 packing kernel (aten::_convert_weight_to_int4pack)
        # is CUDA-only, so weights must already be resident on the GPU before
        # quantize_() runs; quantizing CPU-resident weights raises
        # NotImplementedError for this backend.
        from torchao.quantization import quantize_
        quantize_(model, quantization_config)

    model.eval()

    observed = _device_of(model)
    capability.assert_model_residency(expected_device=device, observed_devices=frozenset(observed))

    return model, tokenizer


def _synchronize(device: str):
    import torch
    if device == "cuda":
        torch.cuda.synchronize()


def run_once(model, tokenizer, input_ids, device: str, max_new_tokens: int):
    """Run a single timed generation; returns a metrics.TokenTiming."""
    import torch

    input_tensor = torch.tensor([input_ids], device=device)
    prompt_tokens = input_tensor.shape[1]

    with torch.inference_mode():
        _synchronize(device)
        t_start = time.perf_counter()

        # Prefill: a single forward pass over the prompt, producing the first
        # token. Measured separately from the rest of decode.
        prefill_out = model(input_tensor, use_cache=True)
        _synchronize(device)
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

        _synchronize(device)
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


def run_benchmark(args) -> dict:
    import torch

    probe = probe_gpu()
    device = capability.select_device(use_gpu=args.use_gpu, probe=probe)
    capability.gate_lane(lane=args.lane, use_gpu=args.use_gpu)

    model_id = config.PORTABLE_MODEL if args.model_tier == "portable" else config.QUANT_MODEL
    revision = config.PORTABLE_REVISION if args.model_tier == "portable" else config.QUANT_REVISION
    dtype = torch.bfloat16

    shape = config.SHAPES[args.shape]
    prompt_tokens = shape.get("prompt_tokens", 128)
    max_new_tokens = shape.get("max_new_tokens", 128)

    t_load_start = time.perf_counter()
    model, tokenizer = _load_model_and_tokenizer(model_id, revision, device, dtype, args.quant, probe)
    _synchronize(device)
    cold_load_s = time.perf_counter() - t_load_start

    input_ids = _build_prompt(tokenizer, prompt_tokens)

    compile_time_s = None
    if args.lane == "compiled":
        t_compile_start = time.perf_counter()
        model = torch.compile(model)
        # Trigger compilation with a warmup call outside the timed inference loop.
        run_once(model, tokenizer, input_ids, device, max_new_tokens=1)
        _synchronize(device)
        compile_time_s = time.perf_counter() - t_compile_start

    # First-inference timing (includes any lazy CUDA context / kernel warm-up)
    # kept separate from both cold load and the timed repetitions.
    t_first_inf_start = time.perf_counter()
    first_timing = run_once(model, tokenizer, input_ids, device, max_new_tokens)
    first_inference_s = time.perf_counter() - t_first_inf_start

    for _ in range(config.DEFAULT_WARMUP_ITERATIONS - 1):
        run_once(model, tokenizer, input_ids, device, max_new_tokens)

    timings = [run_once(model, tokenizer, input_ids, device, max_new_tokens) for _ in range(config.DEFAULT_TIMED_REPETITIONS)]

    peak_memory_bytes = None
    if device == "cuda":
        peak_memory_bytes = int(torch.cuda.max_memory_allocated())

    total_latency_summary = metrics.summarize([t.total_s for t in timings])
    ttft_summary = metrics.summarize([t.ttft_s for t in timings])
    prefill_tps_summary = metrics.summarize([t.prefill_tokens_per_second for t in timings])
    decode_tps_summary = metrics.summarize([t.decode_tokens_per_second for t in timings])

    serialized_bytes = metrics.serialized_bytes_of([p.numel() * p.element_size() for p in model.parameters()])

    quant_available, quant_reason = capability.gate_quant_lane(quant=args.quant, probe=probe)

    result = {
        "ai_model": model_id,
        "ai_model_revision": revision,
        "ai_device": device,
        "architecture": os.environ.get("PROCESSOR_ARCHITECTURE", ""),
        "model_tier": args.model_tier,
        "lane": args.lane,
        "quant": args.quant,
        "quant_available": quant_available,
        "quant_reason": quant_reason,
        "shape": args.shape,
        "prompt_tokens": prompt_tokens,
        "max_new_tokens": max_new_tokens,
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
        "scenario_runtime": total_latency_summary["median"],
    }
    return result


def write_csv(result: dict, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        for key, value in result.items():
            writer.writerow([key, value])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="pytorch_inf_v2 Windows inference benchmark")
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
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
        except ImportError:
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

    out_path = os.path.join(args.log_dir, "pytorch_inf_v2_inference_info.csv")
    write_csv(result, out_path)
    _log(f"Wrote metrics to {out_path}")
    for key, value in result.items():
        _log(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
