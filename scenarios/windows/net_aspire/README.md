# .NET Aspire Build Workload

Builds the [.NET Aspire](https://github.com/dotnet/aspire) cloud-app orchestration stack from
source (tag `v9.4.2`). It restores, cleans, then performs a no-restore rebuild of
`Aspire.slnx` and reports build time — a large managed (.NET / MSBuild) build workload.

## What HOBL sets up (from `net_aspire_resources/net_aspire_prep.ps1`)

- winget: stable .NET SDK 11.0.100, .NET SDK 8, Git
- Clones `dotnet/aspire` @ `v9.4.2` to `<drive>\aspire`
- Pins `global.json`'s `sdk.version` and `tools.dotnet` to `11.0.100`, disables
  prerelease SDK selection and roll-forward, and keeps the Aspire source workload unchanged.

SDK `11.0.100` is the latest stable SDK verified against
[Microsoft release metadata](https://builds.dotnet.microsoft.com/dotnet/release-metadata/releases-index.json)
on November 22, 2026. macOS prep applies the same pin before `build.sh` lets
Arcade install the SDK into the Aspire repository's `.dotnet` directory.
Existing DUTs rerun prep for this SDK upgrade (Windows prep version `10`,
macOS prep version `12`).

## Run it standalone (Windows)

```powershell
winget install --id Microsoft.DotNet.SDK.11 --source winget --version 11.0.100
winget install --id Microsoft.DotNet.SDK.8 --source winget
winget install --id Git.Git --source winget

git clone https://github.com/dotnet/aspire.git
cd aspire
git checkout v9.4.2

$config = Get-Content .\global.json -Raw | ConvertFrom-Json
$config.sdk.version = "11.0.100"
$config.sdk.rollForward = "disable"
$config.sdk.allowPrerelease = $false
$config.tools.dotnet = "11.0.100"
$config | ConvertTo-Json -Depth 100 | Set-Content .\global.json -Encoding utf8

# Timed workload
dotnet restore Aspire.slnx
dotnet clean Aspire.slnx
dotnet build Aspire.slnx --no-restore
```

## Notes

- On ARM64, HOBL points `DOTNET_INSTALL_DIR` at the system dotnet to avoid pulling an
  x64-only legacy runtime. If `dotnet restore` complains about an old runtime, set
  `$env:DOTNET_INSTALL_DIR="C:\Program Files\dotnet"`.
- Aspire restores only from Microsoft/dnceng NuGet feeds. Default: 4 loops.
