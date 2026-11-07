# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Windows helper for the Python scenario: install, locate, run, or collect BLDT.
# Despite the "prep" filename, this script also runs the assessment.
# param declares inputs; $ names a variable, and ValidateSet limits allowed values.
param(
    # Python selects one operation each time it invokes this script.
    [Parameter(Mandatory = $true)]
    [ValidateSet('Install', 'Discover', 'Run', 'CopyReports')]
    [string]$Action,
    [string]$DataRoot = '',
    [int]$CollectionDurationSeconds = 600,
    [int]$EnergyReportDurationSeconds = 600,
    [ValidateSet('AC', 'DC')]
    [string]$PowerSource = 'DC',
    [string]$StartedUtc = ''
)

# Send PowerShell errors to the catch block; hide progress bars in unattended runs.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Keep HOBL files on the script's drive when Python does not provide a path.
$scriptDrive = Split-Path -Qualifier $PSScriptRoot
if (-not $DataRoot) { $DataRoot = "$scriptDrive\hobl_data" }

$reportDirectory = Join-Path $DataRoot 'bldt_battery_life_reports'
$logFile = Join-Path $reportDirectory 'bldt_battery_life_prep.log'

# Keep diagnostic messages in a file so they do not mix with results sent to Python.
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

    # Skip missing registry entries and accept only an executable that exists.
    foreach ($registryKey in $registryKeys) {
        if (-not (Test-Path -LiteralPath $registryKey)) { continue }
        $installPath = (Get-ItemProperty -LiteralPath $registryKey).Path
        if (-not $installPath) { continue }

        $executable = Join-Path $installPath 'BatteryLifeDiagnosticTool.exe'
        if (Test-Path -LiteralPath $executable -PathType Leaf) { return $executable }
    }

    return $null
}

# Download and Install BLDT if it does not already exist
function Install-Bldt {
    $executable = Get-BldtExecutable
    if ($executable) {
        log "BLDT already installed at: $executable"
        return
    }

    # Download Intel's standard BLDT package into a temporary working directory.
    $downloadUrl = 'https://downloadmirror.intel.com/925424/bldt_setup-v3.1.1.zip'
    $workDirectory = Join-Path $env:TEMP ("hobl_bldt_" + [guid]::NewGuid().ToString('N'))
    $archivePath = Join-Path $workDirectory 'bldt.zip'
    $extractPath = Join-Path $workDirectory 'extracted'
    $msiLog = Join-Path $reportDirectory 'bldt_battery_life_install.log'

    # Use a unique temporary folder; Out-Null discards directory-creation output.
    New-Item -ItemType Directory -Path $reportDirectory, $workDirectory -Force | Out-Null

    try {
        log "Downloading BLDT from $downloadUrl"
        Invoke-WebRequest -Uri $downloadUrl -OutFile $archivePath -UseBasicParsing -TimeoutSec 10800

        log "Extracting BLDT to $extractPath"
        Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath -Force

        # Require exactly one installer rather than guessing which MSI to launch.
        $installers = @(Get-ChildItem -LiteralPath $extractPath -Filter '*.msi' -File -Recurse)
        if ($installers.Count -ne 1) { throw "Expected one BLDT MSI, found $($installers.Count)." }

        # Install BLDT silently and retain the native MSI log in HOBL's data directory.
        $installerPath = $installers[0].FullName
        $installerDirectory = Split-Path -Parent $installerPath
        $msiexec = Join-Path $env:SystemRoot 'System32\msiexec.exe'

        # /qn hides installer UI; /norestart suppresses auto reboot; /L*v writes detailed installer logs.
        $arguments = "/i `"$installerPath`" /qn /norestart REBOOT=ReallySuppress INSTALLER_SOURCE_DIR=`"$installerDirectory`" /L*v `"$msiLog`""
        log "Installing BLDT from $installerPath"
        $process = Start-Process -FilePath $msiexec -ArgumentList $arguments -WorkingDirectory $installerDirectory -PassThru

        # WaitForExit takes milliseconds; stop this installer after one hour.
        try {
            if (-not $process.WaitForExit(3600000)) {
                Stop-Process -Id $process.Id -Force
                throw 'BLDT installation timed out after 3600 seconds.'
            }
            $process.WaitForExit()
            $exitCode = $process.ExitCode
        } finally {
            # Release the process object's resources on success or failure.
            $process.Dispose()
        }

        if ($exitCode -ne 0) { throw "BLDT installation failed with exit code $exitCode; see $msiLog." }
    } finally {
        # Remove only this download's temporary files, leaving BLDT installed.
        if (Test-Path -LiteralPath $workDirectory) { Remove-Item -LiteralPath $workDirectory -Recurse -Force }
    }
}

