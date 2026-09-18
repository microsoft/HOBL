# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Keep Node private to this scenario: other workloads may require Node 24 LTS.
# Called after PATH refreshes in both prep and run, before any npm invocation.
function Enable-VscodeNode {
    param(
        [switch]$Install,
        [string]$RuntimeRoot = (Join-Path $PSScriptRoot "nodejs")
    )

    $nodeVersion = "26.9.0"
    $nodeArch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
    # Published at https://nodejs.org/dist/v26.9.0/SHASUMS256.txt
    $checksums = @{
        x64 = "c8af870b5b3e9789a6cbdb30270e7c212e12d76a7afa7fc7f21b6b21cc22a71b"
        arm64 = "b70e4557d1b3829e45c0afc19ac9376ccbd4a8661235377ffce90b39fc7227ba"
    }
    if (-not $checksums.ContainsKey($nodeArch)) {
        throw "Unsupported Node.js architecture: $nodeArch"
    }

    $archiveName = "node-v$nodeVersion-win-$nodeArch"
    $nodeDir = Join-Path $RuntimeRoot $archiveName
    $nodeExe = Join-Path $nodeDir "node.exe"
    $npmCmd = Join-Path $nodeDir "npm.cmd"

    if ($Install -and -not (Test-Path $nodeExe)) {
        $archivePath = Join-Path ([System.IO.Path]::GetTempPath()) ("hobl-vscode-node-" + [guid]::NewGuid() + ".zip")
        try {
            "-- Downloading scenario-local Node.js $nodeVersion ($nodeArch)" | log
            Invoke-WebRequest -Uri "https://nodejs.org/dist/v$nodeVersion/$archiveName.zip" -OutFile $archivePath -ErrorAction Stop
            if ((Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash -ne $checksums[$nodeArch]) {
                throw "Node.js $nodeVersion archive checksum mismatch"
            }
            Expand-Archive -LiteralPath $archivePath -DestinationPath $RuntimeRoot -Force -ErrorAction Stop
        } finally {
            Remove-Item -LiteralPath $archivePath -Force -ErrorAction SilentlyContinue
        }
    }

    if (-not (Test-Path $nodeExe) -or -not (Test-Path $npmCmd)) {
        throw "Scenario-local Node.js is missing at $nodeDir. Re-run VS Code prep."
    }
    $actualVersion = & $nodeExe --version
    if ($LASTEXITCODE -ne 0 -or $actualVersion -ne "v$nodeVersion") {
        throw "Node.js version is '$actualVersion', expected v$nodeVersion. Re-run VS Code prep."
    }
    $actualArch = & $nodeExe -p process.arch
    if ($LASTEXITCODE -ne 0 -or $actualArch -ne $nodeArch) {
        throw "Node.js architecture is '$actualArch', expected $nodeArch. Re-run VS Code prep."
    }

    $env:PATH = "$nodeDir;$env:PATH"
    "Using scenario-local Node.js $actualVersion ($actualArch): $nodeExe" | log
    $npmVersion = & $npmCmd --version
    if ($LASTEXITCODE -ne 0) {
        throw "Scenario-local npm failed. Re-run VS Code prep."
    }
    "Using bundled npm $npmVersion" | log
}