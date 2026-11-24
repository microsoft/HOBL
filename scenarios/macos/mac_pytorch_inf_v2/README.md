# PyTorch Inference Workload v2 (replacement for `mac_pytorch_inf`, macOS)

GPU-first LLM inference benchmark on [Qwen3](https://huggingface.co/Qwen) using
PyTorch + Hugging Face Transformers for a portable MPS lane, and
[MLX](https://github.com/ml-explore/mlx) + [MLX-LM](https://github.com/ml-explore/mlx-lm)
for a platform-optimized quantized lane. Replaces `mac_pytorch_inf` (Phi-4-mini,
bundled metrics/timing defects -- see "Divergences from `mac_pytorch_inf`"
below). This scenario is additive: `mac_pytorch_inf` is left untouched so both
can run side by side until `mac_pytorch_inf_v2` is validated on real Apple
Silicon hardware.

## Design summary

- **GPU-first, never blended.** All macOS DUTs use Apple's Metal Performance
  Shaders (MPS) GPU backend; CPU is a separate, explicit `--no-gpu` fallback,
  never a silent substitution. `capability.select_device()` raises rather
  than falling back when GPU was requested but MPS is unavailable.
- **Two frameworks, two purposes, not interchangeable:**
  - *Portable* tier always runs on **PyTorch + MPS** (`Qwen/Qwen3-1.7B`, BF16,
    eager by default; `--lane compiled` enables a separately-timed, MPS
    `torch.compile` path described as experimental).
  - *Quantized headline* tier (`Qwen/Qwen3-8B`) baseline (`--quant none`)
    stays on PyTorch + MPS; INT4 (`--quant int4`) and the micro-exponent peer
    (`--quant mxfp4`) switch to **MLX**, Apple's platform-optimized array
    framework, via `mlx_lm.load()` + `mlx.nn.quantize()`.
  - Both tiers are pinned to the same immutable revisions used on Windows:
    portable `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`, quantized
    `b968826d9c46dd6066d109eabc6255188de91218`.
- **"MXFP4", not "NVFP4"**: MLX's quantized micro-exponent format is reported
  under its own name and is **not claimed to be identical** to NVIDIA's NVFP4
  (E2M1) format used on the Windows/CUDA side of this benchmark pair --
  block/scale layout and effective vs. actual on-disk size differ and are
  reported separately, never conflated. See "Known hardware-validation gaps".
- **Workload shapes:** `short` (128 prompt -> 128 output tokens), `long` (4096
  -> 128), `sustained` (15-minute budget, config placeholder for a future
  sustained-load loop) -- identical to the Windows scenario's shapes.
- **Metrics kept separate** (not blended into one number): cold model load,
  first inference, compile time, true TTFT, prefill tok/s, decode tok/s,
  end-to-end latency, serialized parameter/weight bytes, peak MPS/unified
  memory, and median/p95/CV over repeated timed runs. `metrics.py` is shared
  verbatim with the Windows scenario.
- **Correctness fixes vs. `mac_pytorch_inf`:** uses the model's official
  `apply_chat_template(enable_thinking=False)`; calls `model.eval()` and
  `torch.inference_mode()`; fixed `max_new_tokens` (no early-stop drift); no
  streaming/console decoding inside the timed region; explicit MPS
  synchronization (`torch.mps.synchronize()`) around every timing boundary;
  manual KV-cache decode loop (not `.generate()`) for accurate
  prefill/decode/TTFT accounting on the PyTorch lane; warmup iterations
  before timed repetitions; fails fast on NaN/Inf logits instead of
  sanitizing; asserts all model parameters land on the expected device (no
  `device_map="auto"`, CPU offload, or disk offload in GPU lanes).

## What HOBL sets up (from `mac_pytorch_inf_v2_resources/mac_pytorch_inf_v2_prep.sh`)

- Python **3.14.8** via pyenv, installed conditionally (never `pyenv install
  -f`, which would wipe every other scenario sharing the pyenv version
  directory) and isolated into a **private per-scenario venv** at
  `hobl_bin/mac_pytorch_inf_v2_resources/.venv` -- untouched by other
  scenarios' `pyenv install`/`pyenv global`.
- `torch==2.14.0` (no CUDA build tag; MPS ships in the standard macOS wheel)
  and `transformers==5.19.0` for the portable/baseline lane.
- `mlx==0.32.3` and `mlx-lm==0.32.0` for the quantized INT4/MXFP4 lanes.
- Both model tiers (portable + quantized) are downloaded during prep, outside
  of any scored time.

## Run it standalone (macOS)

```bash
pyenv install 3.14.8
pyenv local 3.14.8
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements_osx.txt

# Timed workload (run from mac_pytorch_inf_v2_resources/, where run_benchmark.py lives)
python run_benchmark.py --model-tier portable --lane eager --quant none --shape short --log-dir .
```

Useful flags: `--model-tier {portable,quantized}`, `--lane {eager,compiled}`,
`--quant {none,int4,mxfp4}`, `--shape {short,long,sustained}`, `--no-gpu`,
`--probe-only` (print the GPU/capability probe as JSON and exit),
`--setup` (pre-download weights only), `--cleanup-gpu` (release cached GPU
memory).

## HOBL parameters

| Parameter    | Default    | Options                              |
|--------------|------------|---------------------------------------|
| `loops`      | `2`        | integer                               |
| `use_gpu`    | `true`     | `true`, `false`                       |
| `model_tier` | `portable` | `portable`, `quantized`               |
| `lane`       | `eager`    | `eager`, `compiled`                   |
| `quant`      | `none`     | `none`, `int4`, `mxfp4`                |
| `shape`      | `short`    | `short`, `long`, `sustained`          |

## Known hardware-validation gaps (explicitly tracked, not hidden)

- **No Apple Silicon hardware was available to validate any lane in this
  change.** All config/capability/metrics-math logic is unit-tested without
  torch/MPS/MLX imports (see `tests/`), but no end-to-end run (model load,
  MPS inference, MLX quantization) has executed on real hardware.
- **`mlx_lm.stream_generate()` field names and `mlx.nn.quantize()`'s exact
  signature are implemented from API recollection, not verified against the
  actual pinned `mlx==0.32.3`/`mlx-lm==0.32.0` source.** `run_benchmark.py`
  fails fast with a clear error (rather than silently falling back) if the
  expected `GenerationResponse` fields or `quantize()` keyword arguments are
  not present at runtime -- this must be the first thing checked if a real
  run on Apple Silicon fails during the MLX lane.
- **MXFP4 defaults to capability-gated-unavailable
  (`GpuProbe.has_mlx_mxfp4 = False`).** No genuine MXFP4 kernel path in MLX
  has been confirmed; `capability.gate_quant_lane()` reports it as
  unavailable with an explicit reason rather than silently falling back to
  INT4 or CPU, or claiming parity with NVIDIA's NVFP4. This gate should only
  be flipped on once a real MLX MXFP4 kernel path is confirmed on hardware.
- **No performance numbers are reported in this change.** All metrics code is
  implemented and unit-tested at the config/capability/metrics-math level
  only; end-to-end numbers require real Apple Silicon hardware that was not
  available in this environment.

## Divergences from `mac_pytorch_inf`

- Different model family (Qwen3 vs. Phi-4-mini), two tiers instead of one,
  pinned by immutable revision instead of floating `main`.
- Python 3.14.8 instead of the version pinned by `mac_pytorch_inf`.
- Adds a second framework (MLX/MLX-LM) for the quantized INT4/MXFP4 lanes;
  `mac_pytorch_inf` is PyTorch-only.
- `.generate()`-based decode loop replaced by a manual KV-cache loop (PyTorch
  lane) for accurate prefill/TTFT/decode separation.
- Manual **per-scenario venv** (`.venv` under the resources directory)
  instead of installing packages directly into the shared pyenv
  site-packages -- survives another scenario's `pyenv install` even if one is
  run without the conditional-install guard.
- Timestamping uses the same `date +%s`-based approach as `mac_pytorch_inf`'s
  scripts for host-side script logging, but all *scored* timing is measured
  in-process by `run_benchmark.py`/`metrics.py` using
  `time.perf_counter()` (sub-second precision), matching the Windows
  scenario's measurement boundary -- shell-level `date +%s` is never used for
  timed metrics, only for prep/run/teardown script log lines.
- Follows the `core.app_scenario` + `checkPrepStatus` scenario-class
  convention shared with `mac_pytorch_inf`/`mac_foundrylocal` (not the newer
  `checkPrepStatusNew` API used by the Windows `pytorch_inf_v2` scenario,
  which does not have a macOS equivalent in this repo yet).
- Adds hardware-free unit tests for config/capability/metrics and scenario
  host-orchestration logic (see `tests/`).
