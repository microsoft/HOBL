# .NET Aspire Build Workload

Builds the [.NET Aspire](https://github.com/dotnet/aspire) cloud-app orchestration stack from
source (tag `v9.4.2`). It restores, cleans, then performs a no-restore rebuild of
`Aspire.slnx` and reports build time — a large managed (.NET / MSBuild) build workload.

## What HOBL sets up (from `net_aspire_resources/net_aspire_prep.ps1`)

- winget: .NET SDK 10 preview, .NET SDK 8, Git
- Clones `dotnet/aspire` @ `v9.4.2` to `<drive>\aspire`

## Run it standalone (Windows)

```powershell
winget install --id Microsoft.DotNet.SDK.Preview --source winget --version 10.0.100-preview.5.25277.114
winget install --id Microsoft.DotNet.SDK.8 --source winget
winget install --id Git.Git --source winget

git clone https://github.com/dotnet/aspire.git
cd aspire
git checkout v9.4.2

# Timed workload
dotnet restore Aspire.slnx
dotnet clean Aspire.slnx
dotnet build Aspire.slnx --no-restore
```

## Optional MSBuild binary logs

Binary logging is disabled by default. To enable it, add this to the HOBL profile:

```ini
[net_aspire]
binlog=1
```

Set `binlog=0` to disable it. When enabled, each build writes a separate
`net_aspire_build_<timestamp>.binlog` to `<drive>\hobl_data`, which HOBL collects
with the scenario results. Only the build is logged, not clean or restore.
Binary logging adds overhead to the measured build time; keep this setting
consistent when comparing results.

Existing prepared DUTs receive the updated run script when binary logging is
enabled, without rerunning prep. For standalone use, pass `-binlog` to
`net_aspire_resources\net_aspire_run.ps1`.

The macOS `mac_net_aspire` scenario supports the same default-off setting:

```ini
[mac_net_aspire]
binlog=1
```

For command-line overrides, append `mac_net_aspire:binlog=1` to the HOBL command.
Each build writes `mac_net_aspire_build_<timestamp>_<pid>.binlog` to
`/Users/Shared/hobl_data` for result collection. Standalone macOS runs accept
`--binlog` on `mac_net_aspire_run.sh`. Prepared-DUT updates, build-only logging,
and timing overhead work the same way as on Windows.

## Windows build experiments

These independent options affect only the timed `dotnet build` command.
Prep, clean, and restore are unchanged, and existing prepared DUTs receive the
updated run script when either option is enabled without rerunning prep.

| HOBL parameter | Default | Build effect |
| --- | --- | --- |
| `skip_playwright_browser_install` | `0` | Set to `1` to add `-p:InstallBrowsersForPlaywright=false`. |
| `max_cpu_count` | `0` | Set to a positive integer to add `-m:<value>`. `0` omits the switch and keeps the original default; it does not mean single-threaded. |

Append these overrides to your Windows `net_aspire` HOBL command:

```powershell
# Experiment A: only skip repeated Playwright browser preparation
net_aspire:skip_playwright_browser_install=1 net_aspire:max_cpu_count=0

# Experiment B: original workload, only change MSBuild parallelism
net_aspire:skip_playwright_browser_install=0 net_aspire:max_cpu_count=12
```

The resulting build commands are, respectively:

```powershell
dotnet build Aspire.slnx --no-restore -p:InstallBrowsersForPlaywright=false
dotnet build Aspire.slnx --no-restore -m:12
```

Both parameters can also be set under `[net_aspire]` in the profile. Explicitly
resetting the other parameter as shown above keeps experiments A and B isolated,
even if the profile contains an earlier override. Keep power mode, binlog
settings, and other test settings identical when comparing results. These are
experimental controls, not a guarantee of faster builds.

Standalone runs accept `-skipPlaywrightBrowserInstall` and `-maxCpuCount 12`
on `net_aspire_run.ps1`. The chosen build command is recorded in the run log.

## Notes

- On ARM64, HOBL points `DOTNET_INSTALL_DIR` at the system dotnet to avoid pulling an
  x64-only legacy runtime. If `dotnet restore` complains about an old runtime, set
  `$env:DOTNET_INSTALL_DIR="C:\Program Files\dotnet"`.
- Aspire restores only from Microsoft/dnceng NuGet feeds. Default: 4 loops.
