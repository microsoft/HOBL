# FastAPI Build & Test Workload

Python developer inner-loop benchmark. It builds the [FastAPI](https://github.com/fastapi/fastapi)
library from source using a PEP 517 build (PDM backend), then runs the project's full test
suite under `coverage`. It measures **build time** and **test time** separately and reports
their sum as the scenario runtime — a proxy for Python package build + test performance.

## What HOBL sets up (from `fast_api_resources/fast_api_prep.ps1`)

- Python 3.12.10 via pyenv (isolated venv)
- Visual Studio 2022 C++ build tools (for native extension builds)
- Git (winget)
- Clones `https://github.com/fastapi/fastapi.git` to `<drive>\fastapi`

## Run it standalone (Windows)

```powershell
# 1. Prerequisites
winget install --id Git.Git --source winget
pyenv install 3.12.10; pyenv local 3.12.10

# 2. Clone the repo
git clone https://github.com/fastapi/fastapi.git
cd fastapi

# 3. Isolated venv + build/test tooling
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install uv build
python -m uv sync --no-dev --group tests --extra all --inexact --python .\.venv\Scripts\python.exe

# 4. Timed workload
python -m build                        # PEP 517 build -> dist/
$env:PYTHONPATH = ".\docs_src"
python -m pytest -n 0 --cov --cov-context=test tests scripts\tests
```

## Notes

- The PEP 517 build spins up its own isolated environment. On a proxied corporate network,
  set `$env:PIP_INDEX_URL` to your approved PyPI mirror so build isolation can fetch deps.
- HOBL default: 5 loops (each loop = build + test). Works on x64 and ARM64.
- Set `fast_api:workers=auto` or a non-negative integer to select pytest workers;
  the default `0` keeps tests serial. On macOS, use `mac_fast_api:workers`.
  Example: `hobl.cmd -s fast_api fast_api:loops=1 fast_api:workers=auto`.
