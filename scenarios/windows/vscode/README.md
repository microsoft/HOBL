# VS Code Build Workload

Compiles [Visual Studio Code](https://github.com/microsoft/vscode) (tag `1.132.0`) from source
via `npm run compile` (TypeScript → `out/`). It reports compile time — a large TypeScript /
Node.js build benchmark.

## What HOBL sets up (from `vscode_resources/vscode_prep.ps1`)

- Visual Studio 2022 C++ build tools (for native modules)
- Node.js **26.9.0**, including its bundled npm, from the official architecture-specific
	archive (SHA-256 verified); Git; Python 3.12.10 (pyenv, required by node-gyp)
- Clones `microsoft/vscode` @ `1.132.0` to `<drive>\vscode`; runs `npm install` during prep

Node is private to `vscode_resources/nodejs/`, not installed globally with winget.
Both prep and run select that runtime and verify its version and native architecture
(Windows x64/ARM64). macOS ARM64 uses the same Node version in its own scenario resources.
Other scenarios' system/Homebrew Node installations are left unchanged.

## Node 26 compatibility and validation

VS Code `1.132.0` specifies Node `24.18.0` and enforces the same major version in its
preinstall script. This workload **deliberately overrides that check** with
`VSCODE_SKIP_NODE_VERSION_CHECK=1` during dependency installation to benchmark Node
`26.9.0`. It does not change the VS Code tag, Electron/native-header targets, lifecycle
scripts, or the timed `npm run compile` command. This is not a claim of upstream
Node 26 support: a full clean prep and compile must be validated on each target.

The prep-version bumps force dependency preparation on existing DUTs. macOS clears
old `node_modules` during prep; Windows already recreates its VS Code clone. Neither
platform downloads Node or installs dependencies inside the timed run. Runs fail
early if the pinned runtime is missing or has the wrong version/architecture.

Node 26 results are a new toolchain baseline and should not be mixed with prior
Node 24 results. Log files record the selected Node/npm versions and runtime path.

## Run it standalone (Windows)

```powershell
winget install --id Git.Git --source winget
# From this HOBL scenario's directory: installs only the private Node runtime.
function log { process { Write-Host $_ } }
. .\vscode_resources\vscode_node.ps1
Enable-VscodeNode -Install
pyenv install 3.12.10; pyenv local 3.12.10
# + Visual Studio 2022 C++ build tools (needed by node-gyp)

git clone https://github.com/microsoft/vscode.git
cd vscode
git checkout 1.132.0
$previousSkipCheck = $env:VSCODE_SKIP_NODE_VERSION_CHECK
try {
	$env:VSCODE_SKIP_NODE_VERSION_CHECK = "1"
	npm install
} finally {
	$env:VSCODE_SKIP_NODE_VERSION_CHECK = $previousSkipCheck
}

# Timed workload
npm run compile
```

## Notes

- Requires PowerShell 7+. Only compile time is measured (no test phase).
- HOBL preserves `node_modules/` between runs and cleans `out/` and `.build/` each loop.
- Default: 1 loop. ARM64 uses Visual Studio Community (Build Tools is x64-only).
