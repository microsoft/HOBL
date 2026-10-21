# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = "",
    [string]$startTime = (Get-Date).ToString("o"),
    [string]$CompilerVersion = "21.1.8",
    [string]$InstallerSha256 = ""
)

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
        [HoblRunPhaseProvider]::Log.Phase($Marker, "llvm")
    } catch {
    }
}

# Configuration
$scriptDrive = Split-Path -Qualifier $PSScriptRoot

if (-not (Test-Path "$scriptDrive\hobl_data")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_data" -ForegroundColor Red
    Exit 1
}
if (-not (Test-Path "$scriptDrive\hobl_bin")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_bin" -ForegroundColor Red
    Exit 1
}

if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\llvm_run.log" }
$llvmBuildDir = "$scriptDrive\build_llvm"
$llvmInstallDir = "$env:ProgramFiles\llvm"
$metricsFile = "$scriptDrive\hobl_data\llvm_results.csv"
$traceFile = "$scriptDrive\hobl_data\llvm_results.trace"

# Determine processor architecture
$osInfo = Get-CimInstance Win32_OperatingSystem
$arch = $osInfo.OSArchitecture
$processorArch = $env:PROCESSOR_ARCHITECTURE

if ($arch -eq "64-bit" -and $processorArch -eq "AMD64") {
    $logSuffix = "x64"
    $vsArchParam = "x64"
    $vsHostArchParam = "x64"
    $vsProduct = "Community"
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    $logSuffix = "ARM64"
    $vsArchParam = "arm64"
    $vsHostArchParam = "arm64"
    $vsProduct = "Community"
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
        $code = 1
        " ERROR - Last command failed." | log
        Exit $code
    }
}

function getVSVersion {
    param([string]$product)

    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) {
        $vswhere = "${env:ProgramFiles}\Microsoft Visual Studio\Installer\vswhere.exe"
        if (-not (Test-Path $vswhere)) {
            return $null
        }
    }

    try {
        $productFilter = if ($product -eq "BuildTools") { "Microsoft.VisualStudio.Product.BuildTools" } else { "Microsoft.VisualStudio.Product.Community" }
        $instances = & $vswhere -products $productFilter -format json | ConvertFrom-Json

        if ($instances) {
            $instance = $instances | Select-Object -First 1
            return @{
                Version = $instance.installationVersion
                Path = $instance.installationPath
            }
        }
    } catch {
        return $null
    }

    return $null
}

Set-Content -Path $logFile -encoding utf8 "-- llvm_run started ($logSuffix version)"
Write-RunPhaseMarker "phase.run_prep.start"

$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# Verify required commands are findable on PATH after refresh.
# Fail fast with a clear diagnostic instead of a chain of "term not recognized" errors.
foreach ($cmd in @('ninja')) {
    $resolved = Get-Command $cmd -ErrorAction SilentlyContinue
    if (-not $resolved) {
        " ERROR - Required command '$cmd' not found on PATH after refresh." | log
        " ERROR - Prep may not have completed, or the RPC service has a stale PATH." | log
        " ERROR - PATH: $env:Path" | log
        Exit 1
    }
    "Found ${cmd}: $($resolved.Source)" | log
}

# --- Initialize Visual Studio Developer Command environment ---
# VsDevCmd.bat sets up LIB, INCLUDE, and PATH so that MSVC libraries and headers
# are discoverable during the build (e.g., ATL/MFC, Windows SDK, UCRT).
"-- Initializing Visual Studio Developer Command environment" | log

$vsInfo = getVSVersion -product $vsProduct
if (-not $vsInfo -or -not $vsInfo.Path) {
    " ERROR - Visual Studio $vsProduct installation not found via vswhere" | log
    Exit 1
}
"Found Visual Studio at: $($vsInfo.Path)" | log

$vsDevCmd = Join-Path $vsInfo.Path "Common7\Tools\VsDevCmd.bat"
if (-not (Test-Path $vsDevCmd)) {
    " ERROR - VsDevCmd.bat not found at: $vsDevCmd" | log
    Exit 1
}
"Using VsDevCmd.bat: $vsDevCmd" | log

