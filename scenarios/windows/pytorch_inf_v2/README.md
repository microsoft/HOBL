# PyTorch Inference Workload v2 (replacement for `pytorch_inf`)

GPU-first LLM inference benchmark on [Qwen3](https://huggingface.co/Qwen) using
[PyTorch](https://pytorch.org/) + Hugging Face Transformers. Replaces `pytorch_inf`
(Phi-4-mini, blended GPU/CPU behavior, bundled metrics/timing defects -- see
"Divergences from `pytorch_inf`" below). This scenario is additive: `pytorch_inf`
is left untouched so both can run side by side until `pytorch_inf_v2` is validated
on real N1X / Apple Silicon hardware.

## Design summary

- **GPU-first, never blended.** Windows x64 and Windows Arm64 (N1X) both use an
  NVIDIA GPU via CUDA; CPU is a separate, explicit `-noGpu` fallback, never a
  silent substitution. `capability.select_device()` raises rather than falling
  back when a GPU was requested but unavailable.
- **Two model tiers:**
  - *Portable* (BF16): `Qwen/Qwen3-1.7B` @ immutable revision
    `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`. Fits an 8 GB GPU budget. Eager
    lane by default; `--lane compiled` enables a separately-timed
    `torch.compile` path.
  - *Quantized headline*: `Qwen/Qwen3-8B` @ immutable revision
    `b968826d9c46dd6066d109eabc6255188de91218`. INT4 via TorchAO/Inductor
    (`--quant int4`); NVFP4 (E2M1 micro-exponent) is capability-gated behind
    Blackwell-class compute capability (`--quant nvfp4`) and is **not claimed
    as executed** on hardware that cannot genuinely run it (see
    "Known hardware-validation gaps").
- **Workload shapes:** `short` (128 prompt -> 128 output tokens), `long` (4096 ->
  128), `sustained` (15-minute budget, config placeholder for a future
  sustained-load loop).
- **Metrics kept separate** (not blended into one number): cold model load,
  first inference, compile time, true TTFT, prefill tok/s, decode tok/s,
  end-to-end latency, serialized parameter bytes, peak CUDA memory, and
  median/p95/CV over repeated timed runs.
- **Correctness fixes vs. `pytorch_inf`:** uses the model's official
  `apply_chat_template(enable_thinking=False)`; calls `model.eval()` and
  `torch.inference_mode()`; fixed `max_new_tokens` (no early-stop drift); no
  streaming/console decoding inside the timed region; explicit CUDA
  synchronization around every timing boundary; manual KV-cache decode loop
  (not `.generate()`) for accurate prefill/decode/TTFT accounting; warmup
  iterations before timed repetitions; fails fast on NaN/Inf logits instead of
  sanitizing; asserts all model parameters land on the expected device (no
  `device_map="auto"`, CPU offload, or disk offload in GPU lanes).

## What HOBL sets up (from `pytorch_inf_v2_resources/pytorch_inf_v2_prep.ps1`)

- Python **3.14.8** (`3.14.8` x64 / `3.14.8-arm` N1X) via pyenv, installed
  conditionally (never `-f`) and isolated into a **private per-scenario venv**
  at `hobl_bin\pytorch_inf_v2_resources\.venv` -- untouched by other
  scenarios' `pyenv install`/`pyenv global`.
- x64: `torch==2.14.0+cu134` / `torchvision==0.29.0+cu134` from
  `https://download.pytorch.org/whl/cu134`.
- Arm64 (N1X): NVIDIA's out-of-tree CUDA build of `torch==2.14.0+cu134` from
  `https://pypi.nvidia.com/nvtorch_oot/torch/` -- **downloaded explicitly and
  SHA256-verified** against the pin in `config.py` before install (prep fails
  fast on any hash mismatch; this is not a standard PyPI/pytorch.org mirror).
- `transformers==5.18.0`, `triton-windows==3.8.0.post29`, `torchao==0.18.0`
  (INT4/NVFP4 are additionally gated by a runtime capability probe --
  `capability.gate_quant_lane()` -- before being used, regardless of whether
  the packages import successfully). `transformers` targets 5.19.0 by design,
  but the Microsoft-managed package feed proxy (required on managed devices
  under CISO Central Feed Services policy; direct public PyPI is blocked)
  had not mirrored 5.19.0 as of the last hardware validation pass and tops
  out at 5.18.0, which fully supports the Qwen3 architecture used here.
  Revisit this pin once 5.19.0 is mirrored.
- Both model tiers (portable + quantized) are downloaded during prep, outside
  of any scored time.

## Run it standalone (Windows)

```powershell
pyenv install 3.14.8        # 3.14.8-arm on N1X
pyenv local 3.14.8
python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements_win.txt   # or requirements_win_arm64.txt on N1X

# Timed workload (run from pytorch_inf_v2_resources/, where run_benchmark.py lives)
python run_benchmark.py --model-tier portable --lane eager --quant none --shape short --log-dir .
```

Useful flags: `--model-tier {portable,quantized}`, `--lane {eager,compiled}`,
`--quant {none,int4,nvfp4}`, `--shape {short,long,sustained}`, `--no-gpu`,
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
| `quant`      | `none`     | `none`, `int4`, `nvfp4`                |
| `shape`      | `short`    | `short`, `long`, `sustained`          |

## Known hardware-validation gaps (explicitly tracked, not hidden)

- **N1X (Windows Arm64) + CUDA is a new capability.** The current `pytorch_inf`
  Arm64 path is CPU-only; this scenario's Arm64 GPU lane (including the
  NVIDIA wheel hash and `triton-windows`/`torchao` Arm64 wheel availability)
  has **not been run on physical N1X hardware** in this change. If
  `triton-windows`/`torchao`/`safetensors` lack prebuilt Arm64+CP314 wheels at
  execution time, the Rust/Visual Studio native-build fallback used by the
  original `pytorch_inf_prep.ps1` for `safetensors` is not currently
  replicated here and may need to be added.
- **NVFP4 (E2M1)** requires Blackwell-class (`sm_100`+) compute capability.
  `capability.gate_quant_lane()` detects and reports this; `run_benchmark.py`
  explicitly raises rather than emulating the kernel path or falling back to
  CPU when gated. No NVFP4 measurements are included because no Blackwell N1X
  hardware was available to validate it.
- **No performance numbers are reported in this change.** All metrics code is
  implemented and unit-tested at the config/capability/metrics-math level
  only; end-to-end numbers require real GPU hardware (CUDA on x64/N1X, MPS on
  Mac) that was not available in this environment.

## Divergences from `pytorch_inf`

- Different model family (Qwen3 vs. Phi-4-mini), two tiers instead of one,
  pinned by immutable revision instead of floating `main`.
- Python 3.14.8 instead of 3.12.10/3.13.1.
- `.generate()`-based decode loop replaced by a manual KV-cache loop for
  accurate prefill/TTFT/decode separation.
- Adds INT4/NVFP4 quantized lanes, `torch.compile` lane, and sustained-shape
  config (not present in `pytorch_inf`).
- Adds hardware-free unit tests for config/capability/metrics (see `tests/`).
