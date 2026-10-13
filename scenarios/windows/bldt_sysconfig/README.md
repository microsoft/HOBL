# Intel BLDT System Configuration Checker

This Windows scenario runs the Intel Battery Life Diagnostic Tool (BLDT) v3.1.1
`SysConfigChecks` command-line flow. It uses the standard BLDT edition by default
and can install or require the AI edition with `use_ai=true`.

The scenario sets `is_prep = True` because it collects configuration diagnostics,
not power measurements. HOBL skips regular measurement tools and measurement
callbacks; configured prep tools can still run. `runTest()` still executes the
checks on each scenario invocation, independently of the installation prep marker.

## Parameters

| Parameter | Default | Values | Description |
|---|---:|---|---|
| `loops` | `1` | Positive integer | Number of independent SysConfigChecks runs. |
| `use_ai` | `false` | `true`, `false` | Request the AI edition. An installed AI edition satisfies a standard request; standard prep never replaces AI. |
| `power_source` | `AC` | `AC`, `DC` | Value passed to BLDT as `pwrsrc`. |

Example:

```text
bldt_sysconfig:loops=1
bldt_sysconfig:use_ai=false
bldt_sysconfig:power_source=AC
```

## Lifecycle

- **Compatibility** runs at the start of prep, including validation-only calls.
  It logs the detected OS and full CPU name, rejects Windows versions older than
  Windows 10, non-Intel CPUs, and recognized unsupported Intel families or
  pre-8th-generation Core models. Unrecognized Intel model names produce a warning
  for manual verification rather than a guessed rejection. These checks follow
  the bundled v3.1.1 user guide's general prerequisites, not the AI Analyzer's
  separate requirements. They do not change AC/DC state or enforce AI RAM limits.
- **Prep** discovers BLDT through both uninstall registry views and validates the
  registered executable and version. Executable discovery also reads Intel's
  `HKLM\SOFTWARE\Intel\Battery Life Diagnostic Tool` `Path` value (and its
  32-bit registry view), since the MSI may leave uninstall installation paths empty.
  If installation is required, it checks administrator privileges before downloading
  the official Intel ZIP on the DUT, checks the published SHA-256, validates the
  extracted MSI hash, Intel signature, ProductCode, UpgradeCode, and version,
  and performs a quiet non-restarting install. Prep validates the installed
  files before returning success. Python performs a separate validation-only
  call before writing the HOBL prep marker; either failure prevents a success marker.
- **Setup** uploads current scenario scripts and performs live validation even
  when the HOBL prep marker exists. Script fixes do not require reinstalling BLDT.
  A missing executable, wrong version, or incomplete requested AI installation
  causes prep to run again.
- **Run** invokes:

  ```text
  BatteryLifeDiagnosticTool.exe --type SysConfigChecks --params pwrsrc:<AC|DC> --telemetry false
  ```

  It captures stdout, stderr, runtime, and every report file created or changed
  under `%USERPROFILE%\Intel\BatteryLifeDiagnostic`.
  The process handle is retained until exit so Windows PowerShell can reliably
  read the exit code. New reports are copied before rejecting a nonzero exit code.
  Run calls use HOBL's default fail-fast exception handling and exit-code checks;
  a failed call stops the remaining loops.
- **Teardown** uses the standard HOBL result collection path. It does not uninstall
  BLDT or remove shared AI analyzer/model assets.
- **Kill** targets only BLDT's main and UI executables.

The Python structure follows Cinebench's setup-driven prep pattern: `setUp()`
checks live installation state and calls `_run_prep()` when needed.
PowerShell uses the existing pipeline `log` convention, optional `logFile`
parameter, and `" ERROR - "` formatting. Shared BLDT discovery and installer
helpers stay in `bldt_common.ps1` because prep and run both validate the same
installation. The scripts use Windows PowerShell without adding a PowerShell 7
dependency. Prep uses the normal sequential HOBL lifecycle, without a separate
receipt file or cross-scenario locking.

Each BLDT scenario carries its own helper and prep scripts in its resource
folder; there is no separate shared-resources scenario. Apply installer/helper
fixes to both copies. Both scenarios still reuse the machine's BLDT installation,
download cache, and `bldt1` prep marker, with live validation on every setup.

## Results

Each loop creates a timestamped directory under
`hobl_data\bldt_sysconfig`. It contains:

- `bldt_sysconfig_results.csv` and `.json`
- `bldt_sysconfig_run.log`
- BLDT stdout and stderr
- the complete newly created/updated JSON, HTML, ZIP, log, and supporting report files

The latest loop also writes the conventional
`hobl_data\bldt_sysconfig_results.csv` and `.json` files for HOBL result rollup.

The initial stable metrics are `scenario_runtime`, BLDT version/edition, requested
power source, report-type creation indicators, and report file count. Detailed
check/pass/fail metrics are intentionally deferred until a real v3.1.1
SysConfigChecks JSON report is captured and its schema is verified.

## Known validation work

A disposable Intel laptop should be used to confirm BLDT's undocumented process
exit-code contract, browser-launch behavior, first-run UI suppression, and the
v3.1.1 report JSON schema. AI prep additionally requires the Intel package to
materialize the per-user analyzer under `%LOCALAPPDATA%\Intel\BLDT-Analyzer` and
the packaged models under `%ProgramData%\BLDT-Analyzer\models`; prep fails rather
than claiming AI readiness if either payload is missing.