$vsDevCmdArgs = "-arch=$vsArchParam -host_arch=$vsHostArchParam -no_logo"
"Sourcing VsDevCmd.bat with args: $vsDevCmdArgs" | log
cmd /c "`"$vsDevCmd`" $vsDevCmdArgs && set" | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}
"✓ Visual Studio Developer Command environment initialized" | log

# Add LLVM bin to PATH
$llvmBinPath = "$llvmInstallDir\bin"
if (Test-Path $llvmBinPath) {
    $Env:Path = "$llvmBinPath;$Env:Path"
    "✓ LLVM bin added to PATH: $llvmBinPath" | log
} else {
    " ERROR - LLVM bin directory not found: $llvmBinPath. Run llvm_prep.ps1 first." | log
    Exit 1
}

# Verify build directory
"-- Verifying build directory" | log
if (-not (Test-Path $llvmBuildDir)) {
    " ERROR - LLVM build directory not found: $llvmBuildDir. Run llvm_prep.ps1 first." | log
    Exit 1
}

if (-not (Test-Path "$llvmBuildDir\CMakeCache.txt")) {
    " ERROR - CMakeCache.txt not found in $llvmBuildDir. Run llvm_prep.ps1 first." | log
    Exit 1
}
"✓ Build directory verified" | log

# Check the actual compiler before timing; never silently use another LLVM.
try {
    . (Join-Path $PSScriptRoot 'llvm_toolchain.ps1')
    $compiler = Get-LlvmCompilerInfo -InstallDir $llvmInstallDir -ExpectedVersion $CompilerVersion
    if ($InstallerSha256) {
        Assert-LlvmMsiReceipt -Path (Join-Path $PSScriptRoot 'llvm_msi_receipt.json') -Sha256 $InstallerSha256 -Compiler $compiler
    }
    $cache = Get-Content -LiteralPath (Join-Path $llvmBuildDir 'CMakeCache.txt') -ErrorAction Stop
    foreach ($language in @('C', 'CXX')) {
        $entry = @($cache | Where-Object { $_ -match "^CMAKE_${language}_COMPILER:[^=]+=" })
        if ($entry.Count -ne 1 -or ($entry[0] -split '=', 2)[1].Replace('/', '\') -ne $compiler.ClangCl.Replace('/', '\')) {
            throw "CMake $language compiler does not match the selected toolchain. Re-prep required."
        }
    }
    "Using LLVM compiler $($compiler.Version) ($($compiler.Architecture)): $($compiler.ClangCl)" | log
} catch {
    " ERROR - $($_.Exception.Message)" | log
    Exit 1
}

# Clean previous build using ninja directly (matches ProjectD measurement methodology)
$time = Get-Date -Format "HH:mm:ss"
"$time - Cleaning previous build" | log
ninja -C $llvmBuildDir clean
"✓ Build cleaned" | log

# Build LLVM with timing
$time = Get-Date -Format "HH:mm:ss"
"$time - Building LLVM ($logSuffix)" | log
Write-RunPhaseMarker "phase.run_prep.end"
Write-RunPhaseMarker "phase.run_build.start"

# Use ninja directly instead of 'cmake --build' wrapper.
# ProjectD warns that cmake --build "may not be comparable" with ninja -C.
$logDir = Split-Path $logFile -Parent
$buildLog = "$logDir\llvm_build_$($logSuffix.ToLower()).log"
"Build output redirected to: $buildLog" | log

$buildTime = (Measure-Command {
    ninja -C $llvmBuildDir 2>&1 | Tee-Object -FilePath $buildLog
}).TotalSeconds
$buildExitCode = $LASTEXITCODE
$buildTime = [math]::Round($buildTime, 2)
"Build completed in ${buildTime}s" | log
check($buildExitCode)
Write-RunPhaseMarker "phase.run_build.end"
Write-RunPhaseMarker "phase.run_results.start"

$time = Get-Date -Format "HH:mm:ss"
"$time - LLVM build completed" | log

# Confirm build by checking for clang binary
$time = Get-Date -Format "HH:mm:ss"
"$time - Confirming build" | log

$clangExe = "$llvmBuildDir\bin\clang.exe"
if (-not (Test-Path $clangExe)) {
    " ERROR - clang.exe not found after build at $clangExe" | log
    Exit 1
}
"✓ clang.exe found" | log

& $clangExe --version
check($lastexitcode)

"-- llvm_run completed ($logSuffix version)" | log

# ============================================================================
# Calculate scenario_runtime and save metrics
# ============================================================================
$scenarioRuntime = $buildTime

Write-Host ""
Write-Host "========================================"
Write-Host "LLVM Build Metrics Summary"
Write-Host "========================================"
Write-Host "Build Time:  ${buildTime}s"
Write-Host "scenario_runtime (total): ${scenarioRuntime}s"
Write-Host "========================================"

# Write metrics CSV file (key,value format)
$metricsContent = @"
scenario_runtime,$scenarioRuntime
build_time,$buildTime
"@

Set-Content -Path $metricsFile -Value $metricsContent -NoNewline
"Metrics saved to: $metricsFile" | log

$elapsedTime = ((Get-Date) - [DateTime]$startTime).TotalSeconds
# Append to .trace file for timeline correlation (key,value format)

if (-not (Test-Path $traceFile)) {
    "Creating trace file with header: $traceFile" | log
    Set-Content -Path $traceFile -Value "Timestamp,llvm_build_time" -Encoding UTF8
}

$traceContent = @"
$elapsedTime,$buildTime
"@

Add-Content -Path $traceFile -Value $traceContent -Encoding UTF8
"Appended build time to trace file: $traceFile" | log

Write-RunPhaseMarker "phase.run_results.end"

Exit 0