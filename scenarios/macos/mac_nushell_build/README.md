# mac_nushell_build

Clean offline release build of the Nushell nu application with default features (not the plugin workspace) on MacOS.

## Self-contained scenario

This package owns its lifecycle module, `mac_nushell_build_resources/build.py`,
`mac_nushell_build_resources/invoke.sh`, pinned JSON recipe, and regression tests.
There is no shared Rust scenario module or resource directory. The preparation
and build implementation is intentionally duplicated so removing another Rust
scenario does not remove this one's dependencies. Platform variants are also
self-contained, following HOBL's per-platform scenario layout.

The DUT receives only this package's resources in `<dut_exec_path>/mac_nushell_build_resources`.
Its Python environment lives inside that directory; source, Rust installation,
Cargo cache, targets and ownership markers live in `<dut_exec_path>/mac_nushell_build-work`.
Uploads preserve the existing environment. Prep verifies resources on every
setup, rather than trusting only the status marker. The resource-path change
uses prep version 2. Old prototype `rust_build_resources` directories are not
automatically deleted: inspect any existing DUT before removing legacy data.

## Prerequisites and parameters

Git, rustup, and native development tools must already be installed (Visual
Studio C++/SDK on Windows; Xcode Command Line Tools on macOS). Missing tools fail
explicitly. Prep uses HOBL pyenv, installs the pinned Python version only if
missing, and creates a private dependency-free venv without changing shared
Python packages.

Defaults: `loops=1`, `jobs=0` (all logical CPUs), `toolchain=1.100.0`.
The JSON recipe pins source and compiler versions. Upstream default features,
release profiles and linker configuration are preserved. No distribution PGO,
custom profile overrides, plugin builds or release packaging are added.

Select `mac_nushell_build` with the same HOBL profile and instrumentation used for other
developer scenarios. Windows/macOS x64 and Arm64 are supported by their
respective packages; Linux is not supported.

## Measurement and lifecycle

The timed command is:

```text
cargo build --frozen --release -p PACKAGE --bin BINARY --jobs N --timings --message-format=json
```

`scenario_runtime` and `build_time` are the same Cargo wall-clock interval.
Prep, downloads, native-tool discovery, target deletion, provenance checks,
binary smoke checks and result collection are outside this metric. The outer
HOBL DAQ/trace window may include wrapper work and is not the Cargo-only metric.
Every sample starts with empty compiler outputs; dependency sources and OS
caches remain warm. Ambient compiler overrides are removed; checked-in project
configuration remains intact.

Results include key/value CSV, per-sample JSON, Cargo stdout/stderr and timing
HTML, source/tool hashes, runner inventory and binary smoke checks. macOS also
records child CPU/RSS; summed Cargo unit durations are not elapsed build time.
Cancellation targets only the owned process tree. Concurrent work is rejected.
Teardown removes only target outputs, preserving all prep-installed resources.
A stale lock requires operator investigation, not automatic deletion.

## Validation

From the repository root:

```text
python -B -m unittest discover -s scenarios/macos/mac_nushell_build/mac_nushell_build_resources/tests -v
```

Tests cover lifecycle ordering, failures, cancellation, owned cleanup, isolated
environments, and loading/running the scenario with only its package present.
Standalone CI uses this package's launcher with an explicit Python executable
and temporary work/data directories. Prior hosted build evidence is linked in
PR #223; relocation does not change the measured Cargo command or source pins.
Physical-DUT, SimpleRemote, DAQ and mixed-workload qualification remain separate.
