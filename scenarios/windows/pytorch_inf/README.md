# PyTorch Inference Workload

> **Replacement in progress:** see `scenarios\windows\pytorch_inf_v2\README.md`
> for a GPU-first Qwen3 benchmark (portable BF16 + INT4/NVFP4 quantized
> lanes, stricter TTFT/prefill/decode metric separation, and several
> correctness fixes vs. this scenario). `pytorch_inf` is left unchanged and
> runnable side by side until `pytorch_inf_v2` is validated on real N1X
> hardware.

Runs text-generation inference with [PyTorch](https://pytorch.org/) + Hugging Face
Transformers on `microsoft/Phi-4-mini-instruct`. It generates a response to a prompt and
reports tokens/second, time-to-first-token (TTFT), and total generation time. GPU (CUDA 12.8)
on x64; CPU-only on ARM64.

## What HOBL sets up (from `pytorch_inf_resources/pytorch_inf_prep.ps1`)

- Python (3.12.10 on x64 / 3.13.1-arm on ARM64) via pyenv, in a private venv
- `torch` 2.8.0 (+CUDA 12.8 on x64), `transformers` 4.56.1, `tokenizers`, `safetensors`
  (ARM64 compiles safetensors from source → requires Rust)
- `inference.py` (bundled in `pytorch_inf_resources`)

## Run it standalone (Windows)

```powershell
pyenv install 3.12.10; pyenv local 3.12.10        # 3.13.1-arm on ARM64
python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install torch==2.8.0 transformers==4.56.1 tokenizers==0.22.2
# ARM64: add  --index-url https://download.pytorch.org/whl/cpu
#        and install Rust (winget Rustlang.Rustup) so safetensors can compile

# Timed workload (run from pytorch_inf_resources/, where inference.py lives)
python inference.py --prompt "What is the meaning of life?" --log-dir .
```

## Notes

- `--no-gpu` forces CPU inference on x64. Metrics are written to a CSV in the log dir.
- The model (Phi-4-mini) downloads from Hugging Face on first run.
- Default: 2 loops.
