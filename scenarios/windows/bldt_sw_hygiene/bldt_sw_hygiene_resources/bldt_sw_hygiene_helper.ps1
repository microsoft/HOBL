# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Windows helper for Software Hygiene and its optional follow-up AI analysis.
# Despite the "prep" filename, it installs, locates, runs, and collects BLDT.
# param declares inputs; $ names a variable, and ValidateSet limits allowed values.
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Install', 'Discover', 'RunHygiene', 'RunAi', 'CopyReports')]
    [string]$Action,
    [string]$DataRoot = '',
    # A switch is an on/off input; request AI payloads only when analysis is enabled.
    [switch]$RequireAi,
    [int]$CollectionDurationSeconds = 600,
    [int]$WindowsPerformanceRecorderDurationSeconds = 600,
    [ValidateSet('AC', 'DC')]
    [string]$PowerSource = 'DC',
    [string]$StartedUtc = '',
    [ValidateSet('SWHygiene', 'AIAnalysis')]
    [string]$ReportKind = 'SWHygiene',
    [string]$InputFile = ''
)

# Send PowerShell errors to the catch block; hide progress bars in unattended runs.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Default to the script's drive, not a hardcoded drive; Python can supply DataRoot.
$scriptDrive = Split-Path -Qualifier $PSScriptRoot
if (-not $DataRoot) { $DataRoot = "$scriptDrive\hobl_data" }
$reportDirectory = Join-Path $DataRoot 'bldt_sw_hygiene_reports'
$logFile = Join-Path $reportDirectory 'bldt_sw_hygiene_prep.log'

# Keep diagnostic messages out of the structured results sent back to Python.
function log {
    param([string]$Message)
    Add-Content -LiteralPath $logFile -Value $Message -Encoding UTF8
}

