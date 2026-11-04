# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Windows helper for the Python scenario: install, locate, run, or collect BLDT.
# Despite the "prep" filename, this script also runs the sleep assessment.
# param declares inputs; $ names a variable, and ValidateSet limits allowed values.
param(
    # Python selects one operation each time it invokes this script.
    [Parameter(Mandatory = $true)]
    [ValidateSet('Install', 'Discover', 'Run', 'CopyReports')]
    [string]$Action,
    [string]$DataRoot = '',
    # Sleep Study's history window in days, not how long the DUT should sleep.
    [int]$SleepStudyDays = 1,
    [int]$TimeoutSeconds = 2400,
    [string]$StartedUtc = ''
)

# Send PowerShell errors to the catch block; hide progress bars in unattended runs.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Keep HOBL files on the script's drive when Python does not provide a path.
$scriptDrive = Split-Path -Qualifier $PSScriptRoot
if (-not $DataRoot) { $DataRoot = "$scriptDrive\hobl_data" }
$logFile = Join-Path $DataRoot 'bldt_modern_standby_prep.log'

# Keep diagnostic messages out of the structured results sent back to Python.
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

function Install-Bldt {
    # Download Intel's standard BLDT package into a temporary working directory.
    $downloadUrl = 'https://downloadmirror.intel.com/925424/bldt_setup-v3.1.1.zip'
    $workDirectory = Join-Path $env:TEMP ("hobl_bldt_" + [guid]::NewGuid().ToString('N'))
    $archivePath = Join-Path $workDirectory 'bldt.zip'
    $extractPath = Join-Path $workDirectory 'extracted'
    $msiLog = Join-Path $DataRoot 'bldt_modern_standby_install.log'

    # Use a unique temporary folder; Out-Null discards directory-creation output.
    New-Item -ItemType Directory -Path $DataRoot, $workDirectory -Force | Out-Null

    try {
        log "Downloading BLDT from $downloadUrl"
        Invoke-WebRequest -Uri $downloadUrl -OutFile $archivePath -UseBasicParsing -TimeoutSec 10800

        log "Extracting BLDT to $extractPath"
        Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath -Force

        # Require exactly one installer rather than guessing which MSI to launch.
        $installers = @(Get-ChildItem -LiteralPath $extractPath -Filter '*.msi' -File -Recurse)
        if ($installers.Count -ne 1) {
            throw "Expected one BLDT MSI, found $($installers.Count)."
        }

        # Install BLDT silently and retain the native MSI log in HOBL's data directory.
        $installerPath = $installers[0].FullName
        $installerDirectory = Split-Path -Parent $installerPath
        $msiexec = Join-Path $env:SystemRoot 'System32\msiexec.exe'
        # /qn hides installer UI; /norestart suppresses reboot; /L*v saves detailed logs.
        # Escaped quotes preserve paths containing spaces.
        $arguments = "/i `"$installerPath`" /qn /norestart REBOOT=ReallySuppress " +
            "INSTALLER_SOURCE_DIR=`"$installerDirectory`" /L*v `"$msiLog`""
        log "Installing BLDT from $installerPath"
        $process = Start-Process -FilePath $msiexec -ArgumentList $arguments `
            -WorkingDirectory $installerDirectory -PassThru

        # WaitForExit takes milliseconds; stop this installer after three hours.
        try {
            if (-not $process.WaitForExit(10800000)) {
                Stop-Process -Id $process.Id -Force
                throw 'BLDT installation timed out after 10800 seconds.'
            }
            $process.WaitForExit()
            $exitCode = $process.ExitCode
        } finally {
            # Release the process object's resources on success or failure.
            $process.Dispose()
        }

        if ($exitCode -ne 0) {
            throw "BLDT installation failed with exit code $exitCode; see $msiLog."
        }
    } finally {
        # Remove only this download's temporary files, leaving BLDT installed.
        if (Test-Path -LiteralPath $workDirectory) {
            Remove-Item -LiteralPath $workDirectory -Recurse -Force
        }
    }
}

function Invoke-ModernStandby {
    param([string]$Executable)

    New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null
    $stdoutLog = Join-Path $DataRoot 'bldt_modern_standby_stdout.log'
    $stderrLog = Join-Path $DataRoot 'bldt_modern_standby_stderr.log'
    $eventsLog = Join-Path $DataRoot 'bldt_modern_standby_events.json'
    $workingDirectory = Split-Path -Parent $Executable
    # Intel's mosTest initiates sleep. The host-side Python scenario schedules the
    # external wake pulse, so waking does not depend on this sleeping DUT's script.
    # sleep_pwrsrc requests DC assessment; it does not disconnect the charger.
    $parameters = "min_battery_charge:0;sleep_study_days:$SleepStudyDays;enable_sleep:true;sleep_pwrsrc:DC"
    $arguments = @('--type', 'mosTest', '--params', $parameters, '--telemetry=false')
    # Save UTC boundaries for event/report filtering and time native BLDT execution.
    $started = [DateTime]::UtcNow
    $startedUtc = $started.ToString('o')
    $timer = [Diagnostics.Stopwatch]::StartNew()
    # Save normal/error output to files; PassThru returns the process to monitor.
    $process = Start-Process -FilePath $Executable -ArgumentList $arguments `
        -WorkingDirectory $workingDirectory -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog -PassThru

    try {
        $null = $process.Handle
        # Convert the timeout to milliseconds; stop BLDT if it does not finish in time.
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            Stop-Process -Id $process.Id -Force
            throw "BLDT Modern Standby timed out after $TimeoutSeconds seconds."
        }

        $process.WaitForExit()
        $timer.Stop()
        # Query Windows' own evidence of standby: 506 is entry, 507 is exit.
        # The XPath expression limits results to Kernel-Power events during this run.
        $finished = [DateTime]::UtcNow
        $begin = $started.ToString('o')
        $end = $finished.ToString('o')
        $filter = "*[System[Provider[@Name='Microsoft-Windows-Kernel-Power'] and " +
            "(EventID=506 or EventID=507) and TimeCreated[@SystemTime >= '$begin' and " +
            "@SystemTime <= '$end']]]"
        # Sort by event record order; $_ is the current event in ForEach-Object.
        # Python uses these timestamps to validate a single, long-enough sleep interval.
        $events = @(
            Get-WinEvent -LogName System -FilterXPath $filter -ErrorAction SilentlyContinue |
                Sort-Object RecordId |
                ForEach-Object {
                    [pscustomobject]@{
                        id = $_.Id
                        record_id = $_.RecordId
                        seconds = ($_.TimeCreated.ToUniversalTime() - $started).TotalSeconds
                        utc = $_.TimeCreated.ToUniversalTime().ToString('o')
                    }
                }
        )
        # Keep a readable evidence file as well as returning events to Python.
        ConvertTo-Json -InputObject $events -Depth 3 |
            Set-Content -LiteralPath $eventsLog -Encoding UTF8

        # Return the exit code, elapsed time, and nested event records as JSON.
        [pscustomobject]@{
            started_utc = $startedUtc
            exit_code = $process.ExitCode
            seconds = [math]::Round($timer.Elapsed.TotalSeconds, 3)
            events = $events
        } | ConvertTo-Json -Depth 4 -Compress
    } finally {
        $process.Dispose()
    }
}

