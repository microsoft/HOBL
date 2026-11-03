# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Install', 'Discover', 'RunHygiene', 'RunAi', 'CopyReports')]
    [string]$Action,
    [string]$DataRoot = '',
    [switch]$RequireAi,
    [int]$CollectionDurationSeconds = 600,
    [int]$TimeoutSeconds = 1500,
    [string]$StartedUtc = '',
    [ValidateSet('SWHygiene', 'AIAnalysis')]
    [string]$ReportKind = 'SWHygiene',
    [string]$InputFile = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$scriptDrive = Split-Path -Qualifier $PSScriptRoot
if (-not $DataRoot) { $DataRoot = "$scriptDrive\hobl_data" }
$logFile = Join-Path $DataRoot 'bldt_sw_hygiene_prep.log'

function log {
    param([string]$Message)
    Add-Content -LiteralPath $logFile -Value $Message -Encoding UTF8
}

function Get-BldtInstallation {
    param([switch]$RequireAi)

    $registryKeys = @(
        'HKLM:\SOFTWARE\Intel\Battery Life Diagnostic Tool',
        'HKLM:\SOFTWARE\WOW6432Node\Intel\Battery Life Diagnostic Tool'
    )

    foreach ($registryKey in $registryKeys) {
        if (-not (Test-Path -LiteralPath $registryKey)) { continue }
        $installPath = (Get-ItemProperty -LiteralPath $registryKey).Path
        if (-not $installPath) { continue }

        $executable = Join-Path $installPath 'BatteryLifeDiagnosticTool.exe'
        if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) { continue }

        $version = (Get-Item -LiteralPath $executable).VersionInfo.ProductVersion
        $hasAiPayloads = $true
        foreach ($payloadName in 'AIAnalyzer.tar.gz', 'AIAnalyzerModels.tar.gz') {
            $payload = Join-Path $installPath "src\$payloadName"
            if (-not (Test-Path -LiteralPath $payload -PathType Leaf)) {
                $hasAiPayloads = $false
            }
        }

        if ($RequireAi -and -not $hasAiPayloads) { continue }

        return [pscustomobject]@{
            executable = $executable
            version = $version
            edition = if ($hasAiPayloads) { 'ai' } else { 'standard' }
        }
    }

    return $null
}

function Install-Bldt {
    param([ValidateSet('standard', 'ai')][string]$Edition)

    $stem = if ($Edition -eq 'ai') {
        'bldt-ai_setup-v3.1.1'
    } else {
        'bldt_setup-v3.1.1'
    }
    $downloadUrl = "https://downloadmirror.intel.com/925424/$stem.zip"
    $workDirectory = Join-Path $env:TEMP ("hobl_bldt_" + [guid]::NewGuid().ToString('N'))
    $archivePath = Join-Path $workDirectory 'bldt.zip'
    $extractPath = Join-Path $workDirectory 'extracted'
    $msiLog = Join-Path $DataRoot "bldt_sw_hygiene_$Edition.install.log"

    New-Item -ItemType Directory -Path $DataRoot, $workDirectory -Force | Out-Null

    try {
        log "Downloading BLDT $Edition edition from $downloadUrl"
        Invoke-WebRequest -Uri $downloadUrl -OutFile $archivePath -UseBasicParsing -TimeoutSec 10800

        log "Extracting BLDT to $extractPath"
        Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath -Force

        $installers = @(
            Get-ChildItem -LiteralPath $extractPath -Filter "$stem.msi" -File -Recurse
        )
        if ($installers.Count -ne 1) {
            throw "Expected one BLDT $Edition MSI, found $($installers.Count)."
        }

        $installerPath = $installers[0].FullName
        $installerDirectory = Split-Path -Parent $installerPath

        if ($Edition -eq 'ai') {
            foreach ($payloadName in 'AIAnalyzer.tar.gz', 'AIAnalyzerModels.tar.gz') {
                $payload = Join-Path $installerDirectory "src\$payloadName"
                if (-not (Test-Path -LiteralPath $payload -PathType Leaf)) {
                    throw "BLDT AI installer payload was not found: $payload"
                }
            }
        }

        $msiexec = Join-Path $env:SystemRoot 'System32\msiexec.exe'
        if (-not (Test-Path -LiteralPath $msiexec -PathType Leaf)) {
            throw "Windows Installer was not found: $msiexec"
        }

        $arguments = "/i `"$installerPath`" /qn /norestart REBOOT=ReallySuppress " +
            "INSTALLER_SOURCE_DIR=`"$installerDirectory`" WIXUI_EXITDIALOGOPTIONALCHECKBOX=0 " +
            "/L*v `"$msiLog`""
        log "Installing BLDT $Edition from $installerPath"
        $process = Start-Process -FilePath $msiexec -ArgumentList $arguments `
            -WorkingDirectory $installerDirectory -PassThru

        try {
            if (-not $process.WaitForExit(10800000)) {
                Stop-Process -Id $process.Id -Force
                throw 'BLDT installation timed out after 10800 seconds.'
            }
            $process.WaitForExit()
            $exitCode = $process.ExitCode
        } finally {
            $process.Dispose()
        }

        if ($exitCode -in 1641, 3010) {
            throw 'BLDT installation requires a DUT reboot; reboot and rerun prep.'
        }
        if ($exitCode -ne 0) {
            throw "BLDT installation failed with exit code $exitCode; see $msiLog."
        }
    } finally {
        if (Test-Path -LiteralPath $workDirectory) {
            Remove-Item -LiteralPath $workDirectory -Recurse -Force
        }
    }
}

