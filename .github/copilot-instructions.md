git git# GitHub Copilot Instructions for HOBL

## PowerShell Coding Standards

### Error Message Formatting
When logging or displaying error messages in PowerShell scripts:
- Always use the format: `" ERROR - "` (note the spacing)
- Leading space before ERROR
- Single space after ERROR
- Dash character `-`
- Single space after the dash
- Example: `" ERROR - Last command failed."`
- Example: `Write-Host " ERROR - Unsupported architecture" -ForegroundColor Red`
- Example: `if ($msg -Match " ERROR - ") { ... }`

### Defensive Programming and Path Handling
- **Never assume default installation paths** unless explicitly instructed to do so
- Always use discovery mechanisms to find installed software:
  - For Visual Studio: Use `vswhere.exe` to query actual installation paths
  - For other tools: Use registry queries, environment variables, or PATH lookups
- Verify paths exist before using them in operations
- Log the actual paths found for debugging and transparency
- Support non-default installation locations (e.g., custom drives, custom folders)
- Example: Use `getVSVersion` function to find VS, then use `$vsInfo.Path` instead of hardcoded `$vsInstallPath`

### Drive-Relative Paths (No Hardcoded C: Drive)
- **Never hardcode `c:\` or any drive letter** in Windows scenario scripts — the scripts may run from any drive
- Always derive the drive letter from the script's own location using `$PSScriptRoot`:
  ```powershell
  $scriptDrive = Split-Path -Qualifier $PSScriptRoot
  ```
- Use `$scriptDrive` to construct all HOBL working paths (`hobl_data`, `hobl_bin`, repo clones, temp dirs, etc.)
- For `param()` block defaults: use an empty string and set the real default after `$scriptDrive` is computed:
  ```powershell
  param(
      [string]$logFile = ""
  )
  $scriptDrive = Split-Path -Qualifier $PSScriptRoot
  if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\scenario_prep.log" }
  ```
- **System paths are the exception** — paths under `$env:ProgramFiles`, `$env:USERPROFILE`, `$env:TEMP`, etc. are fine since they resolve to the correct OS drive automatically
- When reviewing existing scripts, replace any bare `c:\hobl_data`, `c:\hobl_bin`, `c:\opencv`, etc. with `$scriptDrive\...`

### Visual Studio Integration
- Use `vswhere.exe` to locate Visual Studio installations (handles all editions and custom paths)
- The `getVSVersion` function returns actual installation path - always use it
- Never hardcode paths like `"${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools"`
- Verification functions should query for actual paths, not assume defaults
- Example pattern:
  ```powershell
  $vsInfo = getVSVersion -product $vsProduct
  $actualVSPath = $vsInfo.Path
  $vsDevCmd = Join-Path $actualVSPath "Common7\Tools\VsDevCmd.bat"
  ```

### pyenv-win and Python Path Resolution
- HOBL uses `pyenv-win` for Python version management across scenarios — do NOT replace it with simple `winget install` of Python
- **Never use `Get-Command python` to resolve the Python executable path** — it returns the pyenv batch file shim, not the actual `python.exe`
- Always use `pyenv which python` to get the real Python executable path
- Example:
  ```powershell
  $pythonExeRaw = pyenv which python 2>$null
  if ($pythonExeRaw) {
      $pythonExe = $pythonExeRaw.Trim()
      if (Test-Path $pythonExe) {
          "Using Python: $pythonExe" | log
      }
  }
  ```
- When passing Python paths to tools like CMake (`-DPython3_EXECUTABLE`), the path must point to the actual `.exe`, not a shim/batch file

### Shared-State Hazards Across Scenarios (CRITICAL — read before touching any prep script)

Multiple HOBL scenarios share the same pyenv-managed Python version (Windows: `3.12.10-arm` is used by `pytorch_inf`, `llvm`, `nodejs`, `vscode`, `opencv_build`, `fast_api`; macOS: `3.12.10` is used by `mac_pytorch_inf`, `mac_llvm`, `mac_nodejs`, `mac_opencv_build`, `mac_net_aspire`). When several scenarios share a single pyenv version directory, **anything one scenario does to that directory affects every other scenario**.

The most damaging operation observed in production was `pyenv install <version> -f`, which deletes and re-extracts the entire `~\.pyenv\pyenv-win\versions\<version>\` directory — including `Lib\site-packages\`. A single scenario's prep silently wiped torch (and every other pip-installed package) from another scenario's site-packages. Because HOBL's `prep_status` file says prep is "done," the next iteration skipped prep and failed cryptically.

**Rules to prevent this class of bug:**

- **Never** use force flags on version-manager installs that target shared toolchains:
  - ❌ `pyenv install <version> -f` (Windows or macOS)
  - ❌ `nvm install <version> --reinstall-packages-from=<other>` (clobbers a shared Node)
  - ❌ `brew reinstall <pkg>` for a `brew` package another scenario depends on
  - ❌ `rustup toolchain install <toolchain> --force-non-host`

  Replace with a conditional install pattern:

  Windows:
  ```powershell
  $installedVersions = (pyenv versions --bare 2>$null) -split "`n" | ForEach-Object { $_.Trim() }
  if ($installedVersions -notcontains $pythonVersion) {
      "Installing Python $pythonVersion via pyenv..." | log
      pyenv install $pythonVersion
      check($lastexitcode)
  } else {
      "Python $pythonVersion already installed via pyenv — preserving existing install" | log
  }
  ```
  macOS (bash):
  ```bash
  if ! pyenv versions --bare | grep -qx "$PYTHON_VERSION"; then
      log "Installing Python $PYTHON_VERSION via pyenv..."
      pyenv install "$PYTHON_VERSION"
  else
      log "Python $PYTHON_VERSION already installed via pyenv — preserving existing install"
  fi
  ```

- **Never** `pip install` directly into the shared pyenv site-packages. Always create a **per-scenario venv** at `<scriptDrive>\hobl_bin\<scenario>_resources\.venv\` (Windows) or `$BIN_DIR/<scenario>_resources/.venv/` (macOS). All `pip install` calls must target the venv's pip via absolute path.

  Windows venv creation pattern (in prep.ps1, after pyenv is set up):
  ```powershell
  $venvDir = "$scriptDrive\hobl_bin\<scenario>_resources\.venv"
  $pyenvPython = (pyenv which python 2>$null).Trim()
  if (-not (Test-Path $pyenvPython)) {
      " ERROR - pyenv python not found at: $pyenvPython" | log
      Exit 1
  }
  if (Test-Path $venvDir) { Remove-Item -Recurse -Force $venvDir }
  & $pyenvPython -m venv $venvDir
  check($lastexitcode)

  $venvPython = Join-Path $venvDir "Scripts\python.exe"
  $venvPip    = Join-Path $venvDir "Scripts\pip.exe"

  & $venvPip install -r requirements.txt
  check($lastexitcode)
  ```
  macOS equivalent uses `bin/python` and `bin/pip` instead of `Scripts/`.

- **Never** `pip install --upgrade pip` in a venv. The pip bundled with the pinned Python release is what we want — reproducible across DUTs, no network dependency.

- **Always** invoke the venv's python by absolute path in run.ps1 / teardown.ps1 — never via `python` on PATH:
  ```powershell
  $venvPython = "$scriptDrive\hobl_bin\<scenario>_resources\.venv\Scripts\python.exe"
  if (-not (Test-Path $venvPython)) {
      " ERROR - venv missing at $venvPython. Re-prep required:" | log
      " ERROR -   delete C:\hobl_bin\prep_status\<scenario><version> on the DUT and re-run." | log
      Exit 1
  }
  & $venvPython script.py args
  ```

- **Always** validate critical imports at the top of run.ps1 with a fail-fast guard. This converts a cryptic `ModuleNotFoundError` 200 lines into the workload into an actionable error message at run start:
  ```powershell
  & $venvPython -c "import torch, transformers; print('torch', torch.__version__)" 2>&1 | log
  if ($LASTEXITCODE -ne 0) {
      " ERROR - venv has missing/broken Python packages." | log
      " ERROR - Possible causes: Defender quarantine, disk cleanup, or external tampering." | log
      " ERROR - Re-prep required: delete C:\hobl_bin\prep_status\<scenario><version> on the DUT and re-run." | log
      Exit 1
  }
  ```

- **The venv survives `pyenv install -f` from other scenarios** because it lives outside the pyenv version directory. Even if a defensive boundary breaks elsewhere, the venv directory and its site-packages are untouched. (On Windows, the venv even survives a Python force-reinstall as long as it's the same major.minor.patch version — see the Python venv docs for details.)

- **The `prep_status` file alone is not a reliable signal that prep artifacts are still present.** External actors (Microsoft Defender quarantine, OS re-imaging, Windows Update, lab tech intervention) can remove prep-installed files without HOBL knowing. The run-time import validation guard above is the durable defense against this.

### Diagnosing Scenario Failures After iter 0 Succeeded

When a scenario succeeds on iter 0 but fails on subsequent iters with what looks like missing dependencies, check **in this order**:

1. **What `prep_status` file does the DUT have?** Look in `hobl.log` for the `if exist C:\hobl_bin\prep_status\<scenario><N>` RPC call. If `<N>` doesn't match the host's current `prep_version` value, **the host hasn't been updated** — the lab's local clone needs `git pull`.
2. **Did another scenario between iter 0 and the failing iter call `pyenv install -f`?** Search intermediate scenarios' preps for the pattern. If yes, this PR's venv pattern is the fix.
3. **Was anything quarantined by Defender?** Check Windows Event Viewer → Microsoft → Windows → Windows Defender → Operational.
4. **Was the DUT re-imaged between iterations?** Look at the study profile's `os_install` parameter and timestamps on `C:\Users\<user>` vs. `C:\hobl_bin\prep_status\`.
5. **Did `pyenv global` get switched by another scenario's prep?** Run `pyenv version` on the DUT; should match what the failing scenario expects.

### Execution Policy for PowerShell Archive Module
- Scripts that use `pyenv install` (which internally calls `Expand-Archive`) must set the execution policy at the top of the script
- Without this, `Microsoft.PowerShell.Archive` module fails to load on fresh Windows installs
- Always include this block early in prep scripts that use pyenv:
  ```powershell
  $executionPolicy = Get-ExecutionPolicy -Scope Process
  if ($executionPolicy -eq "Restricted" -or $executionPolicy -eq "Undefined") {
      Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process -Force -ErrorAction Stop
  }
  ```

### General Guidelines
- Use consistent error handling patterns across all scenario scripts
- Maintain architecture-aware code (x64 vs ARM64) where applicable
- Follow existing function patterns for check(), checkCmd(), log(), etc.
- Verify all prerequisites exist before proceeding with operations
- Provide clear error messages indicating what's missing and how to fix it

### Developer Scenario Timing and Metrics
- Every run script must report `scenario_runtime` (in seconds) via a metrics summary banner and a CSV results file
- **Timing measurements must be consistent between macOS and Windows** for the same scenario — the same phases must be timed, and `scenario_runtime` must be computed the same way on both platforms
- Before adding or changing timing in a scenario, check the other platform's script to ensure they stay aligned
- macOS scripts may capture additional detail (user, sys, cputime via `/usr/bin/time -p`) but `scenario_runtime` must always use wall-clock time on both platforms
- **CSV key names must match between platforms** where the same value is reported on both. Use the canonical key names below.

#### Canonical CSV Key Names
The following keys are shared across platforms. Where a key appears on both macOS and Windows, it must use the same name:

**Build/compile scenarios** (shared keys):
- `scenario_runtime` — wall-clock time for the full timed portion (seconds)
- `build_time` — wall-clock time for the build phase (seconds)
- `test_time` — wall-clock time for the test phase, if applicable (seconds)
- `architecture` — CPU architecture, where reported

macOS-only additional keys (from `/usr/bin/time -p`):
- `build_user`, `build_sys`, `build_cputime`
- `test_user`, `test_sys`, `test_cputime`

**AI/inference scenarios** (shared keys):
- `scenario_runtime` — total inference/generation time (seconds)
- `time_to_first_token_ms` — time to first token in milliseconds
- `time_to_first_token_s` — time to first token in seconds
- `tokens_per_second` — token generation rate
- `total_tokens_generated` — number of tokens generated
- `total_generation_time_s` — total generation time in seconds
- `ai_model` — model name (not `model`)
- `ai_device` — device type (not `device`)
- `architecture` — CPU architecture, where reported

### Prep Version Bumping
- Each developer scenario has a `prep_version` string in its Python file (e.g., `prep_version = "2"`) that controls whether the prep script re-runs on the DUT
- **When a prep change REQUIRES re-execution on existing DUTs** (e.g., a different Python version, a new mandatory dependency, a changed install path), increment `prep_version` by 1 in the corresponding scenario's Python file (both Windows and macOS).
- **When a prep change is purely defensive and safe to re-apply against existing state** (e.g., replacing `pyenv install -f` with a conditional install that's a no-op when the version exists), **do NOT bump prep_version**. Bumping forces every lab DUT to re-prep, which can take 10–15 minutes per scenario across the whole fleet. The fix should ship without forcing a re-prep wave.
- Decision rule: ask "if this prep is skipped on an existing DUT, will the run still work correctly?" If yes → don't bump. If no → bump.
- This only needs to happen **once per PR** — not per commit
- Always increment for both platforms if both were changed, or just the affected platform if only one was modified

### Teardown Script Safety Rules
- Teardown scripts **must only clean up artifacts that the run script will recreate**
- Teardown scripts **must never remove content installed during prep** (e.g., `node_modules`, Maven caches, cloned repos, conda/micromamba environments, installed packages)
- **Never use `git clean -xfd`** in teardown — it removes all untracked/ignored files including prep-installed dependencies
- Instead, use targeted removal of specific build output directories (e.g., `out/`, `.build/`, `target/`)
- Before adding cleanup to a teardown script, verify: "Will the run script recreate this?" If not, don't remove it
- The prep/run/teardown lifecycle: prep installs dependencies (runs once), run builds/tests (runs many times), teardown cleans build outputs between runs (must not undo prep)

## Developer Scenarios
When the user refers to "developer scenarios", they mean the following 13 scenarios. Each has both macOS and Windows variants. The Rust scenarios share their prep/run scripts in `scenarios/rust_build_resources/`; the other scenarios keep platform-specific resource folders. The folder structure is as follows:

| Scenario | macOS folder | Windows folder |
|---|---|---|
| Fast API | `scenarios/MacOS/mac_fast_api/` | `scenarios/windows/fast_api/` |
| Foundry Local | `scenarios/MacOS/mac_foundrylocal/` | `scenarios/windows/foundrylocal/` |
| LLVM | `scenarios/MacOS/mac_llvm/` | `scenarios/windows/llvm/` |
| MLPerf | `scenarios/MacOS/mac_mlperf/` | `scenarios/windows/mlperf/` |
| .NET Aspire | `scenarios/MacOS/mac_net_aspire/` | `scenarios/windows/net_aspire/` |
| Node.js | `scenarios/MacOS/mac_nodejs/` | `scenarios/windows/nodejs/` |
| Ollama | `scenarios/MacOS/mac_ollama/` | `scenarios/windows/ollama/` |
| OpenCV Build | `scenarios/MacOS/mac_opencv_build/` | `scenarios/windows/opencv_build/` |
| PyTorch Inference | `scenarios/MacOS/mac_pytorch_inf/` | `scenarios/windows/pytorch_inf/` |
| Spring Pet Clinic | `scenarios/MacOS/mac_spring_petclinic/` | `scenarios/windows/spring_petclinic/` |
| VS Code | `scenarios/MacOS/mac_vscode/` | `scenarios/windows/vscode/` |
| rust-analyzer Build | `scenarios/macos/mac_rust_analyzer_build.py` | `scenarios/windows/rust_analyzer_build.py` |
| Nushell Build | `scenarios/macos/mac_nushell_build.py` | `scenarios/windows/nushell_build.py` |

When asked to make a change across "all developer scenarios", apply it to all 13 (both platforms unless a specific platform is specified). `testplans/hobl_dev_heavy.ps1` runs this set with platform selection; preserve rust-analyzer and Nushell as distinct workloads.