function Copy-BldtReports {
    # Stage only reports created by this run; include shared HTML assets.
    if (-not $StartedUtc) { throw 'BLDT report start time was not provided.' }

    $started = [DateTime]::Parse($StartedUtc).ToUniversalTime()
    $reportRoot = Join-Path $env:USERPROFILE 'Intel\BatteryLifeDiagnostic'
    $destination = Join-Path $DataRoot 'bldt_modern_standby_reports'
    if (-not (Test-Path -LiteralPath $reportRoot -PathType Container)) {
        throw "BLDT report directory was not found: $reportRoot"
    }

    # Collect supported report formats written since the run began, including
    # supporting reports without a mosTest filename. $_ represents each file.
    $reports = @(Get-ChildItem -LiteralPath $reportRoot -File -Recurse | Where-Object {
        $_.LastWriteTimeUtc -ge $started -and
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

    [pscustomobject]@{
        reports = @($reports | ForEach-Object { $_.Name })
    } | ConvertTo-Json -Compress
}

# Execution reaches this block after defining the functions above.
try {
    # Dispatch one operation requested by Python; -eq means "equals".
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
    Invoke-ModernStandby -Executable $executable
} catch {
    # Report the exception and signal script failure (exit 1) to Python.
    $message = " ERROR - $($_.Exception.Message)"
    Write-Output $message
    if (Test-Path -LiteralPath $DataRoot) {
        Add-Content -LiteralPath $logFile -Value $message -Encoding UTF8 `
            -ErrorAction SilentlyContinue
    }
    exit 1
}
