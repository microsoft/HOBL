# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

$ErrorActionPreference = "SilentlyContinue"
Write-Host " INFO - stop_perfStress_background starting"

# Retry helper so cleanup remains robust when processes are still spinning up/down.
function Stop-PerfStressProcesses {
    $patterns = "percentile_stress\.py|install_python\.ps1"
    $attempt = 0
    while ($attempt -lt 5) {
        $found = $false
        $killedThisAttempt = 0

        Get-CimInstance Win32_Process |
            Where-Object { $_.CommandLine -and ($_.CommandLine -match $patterns) } |
            ForEach-Object {
                $found = $true
                $killedThisAttempt++
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }

        # Extra guards for python launch variants.
        Get-CimInstance Win32_Process |
            Where-Object { $_.Name -match "(?i)^(python|py|pythonw)\.exe$" -and $_.CommandLine -and ($_.CommandLine -match "percentile_stress\.py") } |
            ForEach-Object {
                $found = $true
                $killedThisAttempt++
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }

        Write-Host (" INFO - Stop attempt {0}: killed candidates={1}" -f ($attempt + 1), $killedThisAttempt)

        if (-not $found) {
            break
        }

        Start-Sleep -Milliseconds 500
        $attempt++
    }
}

function Close-ExplorerWindows {
    # Filter to actual File Explorer folder windows (have a MainWindowTitle).
    # The desktop shell explorer process has MainWindowHandle != 0 but no title, so excluding it
    # avoids the misleading "before=1 / after=1" count caused by the always-present shell process.
    $explorerCount = (Get-Process explorer | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -ne '' } | Measure-Object).Count
    Write-Host (" INFO - Explorer folder windows before close={0}" -f $explorerCount)

    Get-Process explorer |
        Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -ne '' } |
        ForEach-Object { $_.CloseMainWindow() | Out-Null }

    Start-Sleep -Milliseconds 700

    # Fallback close for any remaining explorer folder windows.
    try {
        $shell = New-Object -ComObject Shell.Application
        foreach ($w in $shell.Windows()) {
            if ($w -and $w.FullName -and ($w.FullName -like "*explorer.exe")) {
                $w.Quit()
            }
        }
    }
    catch {
        Write-Host " ERROR - stop_perfStress_background fallback close failed."
    }

    $remainingExplorer = (Get-Process explorer | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -ne '' } | Measure-Object).Count
    Write-Host (" INFO - Explorer folder windows after close={0}" -f $remainingExplorer)
}

# Stop background processes launched by perf_stress setup.
Stop-PerfStressProcesses

$remainingStress = (Get-CimInstance Win32_Process |
    Where-Object {
        ($_.CommandLine -and ($_.CommandLine -match "percentile_stress\.py|install_python\.ps1")) -or
        ($_.Name -match "(?i)^(python|py|pythonw)\.exe$" -and $_.CommandLine -and ($_.CommandLine -match "percentile_stress\.py"))
    } |
    Measure-Object).Count

Write-Host (" INFO - Remaining stress candidates after stop={0}" -f $remainingStress)

# Close open File Explorer windows so reruns start clean.
Close-ExplorerWindows

Write-Host " INFO - stop_perfStress_background completed"

exit 0


