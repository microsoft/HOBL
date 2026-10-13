# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = "",
    [ValidateSet('true', 'false')][string]$UseAi = 'false',
    [ValidateSet('AC', 'DC')][string]$PowerSource = 'AC',
    [ValidateRange(1, 1000)][int]$LoopNumber = 1,
    [ValidateRange(1, 120)][int]$TimeoutMinutes = 15
)

$ErrorActionPreference = 'Stop'
$scriptDrive = Split-Path -Qualifier $PSScriptRoot
$dataRoot = "$scriptDrive\hobl_data"
$reportRoot = Join-Path $env:USERPROFILE 'Intel\BatteryLifeDiagnostic'
$runId = "{0}_loop{1}" -f (Get-Date -Format 'yyyyMMdd_HHmmss'), $LoopNumber
$artifactRoot = Join-Path $dataRoot "bldt_sysconfig\$runId"
if (-not $logFile) { $logFile = Join-Path $artifactRoot 'bldt_sysconfig_run.log' }
$stdoutFile = Join-Path $artifactRoot 'bldt_stdout.log'
$stderrFile = Join-Path $artifactRoot 'bldt_stderr.log'
$resultsCsv = Join-Path $dataRoot 'bldt_sysconfig_results.csv'
$resultsJson = Join-Path $dataRoot 'bldt_sysconfig_results.json'
$artifactResultsCsv = Join-Path $artifactRoot 'bldt_sysconfig_results.csv'
$artifactResultsJson = Join-Path $artifactRoot 'bldt_sysconfig_results.json'

New-Item -Path $dataRoot, $artifactRoot -ItemType Directory -Force | Out-Null
Set-Content -LiteralPath $logFile -Value '-- BLDT SysConfig run started --' -Encoding UTF8
. (Join-Path $PSScriptRoot 'bldt_common.ps1')

function Write-MetricCsv {
    param([Parameter(Mandatory)][object]$Metrics, [Parameter(Mandatory)][string]$Path)
    $lines = foreach ($property in $Metrics.PSObject.Properties) {
        $value = [string]$property.Value
        if ($value -match '[,"\r\n]') {
            $value = '"' + $value.Replace('"', '""') + '"'
        }
        "$($property.Name),$value"
    }
    $lines | Set-Content -LiteralPath $Path -Encoding UTF8
}

try {
    $requireAi = $UseAi -eq 'true'
    $installation = Assert-BldtInstallation -RequireAi:$requireAi
    if (-not (Test-Path -LiteralPath $reportRoot)) {
        New-Item -Path $reportRoot -ItemType Directory -Force | Out-Null
    }

    $before = @{}
    foreach ($file in Get-ChildItem -LiteralPath $reportRoot -File -Recurse -ErrorAction SilentlyContinue) {
        $before[$file.FullName] = "$($file.Length):$($file.LastWriteTimeUtc.Ticks)"
    }

    $arguments = @(
        '--type', 'SysConfigChecks',
        '--params', "pwrsrc:$PowerSource",
        '--telemetry', 'false'
    )
    "Running: $($installation.Executable) $($arguments -join ' ')" | log
    $stopwatch = [Diagnostics.Stopwatch]::StartNew()
    $exitCode = Invoke-BldtProcess -FilePath $installation.Executable -ArgumentList $arguments `
        -StandardOutput $stdoutFile -StandardError $stderrFile -TimeoutSeconds ($TimeoutMinutes * 60) `
        -WorkingDirectory $installation.InstallRoot
    $stopwatch.Stop()
    "BLDT process exit code: $exitCode" | log

    $changedFiles = @(
        Get-ChildItem -LiteralPath $reportRoot -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object {
                $state = "$($_.Length):$($_.LastWriteTimeUtc.Ticks)"
                -not $before.ContainsKey($_.FullName) -or $before[$_.FullName] -ne $state
            }
    )
    foreach ($file in $changedFiles) {
        $relativePath = $file.FullName.Substring($reportRoot.Length).TrimStart('\')
        $destination = Join-Path (Join-Path $artifactRoot 'reports') $relativePath
        New-Item -Path (Split-Path -Parent $destination) -ItemType Directory -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
    }

    if ($exitCode -ne 0) {
        throw "BLDT SysConfigChecks failed with exit code $exitCode. See $stdoutFile and $stderrFile"
    }
    if ($changedFiles.Count -eq 0) {
        throw "BLDT completed without creating or updating report artifacts under $reportRoot."
    }

    $jsonReports = @($changedFiles | Where-Object Extension -eq '.json')
    $htmlReports = @($changedFiles | Where-Object { $_.Extension -in ('.html', '.htm') })
    $zipReports = @($changedFiles | Where-Object Extension -eq '.zip')
    if ($jsonReports.Count -eq 0 -or $htmlReports.Count -eq 0 -or $zipReports.Count -eq 0) {
        throw "BLDT did not produce the expected JSON, HTML, and ZIP report set. JSON=$($jsonReports.Count), HTML=$($htmlReports.Count), ZIP=$($zipReports.Count)."
    }

    $metrics = [pscustomobject]@{
        scenario_runtime = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
        bldt_version = $installation.Version
        bldt_edition = $installation.Edition
        power_source = $PowerSource
        json_report_created = 1
        html_report_created = 1
        zip_report_created = 1
        report_file_count = $changedFiles.Count
    }
    Write-MetricCsv -Metrics $metrics -Path $resultsCsv
    $metrics | ConvertTo-Json | Set-Content -LiteralPath $resultsJson -Encoding UTF8
    Copy-Item -LiteralPath $resultsCsv -Destination $artifactResultsCsv -Force
    Copy-Item -LiteralPath $resultsJson -Destination $artifactResultsJson -Force

    "" | log
    "========================================" | log
    "BLDT SysConfig Metrics Summary" | log
    "========================================" | log
    "Scenario Runtime: $($metrics.scenario_runtime)s" | log
    "BLDT Version:     $($metrics.bldt_version)" | log
    "BLDT Edition:     $($metrics.bldt_edition)" | log
    "Power Source:     $($metrics.power_source)" | log
    "Report Files:     $($metrics.report_file_count)" | log
    "========================================" | log
    "-- BLDT SysConfig run completed successfully --" | log
    exit 0
} catch {
    " ERROR - BLDT SysConfig run failed: $($_.Exception.Message)" | log
    exit 1
}
