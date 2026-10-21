# Developing Command-based Scenarios

This guide covers conventions, patterns, and requirements for modifying or creating developer scenarios in the HOBL codebase. 

## Table of Contents

- [Scenario Structure](#scenario-structure)
- [Platform Parity](#platform-parity)
- [PowerShell Coding Standards (Windows)](#powershell-coding-standards-windows)
- [Shell Script Standards (macOS)](#shell-script-standards-macos)
- [Timing and Metrics](#timing-and-metrics)
- [Prep Version Bumping](#prep-version-bumping)
- [Error Handling](#error-handling)
- [Path Handling](#path-handling)
- [Architecture Awareness](#architecture-awareness)
- [ETW Phase Markers (Windows)](#etw-phase-markers-windows)
- [Python Path Resolution](#python-path-resolution)
- [Visual Studio Integration](#visual-studio-integration)
- [Checklist Before Submitting a PR](#checklist-before-submitting-a-pr)

---

## Scenario Structure

Each developer scenario has both a **Windows** and **macOS** variant. The folder layout follows this pattern:

```text
scenarios/
  windows/<scenario>/
    <scenario>.py                    # Python class (orchestrator)
    __init__.py
    <scenario>_resources/
      <scenario>_prep.ps1            # One-time setup (install deps, clone repos)
      <scenario>_run.ps1             # Timed workload execution
      <scenario>_teardown.ps1        # Cleanup (optional)
  MacOS/mac_<scenario>/
    mac_<scenario>.py
    __init__.py
    mac_<scenario>_resources/
      mac_<scenario>_prep.sh
      mac_<scenario>_run.sh
```

### Python Orchestrator (`<scenario>.py`)

The Python file defines a class that inherits from `scenarios.app_scenario.Scenario` and controls the scenario lifecycle:

| Method | Purpose |
| --- | --- |
| `setUp()` | Checks `prep_version`, uploads resources to DUT, runs prep script if needed |
| `runTest()` | Executes the run script in a loop (default iteration count set via `Params.setDefault`) |
| `tearDown()` | Calls base tearDown, then runs teardown script if one exists |
| `kill()` | Emergency cleanup of processes |

Key class attributes:

```python
module = __module__.split('.')[-1]     # Auto-derived scenario name
prep_version = "2"                      # Controls prep re-execution (see below)
resources = module + "_resources"       # Resource folder name
```

### Script Roles

- **Prep script** — Installs dependencies (SDKs, tools, repos). Runs once per `prep_version`. Should be idempotent where possible.
- **Run script** — The timed workload. Called multiple times (loop iterations). Must produce metrics CSV.
- **Teardown script** — Optional cleanup after all iterations complete.

---

## Platform Parity

Windows and macOS scripts for the same scenario must be **functionally equivalent**:

- Time the same phases (e.g., if Windows times `build`, macOS must also time `build`)
- Use the same CSV key names (e.g., both use `build_time`, not `build_real` on one and `build_time` on the other)
- Compute `scenario_runtime` the same way — always wall-clock time
- macOS scripts **may** capture extra detail (e.g., `user`, `sys`, `cputime` via `/usr/bin/time -p`), but `scenario_runtime` must match semantically

**Before modifying one platform, check the other platform's script to keep them aligned.**

---

## PowerShell Coding Standards (Windows)

### Script Template

Every Windows prep/run script should follow this structure:

```powershell
param(
    [string]$logFile = ""
)

$scriptDrive = Split-Path -Qualifier $PSScriptRoot
if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\<scenario>_run.log" }

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function log {
    [CmdletBinding()] Param([Parameter(ValueFromPipeline)] $msg)
    process {
        if ($msg -Match " ERROR - ") {
            Write-Host $msg -ForegroundColor Red
        } else {
            Write-Host $msg
        }
        Add-Content -Path $logFile -encoding utf8 "$msg"
    }
}

function check {
    param($code)
    if ($code -ne 0) {
        " ERROR - Last command failed." | log
        Exit $code
    }
}

function checkWinget {
    param($code)
    if ($code -eq 0) {
        "Winget command succeeded" | log
    } elseif ($code -eq -1978335189) {
        "Package already installed (this is OK)" | log
    } elseif ($code -eq -1978335215) {
        "No applicable upgrade found (this is OK)" | log
    } else {
        " ERROR - Winget command failed with exit code: $code" | log
        Exit $code
    }
}
```

### Execution Policy

Scripts that use `pyenv install` (which calls `Expand-Archive`) must set execution policy early:

```powershell
$executionPolicy = Get-ExecutionPolicy -Scope Process
if ($executionPolicy -eq "Restricted" -or $executionPolicy -eq "Undefined") {
    Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process -Force -ErrorAction Stop
}
```

---

## Shell Script Standards (macOS)

macOS scripts use `/bin/sh` and follow this pattern:

```sh
#!/bin/sh

LOG_DIR="/Users/Shared/hobl_data"
METRICS_FILE="$LOG_DIR/mac_<scenario>_results.csv"

check_status() {
    if [ $? -ne 0 ]; then
        echo " ERROR - $1 failed"
        exit 1
    fi
    echo "✓ $1 successful"
}

check_command() {
    if command -v "$1" >/dev/null 2>&1; then
        echo "✓ $1 is available"
        return 0
    else
        echo " ERROR - $1 is not available"
        return 1
    fi
}
```

---

## Timing and Metrics

### Run scripts must produce a CSV

Every run script writes a `<scenario>_results.csv` to the `hobl_data` directory in `key,value` format:

```csv
scenario_runtime,45.23
build_time,45.23
```

- `scenario_runtime` is **required** — it represents total wall-clock time of the timed workload
- Additional phase timings are encouraged (e.g., `build_time`, `test_time`)

### Windows timing pattern

```powershell
$buildDuration = Measure-Command {
    dotnet build Aspire.slnx --no-restore > "$logDir\build.log" 2>&1
}
check($lastexitcode)
$buildTime = [math]::Round($buildDuration.TotalSeconds, 2)
```

### macOS timing pattern

```sh
build_start=$(date +%s)
# ... build commands ...
build_end=$(date +%s)
build_time=$((build_end - build_start))
```

### Metrics summary banner

Print a human-readable summary at the end of each run:

```text
========================================
.NET Aspire Metrics Summary
========================================
Build Time:  45.23s
scenario_runtime (total): 45.23s
========================================
```

---

## Prep Version Bumping

Each scenario's Python file contains a `prep_version` string:

```python
prep_version = "2"
```

This controls whether the prep script re-runs on the DUT. The HOBL framework checks this value and only re-runs prep when the version changes.

### Rules

- **Whenever prep or run scripts are modified in a PR**, increment `prep_version` by 1 in the corresponding scenario's Python file
- Increment for **both platforms** if both were changed, or just the affected one
- This only needs to happen **once per PR**, not per commit
- Forgetting to bump means DUTs won't pick up your script changes until someone manually clears the prep status

---

## Error Handling

### Error message format

All error messages **must** use this exact format:

```text
 ERROR - <description>
```

Note the spacing: leading space, `ERROR`, space, dash, space. This is required because the `log` function pattern-matches on `" ERROR - "` to colorize output.

✅ Correct:

```powershell
" ERROR - Last command failed." | log
" ERROR - dotnet not found on PATH" | log
Write-Host " ERROR - Unsupported architecture" -ForegroundColor Red
```

❌ Wrong:

```powershell
"ERROR: something failed" | log
"Error - bad path" | log
```

### Helper functions

Use the standard helpers consistently:

| Function | Use when |
| --- | --- |
| `check($lastexitcode)` | After any command where `$LASTEXITCODE` indicates success/failure |
| `checkWinget($lastexitcode)` | After `winget install` (handles "already installed" codes) |
| `checkCmd($result)` | After commands returning "True"/"False" strings |
| `checkGitClone $code $path` | After `git clone` (handles "already exists" case) |
| `checkSetLocation $path` | Before `Set-Location` to verify path exists |
| `check_status "description"` | macOS equivalent of `check` |

---

## Path Handling

### Windows: Drive-relative paths

**Never hardcode `C:\` or any drive letter.** Scripts may run from any drive.

```powershell
# Derive drive from script location
$scriptDrive = Split-Path -Qualifier $PSScriptRoot

# Use for all HOBL paths
$logFile = "$scriptDrive\hobl_data\scenario.log"
$repoDir = "$scriptDrive\aspire"
```

**System paths are the exception** — `$env:ProgramFiles`, `$env:USERPROFILE`, `$env:TEMP`, etc., resolve correctly on their own.

### macOS: Fixed paths

macOS scripts use `/Users/Shared/hobl_data` and `/Users/Shared/hobl_bin` as standard locations.

---

## Architecture Awareness

Windows scenarios must detect and handle both x64 and ARM64:

```powershell
$osInfo = Get-CimInstance Win32_OperatingSystem
$arch = $osInfo.OSArchitecture
$processorArch = $env:PROCESSOR_ARCHITECTURE

if ($arch -eq "64-bit" -and $processorArch -eq "AMD64") {
    $isARM64 = $false
    $logSuffix = "x64"
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    $isARM64 = $true
    $logSuffix = "ARM64"
} else {
    " ERROR - Unsupported architecture: $arch" | log
    Exit 1
}
```

Use `$isARM64` to conditional-branch where binaries, workarounds, or configurations differ between architectures.

---

## ETW Phase Markers (Windows)

HOBL includes a manifest for the scenario phase marker provider at:

- `scenarios/windows/_dev_tools/HOBL-Scenario-Phases.man`

This manifest maps provider GUID `9f0f6e2e-8d06-4d2f-b8f5-6f1f2d5a1c01` event ID `1` to two Unicode payload fields:

- `Marker`
- `Scenario`

### Registering the manifest for WPA decoding

Run these commands in an elevated PowerShell terminal:

```powershell
$manifestPath = "<repo_root>\scenarios\windows\_dev_tools\HOBL-Scenario-Phases.man"
wevtutil um $manifestPath
wevtutil im $manifestPath
wevtutil gp "HOBL-Scenario-Phases" /ge:true /gm:true
```

Then reopen WPA and reload the ETL file. Generic Events should decode payload text for this provider when metadata matches.

### Marker naming convention

Use this standard marker format:

- `phase.run_prep.start` / `phase.run_prep.end`
- `phase.run_build.start` / `phase.run_build.end`
- `phase.run_test.start` / `phase.run_test.end`

This keeps phase attribution consistent across all developer scenarios and avoids naming collisions with prep/teardown script concepts.

### Emitting markers in run scripts

For Windows scenario run scripts, define an ETW EventSource with:

- Name: `HOBL-Scenario-Phases`
- GUID: `9f0f6e2e-8d06-4d2f-b8f5-6f1f2d5a1c01`
- Event ID: `1`
- Payload: marker string and scenario name

Emit marker pairs immediately around each timed run phase. Example:

```powershell
Write-RunPhaseMarker "phase.run_build.start"
# build work
Write-RunPhaseMarker "phase.run_build.end"
```

---

## Python Path Resolution

HOBL uses **pyenv-win** for Python version management. Do not replace it with `winget install` of Python.

```powershell
# WRONG — returns the pyenv shim, not the real .exe
$python = Get-Command python

# CORRECT — returns the actual python.exe path
$pythonExeRaw = pyenv which python 2>$null
$pythonExe = $pythonExeRaw.Trim()
```

This matters when passing paths to tools like CMake (`-DPython3_EXECUTABLE`) which require the real executable.

---

## Visual Studio Integration

Use `vswhere.exe` to discover Visual Studio — never hardcode installation paths.

```powershell
$vsInfo = getVSVersion -product $vsProduct
$actualVSPath = $vsInfo.Path
$vsDevCmd = Join-Path $actualVSPath "Common7\Tools\VsDevCmd.bat"
```

---

## Checklist Before Submitting a PR

- [ ] Scripts use drive-relative paths (`$scriptDrive`), no hardcoded `C:\`
- [ ] Error messages use the `" ERROR - "` format
- [ ] Standard helper functions (`check`, `log`, etc.) are used consistently
- [ ] `prep_version` incremented in affected scenario Python files (both platforms if both changed)
- [ ] Run script produces `<scenario>_results.csv` with `scenario_runtime`
- [ ] Timing is consistent between Windows and macOS variants
- [ ] CSV key names match across platforms
- [ ] Architecture detection included for Windows scenarios
- [ ] Paths verified with `Test-Path` before use
- [ ] `pyenv which python` used instead of `Get-Command python`
