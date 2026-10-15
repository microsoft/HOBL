# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [ValidateSet('true', 'false')][string]$UseAi = 'false',
    [ValidateSet('AC', 'DC')][string]$PowerSource = 'DC',
    [ValidateRange(0, 100)][int]$MinBatteryCharge = 90,
    [ValidateRange(10, 86400)][int]$SocwatchDuration = 1800,
    [ValidateRange(0, 86400)][int]$SocwatchDelay = 600,
    [ValidateRange(10, 86400)][int]$WprDurationPower = 300,
    [ValidateSet('true', 'false')][string]$SocwatchCfg = 'false',
    [ValidateSet('true', 'false')][string]$GroupByProcessName = 'false',
    [ValidateSet('true', 'false')][string]$ShowHiddenProcesses = 'false',
    [ValidateRange(0, 100)][int]$AllowLostEvents = 0,
    [ValidateRange(1, 10080)][int]$TimeoutMinutes = 105,
    [string]$logFile = ""
)

$ErrorActionPreference = 'Stop'
$scriptDrive = Split-Path -Qualifier $PSScriptRoot
$dataRoot = Join-Path $scriptDrive 'hobl_data'
$runId = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$artifactRoot = Join-Path $dataRoot "bldt_sw_hygiene\$runId"
$reportOutput = Join-Path $artifactRoot 'reports'
$stdoutFile = Join-Path $artifactRoot 'bldt_sw_hygiene_stdout.log'
$stderrFile = Join-Path $artifactRoot 'bldt_sw_hygiene_stderr.log'
$csvFile = Join-Path $dataRoot 'bldt_sw_hygiene_results.csv'
$jsonFile = Join-Path $dataRoot 'bldt_sw_hygiene_results.json'
$artifactCsvFile = Join-Path $artifactRoot 'bldt_sw_hygiene_results.csv'
$artifactJsonFile = Join-Path $artifactRoot 'bldt_sw_hygiene_results.json'
if (-not $logFile) { $logFile = Join-Path $artifactRoot 'bldt_sw_hygiene_run.log' }

New-Item -Path $dataRoot, $artifactRoot, $reportOutput -ItemType Directory -Force | Out-Null
Set-Content -LiteralPath $logFile -Value '-- BLDT Software Hygiene run started --' -Encoding UTF8

function log {
    param([Parameter(ValueFromPipeline = $true)][object]$Message)
    process {
        $text = [string]$Message
        Write-Host $text
        Add-Content -LiteralPath $logFile -Value $text -Encoding UTF8
    }
}

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

function Get-ReportSnapshot {
    param([string]$Root)

    $snapshot = @{}
    if (-not (Test-Path -LiteralPath $Root)) {
        return $snapshot
    }

    Get-ChildItem -LiteralPath $Root -File -Recurse | ForEach-Object {
        $snapshot[$_.FullName] = "$($_.Length):$($_.LastWriteTimeUtc.Ticks)"
    }
    return $snapshot
}

