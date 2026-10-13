param(
    [ValidateSet('true', 'false')][string]$UseAi = 'false',
    [ValidateSet('AC', 'DC')][string]$PowerSource = 'DC',
    [ValidateRange(0, 100)][int]$MinBatteryCharge = 90,
    [ValidateRange(10, 86400)][int]$SocwatchDuration = 600,
    [ValidateRange(0, 86400)][int]$SocwatchDelay = 300,
    [ValidateRange(1, 3600)][int]$EnergyRptDuration = 600,
    [ValidateRange(1, 10080)][int]$TimeoutMinutes = 85,
    [string]$logFile = ""
)

$ErrorActionPreference = 'Stop'
$scriptDrive = Split-Path -Qualifier $PSScriptRoot
$dataRoot = Join-Path $scriptDrive 'hobl_data'
$runId = Get-Date -Format 'yyyyMMdd_HHmmss'
$artifactRoot = Join-Path $dataRoot "bldt_battery_life\$runId"
$reportOutput = Join-Path $artifactRoot 'reports'
$stdoutFile = Join-Path $artifactRoot 'bldt_battery_life_stdout.log'
$stderrFile = Join-Path $artifactRoot 'bldt_battery_life_stderr.log'
$csvFile = Join-Path $dataRoot 'bldt_battery_life_results.csv'
$jsonFile = Join-Path $dataRoot 'bldt_battery_life_results.json'
$artifactCsvFile = Join-Path $artifactRoot 'bldt_battery_life_results.csv'
$artifactJsonFile = Join-Path $artifactRoot 'bldt_battery_life_results.json'
if (-not $logFile) { $logFile = Join-Path $artifactRoot 'bldt_battery_life_run.log' }

New-Item -Path $dataRoot, $artifactRoot, $reportOutput -ItemType Directory -Force | Out-Null
Set-Content -LiteralPath $logFile -Value '-- BLDT Battery Life run started --' -Encoding UTF8

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

    Get-ChildItem -LiteralPath $Root -File -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
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
        Get-ChildItem -LiteralPath $SourceRoot -File -Recurse -ErrorAction SilentlyContinue |
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
    $parameterText = @(
        "min_battery_charge:$MinBatteryCharge"
        "socwatch_duration:$SocwatchDuration"
        "socwatch_delay:$SocwatchDelay"
        "pwrsrc:$PowerSource"
        "energy_rpt_duration:$EnergyRptDuration"
    ) -join ';'
    $arguments = @(
        '--type', 'batteryLife',
        '--params', $parameterText,
        '--telemetry', 'false'
    )

    "Running BLDT Battery Life with parameters: $parameterText" | log
    $stopwatch = [Diagnostics.Stopwatch]::StartNew()
    $exitCode = Invoke-BldtProcess -FilePath $installation.Executable -ArgumentList $arguments `
        -StandardOutput $stdoutFile -StandardError $stderrFile -TimeoutSeconds ($TimeoutMinutes * 60) `
        -WorkingDirectory $installation.InstallRoot
    $stopwatch.Stop()

    Start-Sleep -Seconds 2
    $changedReports = @(
        Copy-ChangedReports -SourceRoot $bldtReportRoot -DestinationRoot $reportOutput `
            -BeforeSnapshot $beforeSnapshot
    )
    $metrics = [pscustomobject][ordered]@{
        scenario_runtime = [math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
        bldt_exit_code = $exitCode
        bldt_version = $installation.Version
        bldt_edition = $installation.Edition
        power_source = $PowerSource
        min_battery_charge = $MinBatteryCharge
        socwatch_duration = $SocwatchDuration
        socwatch_delay = $SocwatchDelay
        energy_rpt_duration = $EnergyRptDuration
        report_file_count = $changedReports.Count
    }

    Write-MetricCsv -Metrics $metrics -Path $csvFile
    $metrics | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $jsonFile -Encoding UTF8
    Copy-Item -LiteralPath $csvFile -Destination $artifactCsvFile -Force
    Copy-Item -LiteralPath $jsonFile -Destination $artifactJsonFile -Force

    '--------------------------------------------------' | log
    'BLDT Battery Life metrics' | log
    $metrics.PSObject.Properties | ForEach-Object { "$($_.Name): $($_.Value)" | log }
    '--------------------------------------------------' | log

    if ($exitCode -ne 0) {
        throw "BLDT Battery Life exited with code $exitCode. Reports were preserved for diagnosis."
    }
    if ($changedReports.Count -eq 0) {
        throw "BLDT Battery Life completed without creating or updating report artifacts under $bldtReportRoot."
    }

    $jsonReports = @($changedReports | Where-Object Extension -eq '.json')
    $htmlReports = @($changedReports | Where-Object { $_.Extension -in ('.html', '.htm') })
    $zipReports = @($changedReports | Where-Object Extension -eq '.zip')
    if ($jsonReports.Count -eq 0 -or $htmlReports.Count -eq 0 -or $zipReports.Count -eq 0) {
        throw "BLDT Battery Life did not produce the expected JSON, HTML, and ZIP report set. JSON=$($jsonReports.Count), HTML=$($htmlReports.Count), ZIP=$($zipReports.Count)."
    }

    '-- BLDT Battery Life run completed successfully --' | log
    exit 0
} catch {
    " ERROR - BLDT Battery Life run failed: $($_.Exception.Message)" | log
    exit 1
}
