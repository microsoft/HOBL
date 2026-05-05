# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.
#
# start_percentile_stress.ps1 - Launcher for percentile_stress.py on the DUT.
#
# Architecture-agnostic: pyenv-win resolves the right python.exe (x64 or arm64)
# based on whatever was installed by perf_stress_prep.ps1.
#
# Called from code_1EN194J.py via a single PowerShell invocation - all pyenv
# resolution, diagnostics, and Start-Process happen here so the host side does
# not have to escape nested quotes through cmd->powershell.
#
# Diagnostics tee to $LogFile on the DUT for post-mortem.
# Exit codes:
#   0 = python.exe launched successfully and still alive after 1.5s
#   1 = pyenv-win not installed / wrong path - re-run perf_stress_prep.ps1
#   2 = python.exe died within 1.5s of launch (check log + percentile_stress.py)

param(
    [Parameter(Mandatory=$true)]
    [string]$ScriptPath,

    [Parameter(Mandatory=$true)]
    [ValidateSet('0','25','50','65','75','85')]
    [string]$TargetCpu,

    [string]$LogFile = "C:\hobl_bin\percentile_stress_launch.log"
)

$ErrorActionPreference = 'Continue'

function Write-Step {
    param([string]$Message)
    $line = (Get-Date -Format 'HH:mm:ss') + ' ' + $Message
    Write-Host $line
    try {
        Add-Content -Path $LogFile -Value $line -ErrorAction SilentlyContinue
    } catch {}
}

Write-Step ' === percentile_stress launcher start ==='
Write-Step (' ScriptPath = ' + $ScriptPath)
Write-Step (' TargetCpu  = ' + $TargetCpu)
Write-Step (' Architecture = ' + $env:PROCESSOR_ARCHITECTURE)

# --- pyenv-win path resolution (works for x64 and arm64 DUTs identically) ---
$shims = Join-Path $env:USERPROFILE '.pyenv\pyenv-win\shims'
$pbin  = Join-Path $env:USERPROFILE '.pyenv\pyenv-win\bin'
Write-Step (' shims=' + $shims + ' exists=' + (Test-Path $shims))
Write-Step (' pbin =' + $pbin  + ' exists=' + (Test-Path $pbin))

if (-not (Test-Path $shims) -or -not (Test-Path $pbin)) {
    Write-Step ' ERROR - pyenv-win not installed on this DUT. Re-run perf_stress_prep.ps1.'
    exit 1
}

$env:PATH = $shims + ';' + $pbin + ';' + $env:PATH

$py = (& pyenv which python 2>$null)
Write-Step (" pyenv which python returned: [" + $py + "]")
if (-not $py -or -not (Test-Path $py)) {
    Write-Step ' ERROR - pyenv which python returned no valid path. Prep pyenv install incomplete.'
    exit 1
}

$pyVer = (& $py --version 2>&1)
Write-Step (' python version: ' + $pyVer)

# Validate the script we are about to run actually exists
if (-not (Test-Path $ScriptPath)) {
    Write-Step (' ERROR - script not found: ' + $ScriptPath)
    exit 1
}

# --- Launch ---
# Use Win32_Process::Create via CIM/WMI rather than Start-Process or Start-Job.
# Why: every prior approach hung the launcher PowerShell because PS held some
# handle/job reference to the child:
#   - Start-Process -RedirectStandardOutput inherits handles -> PS won't exit
#   - Start-Job + Start-Process redirects has the same handle issue inside the job
#   - PS's own background operator (&) keeps the runspace alive
# Win32_Process::Create spawns through WmiPrvSE.exe with no inherited handles
# from our shell. The launcher returns immediately, python.exe survives as an
# orphan owned by WmiPrvSE.
# Cost: we cannot redirect python's stdout/stderr through this path. That's
# acceptable - the script's argparse choices are now fixed, and the post-launch
# liveness probe still catches any crash within 1.5s.
Write-Step (' launching via Win32_Process::Create')
Write-Step (' command: ' + $py + ' ' + $ScriptPath + ' --target-cpu ' + $TargetCpu)

# Quote both paths in case of spaces; CommandLine is a single string.
$cmdLine = '"' + $py + '" "' + $ScriptPath + '" --target-cpu ' + $TargetCpu
try {
    $result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create `
                               -Arguments @{ CommandLine = $cmdLine } `
                               -ErrorAction Stop
} catch {
    Write-Step (' ERROR - Win32_Process::Create threw: ' + $_.Exception.Message)
    exit 2
}

# ReturnValue 0 = success per WMI docs.
if ($result.ReturnValue -ne 0) {
    Write-Step (' ERROR - Win32_Process::Create ReturnValue=' + $result.ReturnValue)
    exit 2
}

$childPid = $result.ProcessId
Write-Step (' python PID=' + $childPid)

Start-Sleep -Milliseconds 1500
$alive = Get-Process -Id ([int]$childPid) -ErrorAction SilentlyContinue
if ($alive) {
    Write-Step (' PERCENTILE_STRESS_RUNNING pid=' + $childPid)
    exit 0
} else {
    Write-Step (' ERROR - python.exe died within 1.5s of launch')
    Write-Step ('   To capture stderr for debugging, manually run on the DUT:')
    Write-Step ('   & "' + $py + '" "' + $ScriptPath + '" --target-cpu ' + $TargetCpu)
    exit 2
}