function Copy-ChangedReports {
    param(
        [string]$SourceRoot,
        [string]$DestinationRoot,
        [hashtable]$BeforeSnapshot
    )

    if (-not (Test-Path -LiteralPath $SourceRoot)) {
        return @()
    }

    $changedFiles = @(
        Get-ChildItem -LiteralPath $SourceRoot -File -Recurse |
            Where-Object {
                $signature = "$($_.Length):$($_.LastWriteTimeUtc.Ticks)"
                -not $BeforeSnapshot.ContainsKey($_.FullName) -or
                $BeforeSnapshot[$_.FullName] -ne $signature
            }
    )

    foreach ($file in $changedFiles) {
        $relativePath = $file.FullName.Substring($SourceRoot.Length).TrimStart('\')
        $destination = Join-Path $DestinationRoot $relativePath
        $destinationDirectory = Split-Path -Parent $destination
        New-Item -Path $destinationDirectory -ItemType Directory -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
    }

    return $changedFiles
}

. (Join-Path $PSScriptRoot 'bldt_common.ps1')

try {
    $requireAi = $UseAi -eq 'true'
    $installation = Assert-BldtInstallation -RequireAi:$requireAi
    "Using BLDT executable: $($installation.Executable)" | log
    "Using BLDT install root: $($installation.InstallRoot)" | log
    "Detected BLDT edition: $($installation.Edition)" | log
    "Detected BLDT version: $($installation.Version)" | log

    $bldtReportRoot = Join-Path $env:USERPROFILE 'Intel\BatteryLifeDiagnostic'
    $beforeSnapshot = Get-ReportSnapshot -Root $bldtReportRoot
    # v3.1.1's WPR utility consumes seconds despite the guide's millisecond label.
    "WPR collection: $WprDurationPower seconds." | log
    $parameterText = @(
        "min_battery_charge:$MinBatteryCharge"
        "socwatch_duration:$SocwatchDuration"
        "socwatch_delay:$SocwatchDelay"
        "socwatch_pwrsrc:$PowerSource"
        "wpr_duration_power:$WprDurationPower"
        "socwatch_cfg:$SocwatchCfg"
        "groupByProcessName:$GroupByProcessName"
        "showHiddenProcesses:$ShowHiddenProcesses"
        "allow_lost_events:$AllowLostEvents"
    ) -join ';'
    $arguments = @(
        '--type', 'SWHygiene',
        '--params', $parameterText,
        '--telemetry', 'false'
    )

    "Running BLDT Software Hygiene with parameters: $parameterText" | log
    $stopwatch = [Diagnostics.Stopwatch]::StartNew()
    try {
        $exitCode = Invoke-BldtProcess -FilePath $installation.Executable -ArgumentList $arguments `
            -StandardOutput $stdoutFile -StandardError $stderrFile -TimeoutSeconds ($TimeoutMinutes * 60) `
            -WorkingDirectory $installation.InstallRoot
    } finally {
        $stopwatch.Stop()
        $changedReports = @(
            Copy-ChangedReports -SourceRoot $bldtReportRoot -DestinationRoot $reportOutput `
                -BeforeSnapshot $beforeSnapshot
        )
    }
    $metrics = [pscustomobject][ordered]@{
        scenario_runtime = [math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
        bldt_exit_code = $exitCode
        bldt_version = $installation.Version
        bldt_edition = $installation.Edition
        power_source = $PowerSource
        min_battery_charge = $MinBatteryCharge
        socwatch_duration = $SocwatchDuration
        socwatch_delay = $SocwatchDelay
        wpr_duration_power = $WprDurationPower
        socwatch_cfg = $SocwatchCfg
        group_by_process_name = $GroupByProcessName
        show_hidden_processes = $ShowHiddenProcesses
        allow_lost_events = $AllowLostEvents
        report_file_count = $changedReports.Count
    }

    Write-MetricCsv -Metrics $metrics -Path $csvFile
    $metrics | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $jsonFile -Encoding UTF8
    Copy-Item -LiteralPath $csvFile -Destination $artifactCsvFile -Force
    Copy-Item -LiteralPath $jsonFile -Destination $artifactJsonFile -Force

    '--------------------------------------------------' | log
    'BLDT Software Hygiene metrics' | log
    $metrics.PSObject.Properties | ForEach-Object { "$($_.Name): $($_.Value)" | log }
    '--------------------------------------------------' | log

    if ($exitCode -ne 0) {
        throw "BLDT Software Hygiene exited with code $exitCode. Reports were preserved for diagnosis."
    }
    if ($changedReports.Count -eq 0) {
        throw "BLDT Software Hygiene completed without creating or updating report artifacts under $bldtReportRoot."
    }

    $jsonReports = @($changedReports | Where-Object Extension -eq '.json')
    $htmlReports = @($changedReports | Where-Object { $_.Extension -in ('.html', '.htm') })
    $zipReports = @($changedReports | Where-Object Extension -eq '.zip')
    if ($jsonReports.Count -eq 0 -or $htmlReports.Count -eq 0 -or $zipReports.Count -eq 0) {
        throw "BLDT Software Hygiene did not produce the expected JSON, HTML, and ZIP report set. JSON=$($jsonReports.Count), HTML=$($htmlReports.Count), ZIP=$($zipReports.Count)."
    }

    '-- BLDT Software Hygiene run completed successfully --' | log
    exit 0
} catch {
    " ERROR - BLDT Software Hygiene run failed: $($_.Exception.Message)" | log
    exit 1
}
