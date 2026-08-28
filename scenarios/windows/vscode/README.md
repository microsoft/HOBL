# VS Code Build Workload

Compiles [Visual Studio Code](https://github.com/microsoft/vscode) (tag `1.132.0`) from source
via `npm run compile` (TypeScript → `out/`). It reports compile time — a large TypeScript /
Node.js build benchmark.

## What HOBL sets up (from `vscode_resources/vscode_prep.ps1`)

- Visual Studio 2022 C++ build tools (for native modules)
- Node.js 24.18.0 (winget), Git, Python 3.12.10 (pyenv, required by node-gyp)
- Clones `microsoft/vscode` @ `1.132.0` to `<drive>\vscode`; runs `npm install` during prep

## Run it standalone (Windows)

```powershell
winget install --id Git.Git --source winget
winget install --id OpenJS.NodeJS.LTS --source winget --version 24.18.0 --architecture x64  # arm64 on ARM64
pyenv install 3.12.10; pyenv local 3.12.10
# + Visual Studio 2022 C++ build tools (needed by node-gyp)

git clone https://github.com/microsoft/vscode.git
cd vscode
git checkout 1.132.0
npm install

# Timed workload
npm run compile
```

## Notes

- Requires PowerShell 7+. Only compile time is measured (no test phase).
- HOBL preserves `node_modules/` between runs and cleans `out/` and `.build/` each loop.
- Default: 1 loop. ARM64 uses Visual Studio Community (Build Tools is x64-only).
