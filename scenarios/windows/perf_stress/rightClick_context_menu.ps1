# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Performs a true mouse right-click in the active File Explorer window.
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class Win32 {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int X, int Y);

    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
}
"@

$explorer = Get-Process explorer -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowHandle -ne 0 } |
    Sort-Object StartTime -Descending |
    Select-Object -First 1

if (-not $explorer) {
    exit 0
}

[Win32]::SetForegroundWindow([IntPtr]$explorer.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 150

$rect = New-Object Win32+RECT
[Win32]::GetWindowRect([IntPtr]$explorer.MainWindowHandle, [ref]$rect) | Out-Null

# Position over common file-list area where selected item is expected.
$x = [int]($rect.Left + (($rect.Right - $rect.Left) * 0.42))
$y = [int]($rect.Top + (($rect.Bottom - $rect.Top) * 0.36))
[Win32]::SetCursorPos($x, $y) | Out-Null

Start-Sleep -Milliseconds 120
# Click once to ensure focus/selection in file list, then right-click target item.
[Win32]::mouse_event(0x0002, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 40
[Win32]::mouse_event(0x0004, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 80
[Win32]::mouse_event(0x0008, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 60
[Win32]::mouse_event(0x0010, 0, 0, 0, [UIntPtr]::Zero)
