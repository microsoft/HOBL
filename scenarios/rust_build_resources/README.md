# Rust build workloads

These are two independent workloads, not a combined Rust benchmark:

| Platform | rust-analyzer server | Nushell application |
|---|---|---|
| Windows | `rust_analyzer_build` | `nushell_build` |
| macOS | `mac_rust_analyzer_build` | `mac_nushell_build` |
| Linux | `lnx_rust_analyzer_build` | `lnx_nushell_build` |

Each has its own persistent checkout, Rust installation, Cargo source cache,
target directory, Python environment, and result identity. Shared scripts only
implement preparation, execution, validation, and cleanup.

The JSON recipes pin upstream source revisions and Rust 1.100.0. Nushell builds
the complete `nu` binary with default features, not the plugin workspace or the
optional `full` feature. rust-analyzer builds its server binary, not its editor
extension. Release profiles, default features, and repository Cargo settings are
preserved. In particular, rust-analyzer selects `rust-lld` on Windows x64 only;
other Windows configurations retain the standard MSVC linker.

## Preparation and parameters

HOBL must have Git, rustup, and a native development toolchain installed:
Visual Studio C++ tools and Windows SDK on Windows, Xcode Command Line Tools on
macOS, or GCC/Clang and system development headers on Linux. Missing tools fail
with an actionable error. Python uses HOBL's pyenv installation, conditionally
installing the pinned Python version without replacing an existing shared
installation. Each scenario creates its own dependency-free venv.

Parameters are `loops=1`, `jobs=0` (all logical CPUs), and `toolchain=1.100.0`.
Compiler versions must be explicit stable versions compatible with the source
revision (rust-analyzer requires at least 1.98; Nushell requires 1.97.1).
Changing a recipe requires re-preparation. Prep is idempotent and verifies its
resources on every HOBL setup; the prep-status marker alone is not trusted.

## Measurement boundary

The run timer surrounds only:

```
cargo build --frozen --release -p PACKAGE --bin BINARY --jobs N --timings --message-format=json
```

Both `scenario_runtime` and `build_time` are this wall-clock interval, in seconds.
It includes dependency compilation, build scripts, native compilation, and
linking. Checkout, toolchain installation, Cargo fetch, environment discovery,
output-directory deletion, checksum validation, executable smoke checks, and
artifact collection are outside this interval. HOBL's outer DAQ/trace interval
may include those run-script activities; use the explicit build metric for the
compile-time baseline, not the outer scenario duration.

Every sample removes only its owned `target` directory. Dependency sources and
OS file caches remain warm on repeated samples; this is a clean-output benchmark,
not a cold-disk benchmark. No compiler-output cache or custom linker/profile
override is used. Ambient Cargo/Rust/compiler overrides are removed from the
child environment, while checked-in project settings remain intact.

Results include canonical HOBL key/value CSV, per-sample JSON, Cargo stdout and
stderr, Cargo timing HTML, source/tool hashes, runner inventory, and binary smoke
checks. Unix child CPU and peak RSS are also recorded; these are not available
from the Windows stdlib path. Cargo unit durations overlap and include codegen
and linking: do not sum them as elapsed time or label them pure compiler phases.

## Validation and lifecycle

Run helper tests with:

```
python -B -m unittest discover -s scenarios/rust_build_resources/tests -v
```

Standalone CI invokes the same `invoke.ps1` or `invoke.sh` used by HOBL, supplying
an explicit Python executable and temporary work/data directories. It does not
run the HOBL host, SimpleRemote, DAQ, or battery instrumentation. Physical-DUT
qualification is separate from hosted-runner build validation.

Cancellation requests affect only this workload's active command. Teardown
removes only `target`, never prep-installed source, dependencies, or toolchains.
Concurrent operations on the same work directory are rejected. A stale
`active.lock` after a hard process termination requires operator investigation;
the workload never guesses that it is safe to remove a lock or kill an unrelated
process.
