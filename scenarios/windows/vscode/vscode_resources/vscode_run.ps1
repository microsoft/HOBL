param(
    [string]$logFile = ""
)

# Require PowerShell > 7
$required = [version]"7.0"
if (-not $PSVersionTable.PSVersion) {
    Write-Host "Cannot determine PowerShell version; aborting." -ForegroundColor Red
    Exit 1
}
if ([version]$PSVersionTable.PSVersion -le $required) {
    Write-Host "This script requires PowerShell greater than $required. Current: $($PSVersionTable.PSVersion)" -ForegroundColor Yellow
    Write-Host "Please install PowerShell 7 or later from https://aka.ms/powershell" -ForegroundColor Yellow
    Exit 1
}

$scriptDrive = Split-Path -Qualifier $PSScriptRoot

if (-not (Test-Path "$scriptDrive\hobl_data")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_data" -ForegroundColor Red
    Exit 1
}
if (-not (Test-Path "$scriptDrive\hobl_bin")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_bin" -ForegroundColor Red
    Exit 1
}

if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\vscode_run.log" }
$vscodePath = "$scriptDrive\vscode"
$metricsFile = "$scriptDrive\hobl_data\vscode_results.csv"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 9F0F6E2E-8D06-4D2F-B8F5-6F1F2D5A1C01 is a custom provider we use to emit phase markers from the scenario script (optional, may not be present)
if (-not ('HoblRunPhaseProvider' -as [type])) {
    Add-Type -TypeDefinition @"
using System.Diagnostics.Tracing;

[EventSource(Name = "HOBL-Scenario-Phases", Guid = "9f0f6e2e-8d06-4d2f-b8f5-6f1f2d5a1c01")]
public sealed class HoblRunPhaseProvider : EventSource
{
    public static readonly HoblRunPhaseProvider Log = new HoblRunPhaseProvider();

    [Event(1, Level = EventLevel.Informational)]
    public void Phase(string marker, string scenario)
    {
        WriteEvent(1, marker, scenario);
    }
}
"@
}

function Write-RunPhaseMarker {
    param([string]$Marker)

    try {
        [HoblRunPhaseProvider]::Log.Phase($Marker, "vscode")
    } catch {
    }
}

# Determine processor architecture
$osInfo = Get-CimInstance Win32_OperatingSystem
$arch = $osInfo.OSArchitecture
$processorArch = $env:PROCESSOR_ARCHITECTURE

if ($arch -eq "64-bit" -and $processorArch -eq "AMD64") {
    $logSuffix = "x64"
    $pythonVersion = "3.12.10"
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    $logSuffix = "ARM64"
    $pythonVersion = "3.12.10-arm"
} else {
    Write-Host " ERROR - Unsupported architecture: $arch (Processor: $processorArch)" -ForegroundColor Red
    Exit 1
}

# Update log file name to include architecture
$logFile = $logFile -replace "\.log$", "_$($logSuffix.ToLower()).log"

function log {
    [CmdletBinding()] Param([Parameter(ValueFromPipeline)] $msg)
    process {
        if ($msg -Match " ERROR - ") {
            Write-Host $msg -ForegroundColor Red
        } else {
            Write-Host $msg
        }
        Add-Content -Path $logFile -encoding utf8 "$msg"
    }
}

function check {
    param($code)
    if ($code -ne 0) {
        " ERROR - Last command failed with exit code: $code" | log
        Exit $code
    }
}

Set-Content -Path $logFile -encoding utf8 "-- vscode run started ($logSuffix version)"
Write-RunPhaseMarker "phase.run_prep.start"

"Detected architecture: $arch (Processor: $processorArch)" | log

# Store original environment for restoration
$originalPath = $env:PATH
$originalPython = $env:PYTHON
$originalPythonHome = $env:PYTHONHOME

# Setup pyenv environment
$pyenvRoot = "$env:USERPROFILE\.pyenv"
$env:PATH = "$pyenvRoot\pyenv-win\bin;$pyenvRoot\pyenv-win\shims;$env:PATH"

"Setting global Python $pythonVersion for $logSuffix build" | log
pyenv global $pythonVersion

# Use pyenv which python to get the real executable path (not the shim)
$pythonExeRaw = pyenv which python 2>$null
if ($pythonExeRaw) {
    $pythonExe = $pythonExeRaw.Trim()
    if (Test-Path $pythonExe) {
        "Using Python: $pythonExe" | log
    } else {
        " ERROR - pyenv which python returned non-existent path: $pythonExe" | log
        Exit 1
    }
} else {
    " ERROR - pyenv which python failed" | log
    Exit 1
}

$pythonDir = Split-Path $pythonExe -Parent

