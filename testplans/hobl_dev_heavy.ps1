# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root.
[CmdletBinding()]
param(
    [Parameter(Mandatory, Position = 0)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string]$Profile,
    [ValidateSet('Windows', 'MacOS')]
    [string]$Platform = 'Windows'
)
$ErrorActionPreference = 'Stop'
$profilePath = (Resolve-Path -LiteralPath $Profile).ProviderPath
$hobl = Join-Path $PSScriptRoot '..\hobl.cmd'
$scenarios = @(
    'fast_api',
    'foundrylocal',
    'llvm',
    'mlperf',
    'net_aspire',
    'nodejs',
    'ollama',
    'opencv_build',
    'pytorch_inf',
    'spring_petclinic',
    'vscode',
    'rust_analyzer_build',
    'nushell_build'
)

foreach ($name in $scenarios) {
    $scenario = if ($Platform -eq 'MacOS') { "mac_$name" } else { $name }
    & $hobl -p $profilePath -s $scenario
    if ($LASTEXITCODE -ne 0) {
        throw " ERROR - Developer workload $scenario failed with exit code $LASTEXITCODE."
    }
}