function Get-BldtInstallation {
    param([switch]$RequireAi)

    # Intel's registry entries reveal custom installation paths in either registry view.
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

        # The executable alone does not prove AI is available: check both payload files.
        $version = (Get-Item -LiteralPath $executable).VersionInfo.ProductVersion
        $hasAiPayloads = $true
        foreach ($payloadName in 'AIAnalyzer.tar.gz', 'AIAnalyzerModels.tar.gz') {
            $payload = Join-Path $installPath "src\$payloadName"
            if (-not (Test-Path -LiteralPath $payload -PathType Leaf)) {
                $hasAiPayloads = $false
            }
        }

        if ($RequireAi -and -not $hasAiPayloads) { continue }

        # Return one record describing the usable installation, or null if none is found.
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

    # Choose Intel's standard or AI package before downloading to a unique temp folder.
    $stem = if ($Edition -eq 'ai') {
        'bldt-ai_setup-v3.1.1'
    } else {
        'bldt_setup-v3.1.1'
    }
    $downloadUrl = "https://downloadmirror.intel.com/925424/$stem.zip"
    $workDirectory = Join-Path $env:TEMP ("hobl_bldt_" + [guid]::NewGuid().ToString('N'))
    $archivePath = Join-Path $workDirectory 'bldt.zip'
    $extractPath = Join-Path $workDirectory 'extracted'
    $msiLog = Join-Path $reportDirectory "bldt_sw_hygiene_$Edition.install.log"

    # Out-Null discards directory-creation output so it cannot pollute Python's result.
    New-Item -ItemType Directory -Path $reportDirectory, $workDirectory -Force | Out-Null

    try {
        log "Downloading BLDT $Edition edition from $downloadUrl"
        Invoke-WebRequest -Uri $downloadUrl -OutFile $archivePath -UseBasicParsing -TimeoutSec 10800

        log "Extracting BLDT to $extractPath"
        Expand-Archive -LiteralPath $archivePath -DestinationPath $extractPath -Force

        # Require exactly one matching MSI, with its AI payloads present if needed.
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

        # Install without UI or automatic reboot, retaining a detailed Windows MSI log.
        # Escaped quotes preserve paths containing spaces.
        $arguments = "/i `"$installerPath`" /qn /norestart REBOOT=ReallySuppress " +
            "INSTALLER_SOURCE_DIR=`"$installerDirectory`" WIXUI_EXITDIALOGOPTIONALCHECKBOX=0 " +
            "/L*v `"$msiLog`""
        log "Installing BLDT $Edition from $installerPath"
        $process = Start-Process -FilePath $msiexec -ArgumentList $arguments `
            -WorkingDirectory $installerDirectory -PassThru

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

        # A reboot-required MSI result is not ready for a workload; surface it explicitly.
        if ($exitCode -in 1641, 3010) {
            throw 'BLDT installation requires a DUT reboot; reboot and rerun prep.'
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

# Reuse a suitable installation; install only when the required edition is missing.
function Install-RequiredBldt {
    $installation = Get-BldtInstallation -RequireAi:$RequireAi
    $requiredEdition = if ($RequireAi) { 'ai' } else { 'standard' }

    if ($null -ne $installation) {
        log "Using existing BLDT $($installation.edition) edition at $($installation.executable)"
        return
    }

    # Discover again after installation to confirm that the required files now exist.
    Install-Bldt -Edition $requiredEdition
    $installation = Get-BldtInstallation -RequireAi:$RequireAi
    if ($null -eq $installation) {
        throw 'BatteryLifeDiagnosticTool.exe was not found after installation.'
    }
}

# Discover returns just the executable path for the Python caller.
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

# Shared runner: Hygiene and AI use the same logging and process handling.
function Invoke-Bldt {
    param(
        [string]$Executable,
        [string[]]$Arguments,
        [string]$LogPrefix
    )

    New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
    $stdoutLog = Join-Path $reportDirectory "$LogPrefix.stdout.log"
    $stderrLog = Join-Path $reportDirectory "$LogPrefix.stderr.log"
    # UTC identifies fresh reports.
    $startedUtc = [DateTime]::UtcNow.ToString('o')
    # Save normal/error output separately; PassThru returns the process to monitor.
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments `
        -WorkingDirectory (Split-Path -Parent $Executable) `
        -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru

    try {
        $null = $process.Handle
        $process.WaitForExit()
        # Build a result record and pipe (|) it to JSON conversion for Python.
        [pscustomobject]@{
            started_utc = $startedUtc
            exit_code = $process.ExitCode
        } | ConvertTo-Json -Compress
    } finally {
        $process.Dispose()
    }
}

function Invoke-SoftwareHygiene {
    param([string]$Executable)

    # Intel options use independent SoC Watch and Windows Performance Recorder durations,
    # with no minimum-charge gate or collection delay. PowerSource describes the
    # detected state; it does not switch the charger.
    $windowsPerformanceRecorderDurationMilliseconds =
        $WindowsPerformanceRecorderDurationSeconds * 1000
    $parameters = (
        "min_battery_charge:0;" +
        "socwatch_duration:$CollectionDurationSeconds;" +
        "socwatch_delay:0;" +
        "socwatch_pwrsrc:$PowerSource;" +
        "wpr_duration_power:$windowsPerformanceRecorderDurationMilliseconds;" +
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

    # AI analyzes the JSON from the preceding Hygiene run, not a new activity capture.
    # Check that the input exists in Intel's report folder before starting analysis.
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
    $destination = $reportDirectory
    if (-not (Test-Path -LiteralPath $reportRoot -PathType Container)) {
        throw "BLDT report directory was not found: $reportRoot"
    }

    # Filter by this run's start time and report kind to avoid old or mismatched output.
    # Where-Object examines each file as $_; @() collects the matches into a list.
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

    # Return the newest collected Hygiene JSON filename for optional AI analysis.
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

# Execution starts here after defining the functions: select one requested operation.
try {
    New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null

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

    # -eq means "equals"; the colon passes that Boolean result to the RequireAi switch.
    # Running AI requires its payloads; running Hygiene accepts either edition.
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
    # Report the exception and signal script failure (exit 1) to Python.
    $message = " ERROR - $($_.Exception.Message)"
    Write-Output $message
    if (Test-Path -LiteralPath $reportDirectory -PathType Container) {
        Add-Content -LiteralPath $logFile -Value $message -Encoding UTF8 `
            -ErrorAction SilentlyContinue
    }
    exit 1
}
