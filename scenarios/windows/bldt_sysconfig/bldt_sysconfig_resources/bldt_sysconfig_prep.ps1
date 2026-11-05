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

    [ValidateSet('AC', 'DC')]
    [string]$PowerSource = 'AC',

    [string]$DataRoot = '',
    [int]$TimeoutSeconds = 900,
    [string]$StartedUtc = ''
)

# Send PowerShell errors to the catch block; hide progress bars in unattended runs.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Keep HOBL files on the script's drive when Python does not provide a path.
$scriptDrive = Split-Path -Qualifier $PSScriptRoot
if (-not $DataRoot) { $DataRoot = "$scriptDrive\hobl_data" }
$logFile = Join-Path $DataRoot 'bldt_sysconfig_prep.log'

# Write diagnostic messages to a file, keeping output available for Python's results.
function log {
    param([string]$Message)
    Add-Content -LiteralPath $logFile -Value $Message -Encoding UTF8
}

# Find where BLDT is installed on the system
function Get-BldtExecutable {
    # Read both Windows registry views so custom BLDT install locations work.
    $registryKeys = @(
        'HKLM:\SOFTWARE\Intel\Battery Life Diagnostic Tool',
        'HKLM:\SOFTWARE\WOW6432Node\Intel\Battery Life Diagnostic Tool'
    )

    # Skip missing entries; return a path only when the executable actually exists.
    foreach ($registryKey in $registryKeys) {
        if (-not (Test-Path -LiteralPath $registryKey)) { continue }
        $installPath = (Get-ItemProperty -LiteralPath $registryKey).Path
        if (-not $installPath) { continue }

        $executable = Join-Path $installPath 'BatteryLifeDiagnosticTool.exe'
        if (Test-Path -LiteralPath $executable -PathType Leaf) { return $executable }
    }

    return $null
}

# Download and Install BLDT 
function Install-Bldt {
    # Download Intel's standard BLDT package into a temporary working directory.
    $downloadUrl = 'https://downloadmirror.intel.com/925424/bldt_setup-v3.1.1.zip'
    $workDirectory = Join-Path $env:TEMP ("hobl_bldt_" + [guid]::NewGuid().ToString('N'))
    $archivePath = Join-Path $workDirectory 'bldt.zip'
    $extractPath = Join-Path $workDirectory 'extracted'
    $msiLog = Join-Path $DataRoot 'bldt_sysconfig_install.log'

    # Use a unique temporary folder; Out-Null discards directory-creation output.
    New-Item -ItemType Directory -Path $DataRoot, $workDirectory -Force | Out-Null

    try {
        log "Downloading BLDT from $downloadUrl"
        Invoke-WebRequest -Uri $downloadUrl -OutFile $archivePath -UseBasicParsing -TimeoutSec 10800

        log "Extracting BLDT to $extractPath"
        Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath -Force

        # @() keeps the search result as a list, even when it contains only one MSI.
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

        # Stop this installer if it exceeds one hour
        try {
            if (-not $process.WaitForExit(3600000)) {
                Stop-Process -Id $process.Id -Force
                throw 'BLDT installation timed out after 3600 seconds.'
            }
            $process.WaitForExit()
            $exitCode = $process.ExitCode
        } finally {
            # Release the process object's resources, whether the wait succeeds or fails.
            $process.Dispose()
        }

        if ($exitCode -ne 0) { throw "BLDT installation failed with exit code $exitCode; see $msiLog." }
    } finally {
        # Always remove this download's temporary files, not the installed application.
        if (Test-Path -LiteralPath $workDirectory) { Remove-Item -LiteralPath $workDirectory -Recurse -Force }
    }
}

# Run the SysConfig checks using the installed BLDT executable
function Invoke-SysConfigChecks {
    param([string]$Executable)

    # Run Intel's workload, capture both output streams, and enforce the scenario timeout.
    New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null
    $stdoutLog = Join-Path $DataRoot 'bldt_sysconfig_stdout.log'
    $stderrLog = Join-Path $DataRoot 'bldt_sysconfig_stderr.log'
    $workingDirectory = Split-Path -Parent $Executable

    # These are Intel CLI options, not PowerShell commands. AC/DC selects the assessment mode; it does not physically switch the charger's power.
    $arguments = @('--type', 'SysConfigChecks', '--params', "pwrsrc:$PowerSource", '--telemetry=false')

    # UTC identifies fresh reports; the stopwatch only measures the workload.
    $startedUtc = [DateTime]::UtcNow.ToString('o')
    $timer = [Diagnostics.Stopwatch]::StartNew()

    # Save normal/error output separately; PassThru returns the process for monitoring.
    $process = Start-Process -FilePath $Executable -ArgumentList $arguments -WorkingDirectory $workingDirectory -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru

    try {
        $null = $process.Handle
        # Set a time out for the workload, stop it if it exceeds the allowed duration
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            Stop-Process -Id $process.Id -Force
            throw "BLDT SysConfigChecks timed out after $TimeoutSeconds seconds."
        }
        $process.WaitForExit()
        $timer.Stop()
        
        # Return a result record for Python, including start time, exit code, and elapsed seconds.
        [pscustomobject]@{
            started_utc = $startedUtc
            exit_code = $process.ExitCode
            seconds = [math]::Round($timer.Elapsed.TotalSeconds, 3)
        } | ConvertTo-Json -Compress
    } finally {
        $process.Dispose()
    }
}

# Gather the reports generated by BLDT for this run
function Copy-BldtReports {
    # Stage only SysConfig reports created by this run; include shared HTML assets when present.
    if (-not $StartedUtc) { throw 'BLDT report start time was not provided.' }

    $started = [DateTime]::Parse($StartedUtc).ToUniversalTime()
    $reportRoot = Join-Path $env:USERPROFILE 'Intel\BatteryLifeDiagnostic'
    $destination = Join-Path $DataRoot 'bldt_sysconfig_reports'

    if (-not (Test-Path -LiteralPath $reportRoot -PathType Container)) { throw "BLDT report directory was not found: $reportRoot" }

    # Filter by both the workload name and timestamp to avoid collecting older runs.
    $reports = @(Get-ChildItem -LiteralPath $reportRoot -File -Recurse | Where-Object {
        $_.LastWriteTimeUtc -ge $started -and
        $_.BaseName -like 'SysConfigChecks_*' -and
        $_.Extension.ToLowerInvariant() -in '.html', '.htm', '.json', '.zip'
    })

    # Preserve subfolders while staging reports to where HOBL retrieves them.
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
    New-Item -ItemType Directory -Path $DataRoot -Force | Out-Null

    if ($Action -eq 'Install') {
        Install-Bldt
        exit 0
    }

    if ($Action -eq 'CopyReports') {
        Copy-BldtReports
    } else {
        $executable = Get-BldtExecutable
        if (-not $executable) { throw 'BatteryLifeDiagnosticTool.exe was not found.' }
    }

    if ($Action -eq 'Discover') {
        Write-Output $executable
    } elseif ($Action -eq 'Run') {
        Invoke-SysConfigChecks -Executable $executable
    }
} catch {
    # Report the exception and signal script failure (exit 1) to the Python caller.
    $message = " ERROR - $($_.Exception.Message)"
    Write-Output $message
    if (Test-Path -LiteralPath $DataRoot) { Add-Content -LiteralPath $logFile -Value $message -Encoding UTF8 -ErrorAction SilentlyContinue }
    exit 1
}