# Run the Battery Life assessment using the installed BLDT executable
function Invoke-BatteryLife {
    param([string]$Executable)

    # Run Intel collection phases for their independently selected durations.
    New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
    $stdoutLog = Join-Path $reportDirectory 'bldt_battery_life_stdout.log'
    $stderrLog = Join-Path $reportDirectory 'bldt_battery_life_stderr.log'
    $workingDirectory = Split-Path -Parent $Executable

    # pwrsrc describes the detected power source; it does not switch a charger.
    $parameters = "min_battery_charge:0;socwatch_duration:$CollectionDurationSeconds;socwatch_delay:0;pwrsrc:$PowerSource;energy_rpt_duration:$EnergyReportDurationSeconds"
    $arguments = @('--type', 'batteryLife', '--params', $parameters, '--telemetry=false')

    # UTC timestamps identify fresh reports
    $startedUtc = [DateTime]::UtcNow.ToString('o')
    # Save normal/error output separately; PassThru returns the process for monitoring.
    $process = Start-Process -FilePath $Executable -ArgumentList $arguments -WorkingDirectory $workingDirectory -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru

    try {
        $null = $process.Handle
        $process.WaitForExit()

        # Return a result record for Python, including start time and exit code
        [pscustomobject]@{
            started_utc = $startedUtc
            exit_code = $process.ExitCode
        } | ConvertTo-Json -Compress
    } finally {
        $process.Dispose()
    }
}

# Gather the reports generated by BLDT for this run
function Copy-BldtReports {
    # Stage only Battery Life reports created by this run; include shared HTML assets.
    if (-not $StartedUtc) { throw 'BLDT report start time was not provided.' }

    $started = [DateTime]::Parse($StartedUtc).ToUniversalTime()
    $reportRoot = Join-Path $env:USERPROFILE 'Intel\BatteryLifeDiagnostic'
    $destination = $reportDirectory
    if (-not (Test-Path -LiteralPath $reportRoot -PathType Container)) { throw "BLDT report directory was not found: $reportRoot" }

    # Filter by both the workload name and timestamp to avoid collecting older runs.
    $reports = @(Get-ChildItem -LiteralPath $reportRoot -File -Recurse | Where-Object {
        $_.LastWriteTimeUtc -ge $started -and
        $_.BaseName -like 'BatteryLife_*' -and
        $_.Extension.ToLowerInvariant() -in '.html', '.htm', '.json', '.zip'
    })

    # Preserve subfolders while staging reports for HOBL's later retrieval.
    foreach ($report in $reports) {
        $relativePath = $report.FullName.Substring($reportRoot.Length).TrimStart('\')
        $target = Join-Path $destination $relativePath
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $report.FullName -Destination $target -Force
    }

    # Copy shared styles/images so the staged HTML reports remain readable.
    $assets = Join-Path $reportRoot 'Assets'
    if (Test-Path -LiteralPath $assets -PathType Container) {
        Copy-Item -LiteralPath $assets -Destination $destination -Recurse -Force
    }

    [pscustomobject]@{ reports = @($reports | ForEach-Object { $_.Name }) } | ConvertTo-Json -Compress
}

# This try-catch block handles the requested action and reports errors to Python.
try {
    # Dispatch one operation requested by Python; -eq means "equals".
    New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null

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
    # Report the exception and signal script failure (exit 1) to Python.
    $message = " ERROR - $($_.Exception.Message)"
    Write-Output $message
    if (Test-Path -LiteralPath $reportDirectory -PathType Container) {Add-Content -LiteralPath $logFile -Value $message -Encoding UTF8 -ErrorAction SilentlyContinue}
    exit 1
}
