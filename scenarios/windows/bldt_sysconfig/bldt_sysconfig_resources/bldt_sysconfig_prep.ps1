# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = "",
    [ValidateSet('true', 'false')][string]$UseAi = 'false',
    [ValidateSet('true', 'false')][string]$ValidateOnly = 'false'
)

$ErrorActionPreference = 'Stop'
$scriptDrive = Split-Path -Qualifier $PSScriptRoot
$dataRoot = "$scriptDrive\hobl_data"
$binRoot = "$scriptDrive\hobl_bin"
$workRoot = Join-Path $binRoot 'bldt_resources'
$downloadRoot = Join-Path $workRoot 'downloads'
$packageRoot = Join-Path $workRoot 'packages'
if (-not $logFile) { $logFile = Join-Path $dataRoot 'bldt_sysconfig_prep.log' }

New-Item -Path $dataRoot, $binRoot, $workRoot, $downloadRoot, $packageRoot -ItemType Directory -Force | Out-Null
Set-Content -LiteralPath $logFile -Value '-- BLDT prep started --' -Encoding UTF8
. (Join-Path $PSScriptRoot 'bldt_common.ps1')

$requireAi = $UseAi -eq 'true'
$edition = if ($requireAi) { 'ai' } else { 'standard' }
try {
    Assert-BldtCompatibility
    try {
        Assert-BldtInstallation -RequireAi:$requireAi | Out-Null
        "Requested BLDT state is already valid; no installation is needed." | log
        exit 0
    } catch {
        if ($ValidateOnly -eq 'true') {
            throw
        }
        "BLDT prep is required: $($_.Exception.Message)" | log
    }

    if (-not (Test-BldtElevated)) {
        throw 'BLDT installation requires the elevated HOBL DUT execution context. Interactive elevation will not be attempted.'
    }

    $package = Get-BldtPackageDefinition -Edition $edition
    $zipPath = Join-Path $downloadRoot $package.ZipName
    Invoke-BldtDownload -Uri $package.Url -Destination $zipPath -Sha256 $package.ZipSha256

    $editionPackageRoot = Join-Path $packageRoot $package.Edition
    if (Test-Path -LiteralPath $editionPackageRoot) {
        Remove-Item -LiteralPath $editionPackageRoot -Recurse -Force
    }
    New-Item -Path $editionPackageRoot -ItemType Directory -Force | Out-Null
    "Extracting verified BLDT package to: $editionPackageRoot" | log
    Expand-Archive -LiteralPath $zipPath -DestinationPath $editionPackageRoot -Force

    $msiFiles = @(Get-ChildItem -LiteralPath $editionPackageRoot -Filter $package.MsiName -File -Recurse)
    if ($msiFiles.Count -ne 1) {
        throw "Expected exactly one '$($package.MsiName)' in the BLDT package, found $($msiFiles.Count)."
    }
    $msiPath = $msiFiles[0].FullName
    $installLog = Join-Path $dataRoot "bldt_$($package.Edition)_msi.log"
    Install-BldtMsi -Path $msiPath -Package $package -InstallLog $installLog

    Start-Sleep -Seconds 3
    Assert-BldtInstallation -RequireAi:$requireAi | Out-Null
    "-- BLDT prep completed successfully --" | log
    exit 0
} catch {
    " ERROR - BLDT prep failed: $($_.Exception.Message)" | log
    exit 1
}
