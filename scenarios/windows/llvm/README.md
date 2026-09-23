# LLVM Build Workload

Compiler-infrastructure build benchmark. It clones the
[LLVM project](https://github.com/llvm/llvm-project) at tag `llvmorg-21.1.8`, configures a
Ninja + CMake build, and performs a full from-clean build. It reports total build time — a
heavy, real-world CPU / memory / I/O compile workload.

## What HOBL sets up (from `llvm_resources/llvm_prep.ps1`)

- Python 3.12.10 (pyenv) and Visual Studio 2022 C++ build tools
- winget: Git, Ninja, CMake
- A pre-built LLVM 21.1.8 toolchain (installer → `C:\Program Files\llvm`)
- Clones `llvm/llvm-project` @ `llvmorg-21.1.8` to `<drive>\llvm-project`; build dir `<drive>\build_llvm`

## Optional approved MSI compiler (Windows)

To use a supplied compiler instead of manually installing it before the test,
configure these **scenario parameters on the HOBL host**:

| Parameter | Value |
| --- | --- |
| `llvm:installer_path` | Full local/UNC path to the approved LLVM MSI, accessible to the host account |
| `llvm:installer_sha256` | Independently approved 64-character SHA-256 of that exact package |
| `llvm:compiler_version` | MSI/compiler version, e.g. `24.0.0` |
| `llvm:allow_unsigned_installer` | `0` by default; set `1` only for an explicitly trusted, hash-pinned unsigned package |

Do not commit the MSI, private download links, credentials, or lab paths. A mapped
drive in your interactive session may not exist for the HOBL service account; use
an accessible local path or an authorized UNC share instead.

HOBL checks the hash before upload, transfers the MSI to the DUT's LLVM resources,
and checks its hash, signature, ProductName/ProductVersion and `INSTALL_ROOT`
directory property before installing. The supplied MSI must use that property.
The existing default downloaded EXE remains the path when no MSI is selected.

Installation uses the already-elevated HOBL DUT context and
`msiexec /i ... /qn /norestart REBOOT=ReallySuppress INSTALL_ROOT=... /L*v ...`.
An already-installed ProductCode uses `/fvamus` to repair all files and recache
the selected MSI, rather than silently retaining a same-version older build.
The MSI integration adds no GUI clicks, `Unblock-File`, elevation prompt, or
SmartScreen/Defender/application-control policy changes. Unsigned opt-in does not accept invalid signatures or override
Windows application-control policy. If Windows policy blocks the package, stop
and obtain a signed/approved distribution or administrator-managed approval.
A hash establishes package identity, not publisher trust.

Only MSI exit code `0` completes prep. `3010`/`1641` require a DUT reboot and
another prep attempt; other failures report the installer log in the result data.
Prep does not record success or start the benchmark after these errors.

Both `clang.exe` and `clang-cl.exe` are checked for native PE architecture and
the configured compiler version. The MSI's filename/container architecture is
not proof of its payload architecture. CMake uses the verified compiler's absolute
path. A receipt records the installer and compiler hashes; run validates it before
timing to catch a later compiler replacement.

Prep version **10** deploys this change. A marker in the uploaded resources also
tracks the selected MSI hash/version, so switching packages forces fresh prep,
including switching back to an earlier selection. Keep
`global:prep_status_enable=1`; setting it to zero skips the embedded prep.
To retry after a failure or force an unchanged selection to re-prep, remove only
the DUT's `prep_status/llvm10` marker while no workload is running, then relaunch.

The compiler uses the workload's existing machine-wide LLVM install location
under Program Files, not an isolated per-scenario toolchain. Other workloads may
also use it. Package switching is subject to the MSI's upgrade/downgrade rules;
HOBL does not automatically uninstall another product or force a downgrade.
When returning to the default compiler, a different existing version fails early
with guidance to have the DUT owner restore the default toolchain first.

**Compiler vs workload:** selecting a `24.0.0` compiler does **not** change the
source benchmark from `llvmorg-21.1.8`. The timed Ninja build and metrics are
unchanged, but compiler changes establish a new performance baseline. macOS is
unchanged. Validate installation and a complete build on each intended DUT before
using the resulting measurements.

## Run it standalone (Windows)

```powershell
winget install --id Git.Git --source winget
winget install --id Ninja-build.Ninja --source winget
winget install --id Kitware.CMake --source winget
# + Visual Studio 2022 with the "Desktop development with C++" workload

git clone --depth 1 --branch llvmorg-21.1.8 --config core.autocrlf=false `
  https://github.com/llvm/llvm-project.git

# From a Developer PowerShell (VsDevCmd loaded for your arch, e.g. -arch=x64 or -arch=arm64):
cmake -G Ninja -S llvm-project\llvm -B build_llvm -DCMAKE_BUILD_TYPE=Release `
  -DLLVM_ENABLE_PROJECTS="clang;lld"

# Timed workload
ninja -C build_llvm
```

## Notes

- The CMake configure line above is representative — see `llvm_resources/llvm_prep.ps1`
  for the exact project/runtime targets and flags HOBL uses.
- Load the MSVC environment first (`VsDevCmd.bat -arch=x64` or `-arch=arm64`).
- Expect a long build (tens of minutes or more). Default: 1 loop. Works on x64 and ARM64.