function Install-RequiredBldt {
    $installation = Get-BldtInstallation -RequireAi:$RequireAi
    $requiredEdition = if ($RequireAi) { 'ai' } else { 'standard' }

    if ($null -ne $installation) {
        log "Using existing BLDT $($installation.edition) edition at $($installation.executable)"
        return
    }

    Install-Bldt -Edition $requiredEdition
    $installation = Get-BldtInstallation -RequireAi:$RequireAi
    if ($null -eq $installation) {
        throw 'BatteryLifeDiagnosticTool.exe was not found after installation.'
    }
}

function Find-BldtExecutable {
    $installation = Get-BldtInstallation -RequireAi:$RequireAi
    if ($null -eq $installation) {
        if ($RequireAi) {
            throw 'The BLDT AI edition and its model payloads were not found.'
        }
        throw 'BatteryLifeDiagnosticTool.exe was not found.'
    }
    $installation.executable
}

function Invoke-Bldt {
    param(
        [string]$Executable,
        [string[]]$Arguments,
        [string]$LogPrefix
    )

    New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null
    $stdoutLog = Join-Path $DataRoot "$LogPrefix.stdout.log"
    $stderrLog = Join-Path $DataRoot "$LogPrefix.stderr.log"
    $startedUtc = [DateTime]::UtcNow.ToString('o')
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments `
        -WorkingDirectory (Split-Path -Parent $Executable) `
        -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru

    try {
        $null = $process.Handle
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            Stop-Process -Id $process.Id -Force
            throw "BLDT timed out after $TimeoutSeconds seconds."
        }

        $process.WaitForExit()
        $timer.Stop()
        [pscustomobject]@{
            started_utc = $startedUtc
            exit_code = $process.ExitCode
            seconds = [math]::Round($timer.Elapsed.TotalSeconds, 3)
        } | ConvertTo-Json -Compress
    } finally {
        $process.Dispose()
    }
}

