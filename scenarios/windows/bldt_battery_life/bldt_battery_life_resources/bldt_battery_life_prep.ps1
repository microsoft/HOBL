# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    # Python selects one operation each time it invokes this script.
    [Parameter(Mandatory = $true)]
    [ValidateSet('Install', 'Discover', 'Run', 'CopyReports')]
    [string]$Action,
    [string]$DataRoot = '',
    [int]$CollectionDurationSeconds = 600,
    [int]$TimeoutSeconds = 4800,
    [string]$StartedUtc = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Keep HOBL files on the script's drive when Python does not provide a path.
$scriptDrive = Split-Path -Qualifier $PSScriptRoot
if (-not $DataRoot) { $DataRoot = "$scriptDrive\hobl_data" }
$logFile = Join-Path $DataRoot 'bldt_battery_life_prep.log'

function log {
    param([string]$Message)
    Add-Content -LiteralPath $logFile -Value $Message -Encoding UTF8
}

function Get-BldtExecutable {
    # Read both Windows registry views so custom BLDT install locations work.
    $registryKeys = @(
        'HKLM:\SOFTWARE\Intel\Battery Life Diagnostic Tool',
        'HKLM:\SOFTWARE\WOW6432Node\Intel\Battery Life Diagnostic Tool'
    )

    foreach ($registryKey in $registryKeys) {
        if (-not (Test-Path -LiteralPath $registryKey)) { continue }
        $installPath = (Get-ItemProperty -LiteralPath $registryKey).Path
        if (-not $installPath) { continue }

        $executable = Join-Path $installPath 'BatteryLifeDiagnosticTool.exe'
        if (Test-Path -LiteralPath $executable -PathType Leaf) { return $executable }
    }

    return $null
}

function Install-Bldt {
    # Download Intel's standard BLDT package into a temporary working directory.
    $downloadUrl = 'https://downloadmirror.intel.com/925424/bldt_setup-v3.1.1.zip'
    $workDirectory = Join-Path $env:TEMP ("hobl_bldt_" + [guid]::NewGuid().ToString('N'))
    $archivePath = Join-Path $workDirectory 'bldt.zip'
    $extractPath = Join-Path $workDirectory 'extracted'
    $msiLog = Join-Path $DataRoot 'bldt_battery_life_install.log'

    New-Item -ItemType Directory -Path $DataRoot, $workDirectory -Force | Out-Null

    try {
        log "Downloading BLDT from $downloadUrl"
        Invoke-WebRequest -Uri $downloadUrl -OutFile $archivePath -UseBasicParsing -TimeoutSec 10800

        log "Extracting BLDT to $extractPath"
        Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath -Force

        $installers = @(Get-ChildItem -LiteralPath $extractPath -Filter '*.msi' -File -Recurse)
        if ($installers.Count -ne 1) { throw "Expected one BLDT MSI, found $($installers.Count)." }

        # Install BLDT silently and retain the native MSI log in HOBL's data directory.
        $installerPath = $installers[0].FullName
        $installerDirectory = Split-Path -Parent $installerPath
        $msiexec = Join-Path $env:SystemRoot 'System32\msiexec.exe'
        $arguments = "/i `"$installerPath`" /qn /norestart REBOOT=ReallySuppress INSTALLER_SOURCE_DIR=`"$installerDirectory`" /L*v `"$msiLog`""
        log "Installing BLDT from $installerPath"
        $process = Start-Process -FilePath $msiexec -ArgumentList $arguments -WorkingDirectory $installerDirectory -PassThru

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

        if ($exitCode -ne 0) { throw "BLDT installation failed with exit code $exitCode; see $msiLog." }
    } finally {
        if (Test-Path -LiteralPath $workDirectory) { Remove-Item -LiteralPath $workDirectory -Recurse -Force }
    }
}

function Invoke-BatteryLife {
    param([string]$Executable)

    # Run both Intel collection phases for the same user-selected duration.
    New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null
    $stdoutLog = Join-Path $DataRoot 'bldt_battery_life_stdout.log'
    $stderrLog = Join-Path $DataRoot 'bldt_battery_life_stderr.log'
    $workingDirectory = Split-Path -Parent $Executable
    $parameters = "min_battery_charge:0;socwatch_duration:$CollectionDurationSeconds;socwatch_delay:0;pwrsrc:DC;energy_rpt_duration:$CollectionDurationSeconds"
    $arguments = @('--type', 'batteryLife', '--params', $parameters, '--telemetry=false')
    $startedUtc = [DateTime]::UtcNow.ToString('o')
    $process = Start-Process -FilePath $Executable -ArgumentList $arguments -WorkingDirectory $workingDirectory -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru

    try {
        $null = $process.Handle
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            Stop-Process -Id $process.Id -Force
            throw "BLDT Battery Life timed out after $TimeoutSeconds seconds."
        }

        $process.WaitForExit()
        [pscustomobject]@{ started_utc = $startedUtc; exit_code = $process.ExitCode } | ConvertTo-Json -Compress
    } finally {
        $process.Dispose()
    }
}

function Copy-BldtReports {
    # Stage only Battery Life reports created by this run; include shared HTML assets.
    if (-not $StartedUtc) { throw 'BLDT report start time was not provided.' }

    $started = [DateTime]::Parse($StartedUtc).ToUniversalTime()
    $reportRoot = Join-Path $env:USERPROFILE 'Intel\BatteryLifeDiagnostic'
    $destination = Join-Path $DataRoot 'bldt_battery_life_reports'
    if (-not (Test-Path -LiteralPath $reportRoot -PathType Container)) { throw "BLDT report directory was not found: $reportRoot" }

    $reports = @(Get-ChildItem -LiteralPath $reportRoot -File -Recurse | Where-Object {
        $_.LastWriteTimeUtc -ge $started -and
        $_.BaseName -like 'BatteryLife_*' -and
        $_.Extension.ToLowerInvariant() -in '.html', '.htm', '.json', '.zip'
    })

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

    [pscustomobject]@{ reports = @($reports | ForEach-Object { $_.Name }) } | ConvertTo-Json -Compress
}

try {
    # Dispatch the operation requested by the Python scenario.
    New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null

    if ($Action -eq 'Install') {
        Install-Bldt
        exit 0
    }

    if ($Action -eq 'CopyReports') {
        Copy-BldtReports
        exit 0
    }

    $executable = Get-BldtExecutable

    if ($Action -eq 'Discover') {
        if (-not $executable) { throw 'BatteryLifeDiagnosticTool.exe was not found.' }
        Write-Output $executable
        exit 0
    }

    if (-not $executable) { throw 'BatteryLifeDiagnosticTool.exe was not found.' }
    Invoke-BatteryLife -Executable $executable
} catch {
    $message = " ERROR - $($_.Exception.Message)"
    Write-Output $message
    if (Test-Path -LiteralPath $DataRoot) { Add-Content -LiteralPath $logFile -Value $message -Encoding UTF8 -ErrorAction SilentlyContinue }
    exit 1
}
