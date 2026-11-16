# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$wallpaper = "ColorChecker3000x2000.png",
    [string]$Brightness = "65",
    [string]$telemetry_enabled = "0"
)

Push-Location -Path (Split-Path $MyInvocation.MyCommand.Path -Parent)

# Disable Surface telemetry service on pre-production devices, if it exists.
sc.exe delete SurfaceDiagData

# Disable sleep
# Sleep after
powercfg -SETDCVALUEINDEX scheme_balanced sub_sleep 29f6c1db-86da-48c5-9fdb-f2b67b1f44da 0
powercfg -SETACVALUEINDEX scheme_balanced sub_sleep 29f6c1db-86da-48c5-9fdb-f2b67b1f44da 0
# Hibernate after
powercfg -SETDCVALUEINDEX scheme_balanced sub_sleep 9d7815a6-7ee4-497e-8888-515a05f02364 0
powercfg -SETACVALUEINDEX scheme_balanced sub_sleep 9d7815a6-7ee4-497e-8888-515a05f02364 0
# System unattended sleep timeout
powercfg -SETDCVALUEINDEX scheme_balanced sub_sleep 7bc4a2f9-d8fc-4469-b07b-33eb785aaca0 0
powercfg -SETACVALUEINDEX scheme_balanced sub_sleep 7bc4a2f9-d8fc-4469-b07b-33eb785aaca0 0
# Dim display after
powercfg -SETDCVALUEINDEX scheme_balanced sub_video 17aaa29b-8b43-4b94-aafe-35f64daaf1ee 0
powercfg -SETACVALUEINDEX scheme_balanced sub_video 17aaa29b-8b43-4b94-aafe-35f64daaf1ee 0
# Turn off display after
powercfg -SETDCVALUEINDEX scheme_balanced sub_video 3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e 0
powercfg -SETACVALUEINDEX scheme_balanced sub_video 3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e 0
powercfg -SETACTIVE scheme_balanced

#  Disable the ALS for consistent backlight
Powercfg.exe -setacvalueindex scheme_current sub_video adaptbright 0
Powercfg.exe -setdcvalueindex scheme_current sub_video adaptbright 0
Powercfg.exe -setactive scheme_current

#  Build NGen Cache:
start-process "$env:windir\Microsoft.NET\Framework\v4.0.30319\ngen.exe" ("ExecuteQueuedItems") -Wait

#  Set desktop background image
Add-Type @"
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32;
namespace Wallpaper
{
public enum Style : int
{
Center, Stretch
}
public class Setter {
public const int SetDesktopWallpaper = 20;
public const int UpdateIniFile = 0x01;
public const int SendWinIniChange = 0x02;
[DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Auto)]
private static extern int SystemParametersInfo (int uAction, int uParam, string lpvParam, int fuWinIni);
public static void SetWallpaper ( string path, Wallpaper.Style style ) {
SystemParametersInfo( SetDesktopWallpaper, 0, path, UpdateIniFile | SendWinIniChange );
RegistryKey key = Registry.CurrentUser.OpenSubKey("Control Panel\\Desktop", true);
switch( style )
{
case Style.Stretch :
key.SetValue(@"WallpaperStyle", "2") ; 
key.SetValue(@"TileWallpaper", "0") ;
break;
case Style.Center :
key.SetValue(@"WallpaperStyle", "1") ; 
key.SetValue(@"TileWallpaper", "0") ; 
break;
}
key.Close();
}
}
}
"@

$Path = (split-path -parent $MyInvocation.MyCommand.Definition) + "\DesktopImages\" + "$wallpaper"
$Style = 'Stretch'
[Wallpaper.Setter]::SetWallpaper( $Path, $Style )

#  Set screen brightness
    # AC Brightness Level
powercfg -SETACVALUEINDEX scheme_balanced SUB_VIDEO aded5e82-b909-4619-9949-f5d71dac0bcb 65
    # DC Brightness Level
powercfg -SETDCVALUEINDEX scheme_balanced SUB_VIDEO aded5e82-b909-4619-9949-f5d71dac0bcb 65
    # Select Correct Profile
powercfg -SETACTIVE scheme_balanced

# Opt out diagtrack and UTC for non-critical events 
if ($telemetry_enabled -eq "0"){
    Copy-Item .\telemetry.ASM-WindowsDefault.json $env:ProgramData\Microsoft\diagnosis\sideload -Force
    Copy-Item .\utc.app.json $env:ProgramData\Microsoft\diagnosis\sideload -Force
}

Pop-Location