# Keep WindowsApps in PATH, but de-duplicate the explicit Python directory before prepending
$cleanPath = ($env:PATH -split ';' | Where-Object { $_ -and ($_ -ne $pythonDir) }) -join ';'
$env:PATH = "$pythonDir;$cleanPath"

# Set environment variables so Node.js native module builds find Python
$env:PYTHON = $pythonExe
$env:PYTHONHOME = $pythonDir
"PYTHON=$env:PYTHON" | log
"PYTHONHOME=$env:PYTHONHOME" | log

$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
# Re-prepend pyenv paths after PATH refresh
$env:PATH = "$pyenvRoot\pyenv-win\bin;$pyenvRoot\pyenv-win\shims;$pythonDir;$env:PATH"

# Select and validate the same private runtime used during prep. Do not install
# or fall back to another scenario's Node version during a measured run.
try {
    . (Join-Path $PSScriptRoot "vscode_node.ps1")
    Enable-VscodeNode
} catch {
    " ERROR - $($_.Exception.Message)" | log
    Exit 1
}

# Verify required commands are findable on PATH after refresh.
# Fail fast with a clear diagnostic instead of a chain of "term not recognized" errors.
foreach ($cmd in @('pyenv', 'node', 'npm')) {
    $resolved = Get-Command $cmd -ErrorAction SilentlyContinue
    if (-not $resolved) {
        " ERROR - Required command '$cmd' not found on PATH after refresh." | log
        " ERROR - Prep may not have completed, or the RPC service has a stale PATH." | log
        " ERROR - PATH: $env:Path" | log
        Exit 1
    }
    "Found ${cmd}: $($resolved.Source)" | log
}

# Navigate to VS Code directory
if (-not (Test-Path $vscodePath)) {
    " ERROR - VS Code directory not found: $vscodePath. Run vscode_prep.ps1 first." | log
    Exit 1
}
Set-Location $vscodePath

# Clean build artifacts from previous run (preserve node_modules installed during prep)
"-- Cleaning previous build artifacts" | log
if (Test-Path "out") {
    Remove-Item -Recurse -Force "out"
    "Removed out/ directory" | log
}
if (Test-Path ".build") {
    Remove-Item -Recurse -Force ".build"
    "Removed .build/ directory" | log
}

# Build VS Code and measure time
$time = Get-Date -Format "HH:mm:ss"
"$time - Building VS Code ($logSuffix)" | log
Write-RunPhaseMarker "phase.run_prep.end"
Write-RunPhaseMarker "phase.run_build.start"

# Redirect npm output to a per-phase log so it is preserved in the results
# share. Measure-Command discards pipeline output entirely; without a file
# redirect, npm's output is lost.
$logDir = Split-Path $logFile -Parent
$buildLog = "$logDir\vscode_build_$($logSuffix.ToLower()).log"
"Build output: $buildLog" | log

$buildTime = (Measure-Command {
    npm run compile *> $buildLog
}).TotalSeconds
$buildExitCode = $LASTEXITCODE
$buildTime = [math]::Round($buildTime, 2)

"Build completed in ${buildTime}s" | log
if ($buildExitCode -ne 0) {
    " ERROR - npm compile failed. See $buildLog for details." | log
    Exit 1
}
Write-RunPhaseMarker "phase.run_build.end"
Write-RunPhaseMarker "phase.run_results.start"

$time = Get-Date -Format "HH:mm:ss"
"$time - VS Code build completed" | log

# Verify build output exists
if (-not (Test-Path "$vscodePath\out")) {
    " ERROR - Build output directory not found: $vscodePath\out" | log
    Exit 1
}
"Build output verified: $vscodePath\out" | log

# ============================================================================
# Calculate scenario_runtime and save metrics
# ============================================================================
$scenarioRuntime = $buildTime

"" | log
"========================================" | log
"VS Code Build Metrics Summary" | log
"========================================" | log
"Build Time:            ${buildTime}s" | log
"scenario_runtime:      ${scenarioRuntime}s" | log
"Architecture:          $logSuffix" | log
"========================================" | log

# Write metrics CSV file (key,value format - HOBL convention)
$metricsContent = @(
    "scenario_runtime,$scenarioRuntime"
    "build_time,$buildTime"
    "architecture,$logSuffix"
)
$metricsContent | Set-Content $metricsFile -Encoding UTF8
"Metrics saved to: $metricsFile" | log

# Restore original environment to not affect other programs
$env:PATH = $originalPath
if ($originalPython) { $env:PYTHON = $originalPython } else { Remove-Item Env:PYTHON -ErrorAction SilentlyContinue }
if ($originalPythonHome) { $env:PYTHONHOME = $originalPythonHome } else { Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue }
"Environment restored" | log

"" | log
"-- vscode run completed ($logSuffix version)" | log
Write-RunPhaseMarker "phase.run_results.end"

Exit 0
