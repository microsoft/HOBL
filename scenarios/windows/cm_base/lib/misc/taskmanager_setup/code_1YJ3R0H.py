# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging

from scenarios.windows.cm_base.background_cleanup import run_powershell


def run(scenario):
    """Set and verify Task Manager's saved left-half placement before measurement."""
    logging.debug('Executing code block: code_1YJ3R0H.py')
    run_powershell(scenario, """
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class TaskManagerWindow {
    [StructLayout(LayoutKind.Sequential)]
    public struct Rect {
        public int Left, Top, Right, Bottom;
    }

    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr window, int command);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetWindowPos(
        IntPtr window, IntPtr insertAfter, int x, int y, int width, int height, uint flags);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool GetWindowRect(IntPtr window, out Rect rect);
}
'@

# Use physical coordinates consistently on monitors with non-default scaling.
if ([TaskManagerWindow]::SetThreadDpiAwarenessContext([IntPtr](-4)) -eq [IntPtr]::Zero) {
    $errorCode = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
    throw " ERROR - Could not enable per-monitor DPI awareness (Win32 error $errorCode)."
}
$taskManagerPath = (Get-Command Taskmgr.exe -CommandType Application -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $taskManagerPath -PathType Leaf)) {
    throw " ERROR - Task Manager executable not found: $taskManagerPath"
}
$area = $null
$width = 0
for ($attempt = 0; $attempt -lt 2; $attempt++) {
    $phase = if ($attempt -eq 0) { 'initial setup' } else { 'reopen verification' }
    Write-Host "Launching Task Manager for ${phase}: $taskManagerPath"
    Start-Process -FilePath $taskManagerPath -ErrorAction Stop

    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $process = $null
    while ($timer.Elapsed.TotalSeconds -lt 15) {
        $windows = @(Get-Process | Where-Object {
            $_.ProcessName -eq 'Taskmgr' -and $_.MainWindowHandle -ne [IntPtr]::Zero
        })
        if ($windows.Count -gt 1) {
            throw " ERROR - Multiple Task Manager windows found. Close extra windows and retry setup."
        }
        if ($windows.Count -eq 1) {
            $process = $windows[0]
            break
        }
        Start-Sleep -Milliseconds 200
    }
    if ($null -eq $process) {
        throw " ERROR - Task Manager launch timed out during ${phase}: no main window appeared within 15 seconds."
    }

    try {
        $window = $process.MainWindowHandle
        if ($attempt -eq 0) {
            [TaskManagerWindow]::ShowWindow($window, 9) | Out-Null
            $area = [System.Windows.Forms.Screen]::FromHandle($window).WorkingArea
            $width = [int][Math]::Floor($area.Width / 2)
            Write-Host "Positioning Task Manager on the left: x=$($area.Left), y=$($area.Top), width=$width, height=$($area.Height)"
            # Keep the existing Z-order and focus while moving the restored window.
            if (-not [TaskManagerWindow]::SetWindowPos(
                $window, [IntPtr]::Zero, $area.Left, $area.Top, $width, $area.Height, 0x0014)) {
                $errorCode = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
                throw " ERROR - Could not position Task Manager (Win32 error $errorCode)."
            }
        }

        $timer.Restart()
        do {
            $rect = New-Object TaskManagerWindow+Rect
            if (-not [TaskManagerWindow]::GetWindowRect($window, [ref]$rect)) {
                $errorCode = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
                throw " ERROR - Could not read Task Manager window bounds (Win32 error $errorCode)."
            }
            $positioned = $rect.Left -eq $area.Left -and $rect.Top -eq $area.Top -and
                ($rect.Right - $rect.Left) -eq $width -and
                ($rect.Bottom - $rect.Top) -eq $area.Height
            if ($positioned) { break }
            Start-Sleep -Milliseconds 100
        } while ($timer.Elapsed.TotalSeconds -lt 3)
        if (-not $positioned) {
            if ($attempt -eq 1) {
                throw " ERROR - Task Manager did not remember its left-half size and position after reopening."
            }
            throw " ERROR - Task Manager did not fit the left half of the monitor's work area."
        }
        Write-Host "Task Manager left-half bounds verified during $phase."
    } finally {
        $process.Refresh()
        if (-not $process.HasExited) {
            if (-not $process.CloseMainWindow()) {
                throw " ERROR - Task Manager did not accept a normal close request."
            }
            if (-not $process.WaitForExit(5000)) {
                throw " ERROR - Task Manager did not exit within 5 seconds. Close it before running the workload."
            }
        }
    }
}
Write-Host "Task Manager saved placement verified; application closed before measurement."
""", timeout=60)