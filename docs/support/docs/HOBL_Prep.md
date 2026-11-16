# Prep Details
  
The goal of HOBL is to test a device in the same way that a typical user would use it, and therefore attempts to minimize any changes from the default setup of the device.  However, some changes need to be made in order to facilitate reliable automation.  Below is the list of scenarios and tools that make such changes to the system, and the changes they make.

Also note that when "Check Preps" is selected on the New Job page (which it is by default), a "prep" scenario will be inserted into the submitted job that will run the individual prep scenarios required by any and all test scenarios in the job.  If a prep scenario has already been run then it will be skipped an not run again until the DUT is re-imaged.

## dut_setup for Windows
This is run to set up the device whenever it is re-imaged, either explicitly by the user or automatically as part of os_install.  It may also be automatically rerun by "prep" if the current version in the repo is newer than the version on the DUT.  Dut_setup makes the following changes to the system:

### Install powershell 7
This allows us to be sure what version of powershell is on the device and can use appropriately compatible commands.
```
msiexec.exe /package %usb_drive%\%dut_setup_folder%\pwsh\PowerShell-7.6.4-win-x64.msi /passive
```

### Set polling period for powersnap telemetry to 60s
[Powersnap](https://learn.microsoft.com/en-us/windows/win32/power/powersnap) is used by various tools, such as "power_light" and "power_heavy" to get detailed traces of power consumption information.  A 60s polling rate gives us good detial without impacting power consumption itself.

```
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\SRUM\Telemetry" /v IntervalTimerInSeconds /t REG_DWORD /d 60 /f > null 2>&1
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\SRUM\Telemetry" /v MinimumIntervalInSeconds /t REG_DWORD /d 60 /f > null 2>&1
```

### Set polling period for onboard power monitor chips to 30s active and 120s standby
If a device has onboard powr monitoring chips, polling rate is set high enough to be valuable without impacting power consumption itself.
```
reg add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SRUM\\Parameters" /v Tier1Period /t REG_DWORD /d 30 /f > null 2>&1   
reg add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SRUM\\Parameters" /v Tier2Period /t REG_DWORD /d 120 /f > null 2>&1   
reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\intelpep\\Parameters" /v ActiveAccountingIntervalInMs /t REG_DWORD /d 0x2710 /f > null 2>&1   
```

### Create Personalization folder in the registry
This is necessary to be able to change some personalization settings when Windows hasn't been activated.
```
reg add HKLM\Software\Policies\Microsoft\Windows\Personalization /f > null 2>&1
```

### Settings to disable lock screen on sleep
So that credentials do not need to be entered when resuming from sleep sessions.
```
reg add HKLM\Software\Policies\Microsoft\Windows\Personalization /v NolockScreen /t REG_DWORD /d 1 /f > null 2>&1
```

### Disable Windows Hello sign-in options
So that we can ensure automation can consistently auto-login.
```
reg add HKLM\SOFTWARE\Microsoft\PolicyManager\default\Settings\AllowSignInOptions /v value /t REG_DWORD /d 0 /f > null 2>&1
```

### Disable "Require password on wake" from shutdown/hibernate
So that automation can resume from hibernate without needing credentials.
```
powercfg -setdcvalueindex 381b4222-f694-41f0-9685-ff5bb260df2e fea3413e-7e05-4911-9a71-700331f1c294 0e796bdb-100d-47d6-a2d5-f7d2daa51f51 0
powercfg -setacvalueindex 381b4222-f694-41f0-9685-ff5bb260df2e fea3413e-7e05-4911-9a71-700331f1c294 0e796bdb-100d-47d6-a2d5-f7d2daa51f51 0
```

### Disable Sleep After
To prevent the device from going to sleep when idle.
```
powercfg -SETDCVALUEINDEX scheme_balanced sub_sleep 29f6c1db-86da-48c5-9fdb-f2b67b1f44da 0
powercfg -SETACVALUEINDEX scheme_balanced sub_sleep 29f6c1db-86da-48c5-9fdb-f2b67b1f44da 0
```

### Disable Hibernate After
To prevent the device from going into hibernate when idle.
```
powercfg -SETDCVALUEINDEX scheme_balanced sub_sleep 9d7815a6-7ee4-497e-8888-515a05f02364 0
powercfg -SETACVALUEINDEX scheme_balanced sub_sleep 9d7815a6-7ee4-497e-8888-515a05f02364 0
```

### Disable System Unattended Sleep Timeout
To prevent the device from going to sleep when left unattended.
```
powercfg -SETDCVALUEINDEX scheme_balanced sub_sleep 7bc4a2f9-d8fc-4469-b07b-33eb785aaca0 0
powercfg -SETACVALUEINDEX scheme_balanced sub_sleep 7bc4a2f9-d8fc-4469-b07b-33eb785aaca0 0
```

### Disable Dim Display After
To prevent the display dimming when idle.
```
powercfg -SETDCVALUEINDEX scheme_balanced sub_video 17aaa29b-8b43-4b94-aafe-35f64daaf1ee 0
powercfg -SETACVALUEINDEX scheme_balanced sub_video 17aaa29b-8b43-4b94-aafe-35f64daaf1ee 0
```

### Disable Turn off Display After
To prevent the display turning off when idle.
```
powercfg -SETDCVALUEINDEX scheme_balanced sub_video 3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e 0
powercfg -SETACVALUEINDEX scheme_balanced sub_video 3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e 0
```

### Enable hibernate
This allows automation to resume after a full battery rundown.
```
powercfg /hibernate on
```

### Enable RTC wake timer
This allows automation to set a timer to automatically wake from hibernate at the end of a full rundown.
```
powercfg -SETDCVALUEINDEX scheme_current sub_sleep RTCWAKE 1
powercfg -SETACVALUEINDEX scheme_current sub_sleep RTCWAKE 1
powercfg -SETACTIVE scheme_balanced
```

### Disable Low Battery Notification
Because the popup can interfere with UI automation.
```
powercfg -SETDCVALUEINDEX SCHEME_CURRENT sub_battery BATFLAGSLOW 0
powercfg -SETACVALUEINDEX SCHEME_CURRENT sub_battery BATFLAGSLOW 0
powercfg -SETDCVALUEINDEX SCHEME_CURRENT sub_battery BATFLAGSCRIT 0
powercfg -SETACVALUEINDEX SCHEME_CURRENT sub_battery BATFLAGSCRIT 0
```

### Set action at critical battery level
On AC don't do anything, on DC hibernate.  This is critical for waking properly after a full rundown.
```
powercfg -SETDCVALUEINDEX SCHEME_CURRENT sub_battery BATACTIONCRIT 2
powercfg -SETACVALUEINDEX SCHEME_CURRENT sub_battery BATACTIONCRIT 0
```

### Set action at low battery level
Don't do anything, let it go to Critical.  This should be default.
```
powercfg -SETDCVALUEINDEX SCHEME_CURRENT sub_battery BATACTIONLOW 0
powercfg -SETACVALUEINDEX SCHEME_CURRENT sub_battery BATACTIONLOW 0
```

###  Disable adaptive screen brightness
This prevents varying measurements resulting from different ambient light conditions.
```
Powercfg -setacvalueindex scheme_current sub_video adaptbright 0
Powercfg -setdcvalueindex scheme_current sub_video adaptbright 0
Powercfg -setactive scheme_current
```

### Set AC and DC screen brightness Level to 65%
An initial standardization, but not substitute for actual screen brightness calibration to 150 nits.
```
powercfg -SETACVALUEINDEX scheme_balanced SUB_VIDEO aded5e82-b909-4619-9949-f5d71dac0bcb 65
powercfg -SETDCVALUEINDEX scheme_balanced SUB_VIDEO aded5e82-b909-4619-9949-f5d71dac0bcb 65
```

### Set dut to sleep on lid closure
```
powercfg -SETACVALUEINDEX scheme_balanced SUB_BUTTONS 5ca83367-6e45-459f-a27b-476b1d01c936 001
powercfg -SETDCVALUEINDEX scheme_balanced SUB_BUTTONS 5ca83367-6e45-459f-a27b-476b1d01c936 001
powercfg -SETACTIVE scheme_balanced
```

### Prevent pen First Run Experience notification
Such indeterminate popups can interfere with automation and measurements.
```
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\PenWorkspace /v PenDetachFREComplete /t REG_DWORD /d 1 /f > null 2>&1
```

### Enable developer mode
Needed by WinAppDriver to do UI Automation.
```
reg add HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock /v AllowDevelopmentWithoutDevLicense /t REG_DWORD /d 1 /f
start ms-settings:developers
```

### Enable network drives mapped in privileged mode to be visible in normal mode, and vice versa
This allows a drive mapped by automation to be visible to an interactive user, primarily used by HOBL UI function to remote to DUT or Host.
```
reg add HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\Policies\System /v EnableLinkedConnections /t REG_DWORD /d 1 /f
```

### Enable location services
This is needed to be able to access Wi-Fi settings.
```
reg add HKLM\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location /v Value /t REG_SZ /d Allow /f
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location /v Value /t REG_SZ /d Allow /f
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location\NonPackaged /v Value /t REG_SZ /d Allow /f
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location /v Value /t REG_SZ /d Allow /f
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location\NonPackaged /v Value /t REG_SZ /d Allow /f

Attempt UI automation to enable location services, in case the reg keys didn't work.
Restart location service to apply changes:

echo Restarting location service...
net stop lfsvc >nul 2>&1
ping 127.0.0.1 -n 3 >nul
net start lfsvc >nul 2>&1

```

### Rename the device, if new name specified
```
  pwsh -Command rename-computer -NewName "%dut_name%" -ErrorAction SilentlyContinue
  pwsh -ExecutionPolicy Bypass -NoProfile %usb_drive%\%dut_setup_folder%\rename.ps1 -ComputerName "%dut_name%"
```

### Disable Windows Update and Configure Automatic Updates to Disabled
This is to make sure that system software doesn't change in the middle of a test pass, confusing results.
```
sc stop wuauserv
SCHTASKS /Change /TN "\Microsoft\Windows\WindowsUpdate\Scheduled Start" /Disable
reg add HKLM\SYSTEM\CurrentControlSet\Services\wuauserv /v Start /t REG_DWORD /d 3 /f
powershell.exe Set-ExecutionPolicy Unrestricted -Force
powershell.exe Set-PolicyFileEntry -Path "$env:windir\Sysnative\GroupPolicy\Machine\registry.pol" -Key SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU -ValueName NoAutoUpdate -Data 1 -Type DWord
powershell.exe Get-PolicyFileEntry -Path "$env:windir\Sysnative\GroupPolicy\Machine\registry.pol" -All
powershell.exe Set-PolicyFileEntry -Path "$env:windir\System32\GroupPolicy\Machine\registry.pol" -Key SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU -ValueName NoAutoUpdate -Data 1 -Type DWord
powershell.exe Get-PolicyFileEntry -Path "$env:windir\System32\GroupPolicy\Machine\registry.pol" -All
gpupdate
```

### Set up Wi-Fi
If Wi-Fi details are specified in the profile, then configure and connect to Wi-Fi.  This allows automation to continue after automated OS installation.
```
netsh wlan add profile filename=%usb_drive%%dut_setup_folder%\wifi.xml
netsh wlan connect name=%dut_wifi_name% interface="Wi-Fi"
netsh wlan set profileparameter name=%dut_wifi_name% connectionmode=auto
```

### Schedule task to reconnect Wi-Fi after reboot
This is to handle cases where a device crashes or shuts down during a scenario that disconnected Wi-Fi.
```
copy %usb_drive%\%dut_setup_folder%\connect_wifi_task.cmd %hobl_bin_path% /v /Y
SCHTASKS /Delete /TN connectWifi /F
SCHTASKS /Create /TN connectWifi /TR %hobl_bin_path%\connect_wifi_task.cmd /SC onlogon
```

### Installing .NET Windows Desktop Runtime
```
if "!dut_architecture!" EQU "arm64" (
    %usb_drive%\%dut_setup_folder%\dotnet\windowsdesktop-runtime-8.0.29-win-arm64.exe /quiet
) else (
    %usb_drive%\%dut_setup_folder%\dotnet\windowsdesktop-runtime-8.0.29-win-x64.exe /quiet
)
```

### Install web_replay certificates
These allow accessing secure websites in the Web Replay archive for web browsing scenarios.
```
pwsh.exe -ExecutionPolicy Bypass -NoProfile %usb_drive%\%dut_setup_folder%\web_replay\install_certs.ps1
```

### Create scheduled task for starting SimpleRemoteConsole on reboot
```
if "%dut_architecture%" EQU "arm64" (
    set this_string="%hobl_bin_path%\SimpleRemoteServer-arm64\start_admin_console.bat"
    set this_srs="%hobl_bin_path%\SimpleRemoteServer-arm64\SimpleRemoteConsole.exe"
) else (
    set this_string="%hobl_bin_path%\SimpleRemoteServer-x64\start_admin_console.bat"
    set this_srs="%hobl_bin_path%\SimpleRemoteServer-x64\SimpleRemoteConsole.exe"
)
```

### Open firewall for SimpleRemote and WinAppDriver
```
netsh advfirewall firewall delete rule name="SimpleRemoteConsole TCP"
netsh advfirewall firewall add rule name="SimpleRemoteConsole TCP" program=!this_srs! dir=in action=allow enable=yes localport=any protocol=TCP profile=public,private,domain
netsh advfirewall firewall delete rule name="SimpleRemoteConsole UDP"
netsh advfirewall firewall add rule name="SimpleRemoteConsole UDP" program=!this_srs! dir=in action=allow enable=yes localport=any protocol=UDP profile=public,private,domain

netsh advfirewall firewall delete rule name="Allow 4723,17556,5901,8020"
netsh advfirewall firewall add rule name="Allow 4723,17556,5901,8020" dir=in action=allow enable=yes localport=4723,17556,5901,8020 protocol=TCP profile=public,private,domain
netsh advfirewall firewall delete rule name="Allow ICMPv4"
netsh advfirewall firewall add rule name="Allow ICMPv4" dir=in action=allow enable=yes protocol=icmpv4:8,any profile=public,private,domain
```

### Register host name with DNS server
```
ipconfig /registerdns
```

## msa_prep
This is a common prep scenario run by the "prep" scenario, and sets the user account for the device.  Msa_prep makes the following changes to the system:

#### Set auto login MSA Account
```
reg add "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon" /v DefaultUserName /t REG_SZ /d ' + self.msa_account + ' /f > null 2>&1
reg add "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon" /v DefaultPassword /t REG_SZ /d ' + self.dut_password + ' /f > null 2>&1
reg add "HKLM\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon" /v AutoAdminlogon /t REG_SZ /d 1 /f > null 2>&1
```

#### Set user password to never expire
```
powershell Set-LocalUser -Name $env:UserName -PasswordNeverExpires 1
```

#### Turn off Surface notifications
```
reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings\\Microsoft.SurfaceHub_8wekyb3d8bbwe!App" /v Enabled /t REG_DWORD /d 0 /f > null 2>&1
```

System_prep is generally run at the beginning of a study (part of hobl and rundown_abl test plans), to quiesce the device and re-set any setting that may have a tendency to change on their own.  system_prep makes the following changes to the system:

## system_prep
System_prep is a common prep scenario run by the "prep" scenario and makes changes to facilitate reliable automation.  system_prep makes the following changes to the system:

### Set dark or light theme if specified
```
if theme == "dark":
    reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v SystemUsesLightTheme /t REG_DWORD /d 0 /f
    reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v AppsUseLightTheme /t REG_DWORD /d 0 /f
if theme == "light":
    reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v SystemUsesLightTheme /t REG_DWORD /d 1 /f
    reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v AppsUseLightTheme /t REG_DWORD /d 1 /f
```

### Enable file extensions in File Explorer
Just for ease of use.
```
reg add "HKCU\\software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" /v HideFileExt /t REG_DWORD /d 00000000 /f > null 2>&1
```

### Disable certain notifications that can interfere with execution:
```
reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\UserProfileEngagement" /v ScoobeSystemSettingEnabled /t REG_DWORD /d 0 /f > null 2>&1
reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" /v SubscribedContent-338389Enabled /t REG_DWORD /d 0 /f > null 2>&1
reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\ContentDeliveryManager" /v SubscribedContent-310093Enabled /t REG_DWORD /d 0 /f > null 2>&1
reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\PushNotifications" /v ToastEnabled /t REG_DWORD /d 0 /f > null 2>&1
```

### Align taskbar icons to the left
So that as tasks come and go the pinned icons don't change their position
```
reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" /v TaskbarAl /t REG_DWORD /d 0 /f > null 2>&1
```

### Disable expandable taskbar
```
reg add "HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced" /v ExpandableTaskbar /t REG_DWORD /d 0 /f > null 2>&1
```

### Disable Recall Popup
```
self._call(["cmd.exe", '/C reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\CloudExperienceHost\Intent\RecallNotice" /v RecallConsentPageShown /t REG_DWORD /d 1 /f > null 2>&1'])
```

### Set Edge to always play videos
```
powershell Set-PolicyFileEntry -Path "$env:windir\\' + system_path + '\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Edge -ValueName AutoplayAllowed -Data 1 -Type DWord
gpupdate /wait:1200
```

### Enable telemetry if specified
```
reg add "HKLM\\SOFTWARE\\Microsoft\\SQMClient" /v IsTestlab /t REG_DWORD /d 0 /f > null 2>&1
reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 3 /f > null 2>&1
reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\DataCollection" /v MaxTelemetryAllowed /t REG_DWORD /d 3 /f > null 2>&1
reg add "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection" /v AllowTelemetry /t REG_DWORD /d 3 /f > null 2>&1
powershell Set-PolicyFileEntry -Path "$env:windir\\' + system_path + '\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Windows\\DataCollection -ValueName AllowTelemetry -Data 3 -Type DWord
gpupdate /wait:1200
```

### Disable telemetry if specified (default)
```
reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Diagnostics\\DiagTrack\\TestHooks" /v SkipTelemetryServiceRules /t REG_DWORD /d 1 /f > null 2>&1   
reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Diagnostics\\DiagTrack\\TestHooks" /v SkipDownloadedSettings /t REG_DWORD /d 1 /f > null 2>&1   
```

### Enable hibernate if specified (default)
```
powercfg.exe /H ON
```

### Disable hibernate if specified
```
powercfg.exe /H OFF
powercfg.exe /setdcvalueindex scheme_current sub_presence STANDBYRESERVETIME 0
powercfg.exe /setdcvalueindex scheme_current sub_presence STANDBYRESETPERCENT 0
powercfg.exe /setdcvalueindex scheme_current sub_presence NSENINPUTPRETIME 0
powercfg.exe /setdcvalueindex scheme_current sub_presence NSENINPUTPRETIME 0
powercfg.exe /setdcvalueindex scheme_current sub_presence STANDBYBUDGETGRACEPERIOD 0
powercfg.exe /setdcvalueindex scheme_current sub_presence USERPRESENCEPREDICTION 0
powercfg.exe /setdcvalueindex scheme_current sub_presence standbybudgetpercent 0
powercfg.exe /setdcvalueindex scheme_current sub_presence STANDBYRESERVEGRACEPERIOD 0
```

### Disable sleep after
```
powercfg -SETDCVALUEINDEX scheme_balanced sub_sleep 29f6c1db-86da-48c5-9fdb-f2b67b1f44da 0
powercfg -SETACVALUEINDEX scheme_balanced sub_sleep 29f6c1db-86da-48c5-9fdb-f2b67b1f44da 0
```
### Disable hibernate after
```
powercfg -SETDCVALUEINDEX scheme_balanced sub_sleep 9d7815a6-7ee4-497e-8888-515a05f02364 0
powercfg -SETACVALUEINDEX scheme_balanced sub_sleep 9d7815a6-7ee4-497e-8888-515a05f02364 0
```
### Disable system unattended sleep timeout
```
powercfg -SETDCVALUEINDEX scheme_balanced sub_sleep 7bc4a2f9-d8fc-4469-b07b-33eb785aaca0 0
powercfg -SETACVALUEINDEX scheme_balanced sub_sleep 7bc4a2f9-d8fc-4469-b07b-33eb785aaca0 0
```
### Disable dim display after
```
powercfg -SETDCVALUEINDEX scheme_balanced sub_video 17aaa29b-8b43-4b94-aafe-35f64daaf1ee 0
powercfg -SETACVALUEINDEX scheme_balanced sub_video 17aaa29b-8b43-4b94-aafe-35f64daaf1ee 0
```
### Disable turn off display after
```
powercfg -SETDCVALUEINDEX scheme_balanced sub_video 3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e 0
powercfg -SETACVALUEINDEX scheme_balanced sub_video 3c0bc021-c8a8-4e07-a973-6b14cbcb2b7e 0
powercfg -SETACTIVE scheme_balanced
```

### Build Defender Cache to minimize Defender running during test
```
start-process "c:\program files\Windows Defender\mpcmdrun.exe" ("BuildSFC -Timeout 7200000") -Wait
```

###  Disable the ALS for consistent backlight
```
Powercfg.exe -setacvalueindex scheme_current sub_video adaptbright 0
Powercfg.exe -setdcvalueindex scheme_current sub_video adaptbright 0
Powercfg.exe -setactive scheme_current
```

###  Build NGen Cache to minimize background activity during test
```
start-process "$env:windir\Microsoft.NET\Framework\v4.0.30319\ngen.exe" ("ExecuteQueuedItems") -Wait
```

###  Set desktop background image
```
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
```

### Set AC brightness Level
```
powercfg -SETACVALUEINDEX scheme_balanced SUB_VIDEO aded5e82-b909-4619-9949-f5d71dac0bcb 100
```
### Set DC brightness Level
```
powercfg -SETDCVALUEINDEX scheme_balanced SUB_VIDEO aded5e82-b909-4619-9949-f5d71dac0bcb 65
```
### Set Balanced profile
```
powercfg -SETACTIVE scheme_balanced
```

### Opt out diagtrack and UTC for non-critical events 
```
if ($telemetry_enabled -eq "0"){
    Copy .\telemetry.ASM-WindowsDefault.json $env:ProgramData\Microsoft\diagnosis\sideload -Force
    Copy .\utc.app.json $env:ProgramData\Microsoft\diagnosis\sideload -Force
}
```

### Synchronize clock
Clocks on the DUT and Host need to be synchronized for automation to work properly.  This code enables automatic time zone and clock updates, and triggers a sync.
```
reg add "HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\tzautoupdate" /v Start /t REG_DWORD /d 00000003 /f
reg add "HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\W32Time\\Parameters" /v Type /t REG_SZ /d NTP /f
net start w32time
w32tm /resync
net stop w32time

```

## process_idle_tasks
Preforms various tasks that prepare a device for testing.  This includes queuing background maintenance tasks in Windows so they will not be running during tests.  To ensure consistent results, please run this scenario at least once per day on devices before starting a study.

### Build Defender Cache to prevent abnormal activity during testing
```
if ($run_idle_tasks -ne "0"){
    start-process "c:\program files\Windows Defender\mpcmdrun.exe" ("BuildSFC -Timeout 7200000") -Wait
}
```

###  Build NGen Cache:
```
start-process "$env:windir\Microsoft.NET\Framework\v4.0.30319\ngen.exe" ("ExecuteQueuedItems") -Wait
```

### Run ProcessIdleTasks to prevent abnormal activity during testing
```
if ($run_idle_tasks -ne "0"){
    start "rundll32.exe" ("advapi32.dll,ProcessIdleTasks") -Wait
}
```

## edge_install
Edge_install is part of the prep plans and installs the latest version of Edge.  Edge_install makes the following changes to the system:

### Make official builds only get 100% allocated configurations from the server.  Prevents flighting during test.
```
setx /m EDGE_FEATURE_OVERRIDES_SOURCE server_default
```
### Install administrative templates to be able to control settings
```
self._upload("utilities\\open_source\\MicrosoftEdgePolicyTemplates\\windows\\admx\\msedge.admx", "c:\\Windows\\PolicyDefinitions")
self._upload("utilities\\open_source\\MicrosoftEdgePolicyTemplates\\windows\\admx\\msedgeupdate.admx", "c:\\Windows\\PolicyDefinitions")
self._upload("utilities\\open_source\\MicrosoftEdgePolicyTemplates\\windows\\admx\\msedgewebview2.admx", "c:\\Windows\\PolicyDefinitions")
self._upload("utilities\\open_source\\MicrosoftEdgePolicyTemplates\\windows\\admx\\en-US\\msedge.adml", "c:\\Windows\\PolicyDefinitions\\en-US")
self._upload("utilities\\open_source\\MicrosoftEdgePolicyTemplates\\windows\\admx\\en-US\\msedgeupdate.adml", "c:\\Windows\\PolicyDefinitions\\en-US")
self._upload("utilities\\open_source\\MicrosoftEdgePolicyTemplates\\windows\\admx\\en-US\\msedgewebview2.adml", "c:\\Windows\\PolicyDefinitions\\en-US")
```
### Change Edge policies to: allow autoplay, prevent recommendations, hide First Run Experience, and disable updates
```
powershell.exe Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Edge -ValueName AutoplayAllowed -Data 1 -Type DWord
powershell.exe Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Edge -ValueName ShowRecommendationsEnabled -Data 0 -Type DWord
powershell.exe Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Edge -ValueName HideFirstRunExperience -Data 1 -Type DWord
powershell.exe Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\Edge -ValueName HideRestoreDialogEnabled -Data 1 -Type DWord
powershell.exe Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\EdgeUpdate -ValueName AutoUpdateCheckPeriodMinutes -Data 0 -Type DWord
powershell.exe Set-PolicyFileEntry -Path "$env:windir\\system32\\GroupPolicy\\Machine\\registry.pol" -Key SOFTWARE\\Policies\\Microsoft\\EdgeUpdate -ValueName UpdateDefault -Data 0 -Type DWord
cmd.exe /C gpupdate /wait:1200
```

### Set reg key to not disable popups and disable offer to save passwords popup
```
cmd.exe /C reg add "HKCU\\SOFTWARE\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Storage\\microsoft.microsoftedge_8wekyb3d8bbwe\\MicrosoftEdge\\New Windows" /v PopupMgr /t REG_SZ /d no /f   
cmd.exe /C reg add "HKCU\\SOFTWARE\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Storage\\microsoft.microsoftedge_8wekyb3d8bbwe\\MicrosoftEdge\\Main" /v "FormSuggest passwords" /t REG_SZ /d no /f   
```

### Set reg key to prevent full screen notification
```
cmd.exe /C reg add "HKCU\\SOFTWARE\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Storage\\microsoft.microsoftedge_8wekyb3d8bbwe\\MicrosoftEdge\\FullScreen\\AllowDomains" /v netflix.com /t REG_DWORD /d 1 /f   
cmd.exe /C reg add "HKCU\\SOFTWARE\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Storage\\microsoft.microsoftedge_8wekyb3d8bbwe\\MicrosoftEdge\\FullScreen\\AllowDomains" /v youtube.com /t REG_DWORD /d 1 /f   
```

### Set reg key to turn off opening apps for certain sites, such as Facebook
```
cmd.exe /C reg add "HKCU\\SOFTWARE\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Storage\\microsoft.microsoftedge_8wekyb3d8bbwe\\MicrosoftEdge\\AppLinks" /v Enabled /d 0 /f 
```

### Disable auto updating of Chrome and Edge
```
cmd.exe /C reg add "HKLM\\Software\\Policies\\Microsoft\\EdgeUpdateDev" /v AutoUpdateCheckPeriodMinutes /d 0 /f
cmd.exe /C reg add "HKLM\\Software\\WOW6432Node\\Microsoft\\EdgeUpdateDev" /v AutoUpdateCheckPeriodMinutes /t REG_DWORD /d 0 /f
cmd.exe /C reg add "HKLM\\Software\\WOW6432Node\\Microsoft\\EdgeUpdateDev" /v IsEnrolledToDomain /t REG_DWORD /d 1 /f
```

## web_prep
### Reset profile to default settings
Differences in Home page and New Tab page layouts can have a significant impact, so to ensure consistency across users we revert to default settings.

### Set cache clearing for "All time" and clear
Because the web test loads the exact same web content over and over, it would get unrealistically high cache hit rates if we didn't clear the cache.  Instead, we achieve representative browser caching activity by going to the same sites multiple times with different content within the test.

## office_install
Office_install is part of the prep plans and installs the specified version of Microsoft 365.  Office makes frequent UI changes, so a given version of HOBL only supports a specific version of Office.  Office_install makes the following changes to the system:

### Disable the activation nag so that the free trial can be used
Note that this prevents the ability to manually activate.  If activation is needed, then run this office_install again with the "activate" parameter set to 1, which will revert this registry setting.
```
reg add HKLM\\SOFTWARE\\Microsoft\\Office\\16.0\\Common\\Licensing /v DisableActivationUI /t REG_DWORD /f /d 00000001
reg add HKLM\\SOFTWARE\\Wow6432Node\\Microsoft\\Office\\16.0\\Common\\Licensing /v DisableActivationUI /t REG_DWORD /f /d 00000001
```

### Disable OneNote inking mode
This is to get consistency between devices with pens and those without.
```
reg add HKCU\\SOFTWARE\\Microsoft\\Office\\16.0\\OneNote\\Options /v FullPageModeOnPenUndock /t REG_DWORD /f /d 00000000
```

### Force Fluent UI update
This is to ensure consistent UI layout among users.
```
reg add HKCU\\Software\\Microsoft\\Office\\16.0\\Common\\ExperimentEcs\\Overrides /v Microsoft.Office.UXPlatform.FluentSVRefresh /t REG_SZ /d true /f
```

### Use System Theme
By default, make the office theme coincide with the system theme (light vs dark).  The office theme can be overriden in productivity_prep.
```
reg add "HKCU\\SOFTWARE\\Microsoft\\Office\\16.0\\Common" /v "UI Theme" /t REG_DWORD /d 6 /f
```

## onedrive_prep
### Reset File Explorer navigation pane to default size, to facilitate UI automation
```
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Modules\GlobalSettings\Sizer /v PageSpaceControlSizer /t REG_BINARY /d a0000000010000000000000056050000 /f
```
### Prevent "Deleted files are removed everywhere" reminder
```
reg add HKLM\SOFTWARE\Policies\Microsoft\OneDrive /v DisableFirstDeleteDialog /t REG_DWORD /d 1 /f
```
### Prevent mass delete popup
```
reg add HKCU\Software\Microsoft\OneDrive\Accounts\Personal /v MassDeleteNotificationDisabled /t REG_DWORD /d 1 /f
```
### Prevent first delete popup
```
reg add HKCU\Software\Microsoft\OneDrive /v FirstDeleteDialogsShown /t REG_DWORD /d 1 /f
```
### In OneDrive app, change Sync settings
```
Uncheck "battery saver mode"
Uncheck "metered"
```
### In OneDrive app, change Notificatoin settings
```
Uncheck "Notify me when syncing is paused"
Uncheck "share with me or edit my shared"
Uncheck "files are deleted in the cloud"
Uncheck "memories"
Uncheck "removed from the cloud"
```

## productivity_prep
Productivity_prep is part of the prep plans and prepares the Office apps, documents, and Outlook inbox for test.  Productivity_prep makes the following changes to the system:
### Pins Office icons to the task bar
This allows automation to open apps with a simple and more user-representative click

### Show file extensions (necessary for scripts to match certain window titles properly, like Word)
```
reg add HKCU\software\Microsoft\Windows\CurrentVersion\Explorer\Advanced /v HideFileExt /t REG_DWORD /f /d 00000000
```

### Hide Windows Search box to make sure there is room for all the taskbar icons we want to add
```
reg add HKCU\software\Microsoft\Windows\CurrentVersion\Search /v SearchboxTaskbarMode /t REG_DWORD /f /d 00000000
```

### Disable auto-recover on Office apps.  This is necessary to be able to recover from a mishap (dropped keys or mouse clicks) in a subsequent loop.
```
reg add HKCU\Software\Microsoft\office\16.0\excel\options /v AutoRecoverEnabled /t REG_DWORD /f /d 00000000
reg add HKCU\Software\Microsoft\office\16.0\PowerPoint\options /v SaveAutoRecoveryInfo /t REG_DWORD /f /d 00000000
reg add HKCU\Software\Microsoft\office\16.0\Word\options /v KeepUnsavedChanges /t REG_DWORD /f /d 00000000
```

### Disable Design Ideas suggestions in PowerPoint because of it's indeterminant behavior causing wild power variations.
```
reg add HKCU\Software\Microsoft\office\16.0\PowerPoint\options /v EnableSuggestionServiceUserSetting /t REG_DWORD /f /d 00000000
```

## store_prep
Store_prep is part of the prep plans and installs the latest app updates.  Afterwards, store_prep disables automatic app updates in the Settings menu to prevent updates from happening during test.

## adaptive_color_disable
"Adapative Color" is disabled in display settings because it can introduce variability due to the ambient light conditions that happen to be present during testing.