function Invoke-SoftwareHygiene {
    param([string]$Executable)

    $parameters = (
        "min_battery_charge:0;" +
        "socwatch_duration:$CollectionDurationSeconds;" +
        "socwatch_delay:0;" +
        "socwatch_pwrsrc:DC;" +
        "wpr_duration_power:$CollectionDurationSeconds;" +
        "socwatch_cfg:false;groupByProcessName:false;" +
        "showHiddenProcesses:false;allow_lost_events:0"
    )
    $arguments = @(
        '--type', 'SWHygiene',
        '--params', $parameters,
        '--telemetry=false'
    )
    Invoke-Bldt -Executable $Executable -Arguments $arguments `
        -LogPrefix 'bldt_sw_hygiene'
}

function Invoke-AiAnalysis {
    param([string]$Executable)

    if (-not $InputFile) { throw 'Software Hygiene input filename was not provided.' }

    $reportRoot = Join-Path $env:USERPROFILE 'Intel\BatteryLifeDiagnostic'
    $source = Join-Path $reportRoot $InputFile
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Software Hygiene input report was not found: $source"
    }

    $arguments = @(
        '--type', 'AIAnalysis',
        '--params', "inputFile:$InputFile;region:global",
        '--telemetry=false'
    )
    Invoke-Bldt -Executable $Executable -Arguments $arguments `
        -LogPrefix 'bldt_sw_hygiene_ai'
}

function Copy-BldtReports {
    if (-not $StartedUtc) { throw 'BLDT report start time was not provided.' }

    $started = [DateTime]::Parse($StartedUtc).ToUniversalTime()
    $reportRoot = Join-Path $env:USERPROFILE 'Intel\BatteryLifeDiagnostic'
    $destination = Join-Path $DataRoot 'bldt_sw_hygiene_reports'
    if (-not (Test-Path -LiteralPath $reportRoot -PathType Container)) {
        throw "BLDT report directory was not found: $reportRoot"
    }

    if ($ReportKind -eq 'AIAnalysis') {
        $reports = @(
            Get-ChildItem -LiteralPath $reportRoot -File -Recurse | Where-Object {
                $_.LastWriteTimeUtc -ge $started -and
                $_.BaseName -like 'SWHygiene_*.AIAnalysis' -and
                $_.Extension.ToLowerInvariant() -in '.html', '.htm', '.json', '.zip'
            }
        )
    } else {
        $reports = @(
            Get-ChildItem -LiteralPath $reportRoot -File -Recurse | Where-Object {
                $_.LastWriteTimeUtc -ge $started -and
                $_.BaseName -like 'SWHygiene_*' -and
                $_.BaseName -notlike '*.AIAnalysis' -and
                $_.Extension.ToLowerInvariant() -in '.html', '.htm', '.json', '.zip'
            }
        )
    }

    foreach ($report in $reports) {
        $relativePath = $report.FullName.Substring($reportRoot.Length).TrimStart('\')
        $target = Join-Path $destination $relativePath
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $report.FullName -Destination $target -Force
    }

    $assets = Join-Path $reportRoot 'Assets'
    if (Test-Path -LiteralPath $assets -PathType Container) {
        Copy-Item -LiteralPath $assets -Destination $destination -Recurse -Force
    }

    $sourceJson = $null
    if ($ReportKind -eq 'SWHygiene') {
        $sourceJson = @(
            $reports | Where-Object { $_.Extension -eq '.json' } |
                Sort-Object LastWriteTimeUtc -Descending
        ) | Select-Object -First 1 -ExpandProperty Name
    }

    [pscustomobject]@{
        reports = @($reports | ForEach-Object { $_.Name })
        source_json = $sourceJson
    } | ConvertTo-Json -Compress
}

try {
    New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null

    if ($Action -eq 'Install') {
        Install-RequiredBldt
        exit 0
    }
    if ($Action -eq 'Discover') {
        Find-BldtExecutable
        exit 0
    }
    if ($Action -eq 'CopyReports') {
        Copy-BldtReports
        exit 0
    }

    $installation = Get-BldtInstallation -RequireAi:($Action -eq 'RunAi')
    if ($null -eq $installation) {
        throw 'BatteryLifeDiagnosticTool.exe was not found.'
    }

    if ($Action -eq 'RunHygiene') {
        Invoke-SoftwareHygiene -Executable $installation.executable
    } elseif ($Action -eq 'RunAi') {
        Invoke-AiAnalysis -Executable $installation.executable
    }
} catch {
    $message = " ERROR - $($_.Exception.Message)"
    Write-Output $message
    if (Test-Path -LiteralPath $DataRoot) {
        Add-Content -LiteralPath $logFile -Value $message -Encoding UTF8 `
            -ErrorAction SilentlyContinue
    }
    exit 1
}
