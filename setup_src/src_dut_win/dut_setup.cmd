set dut_setup_version=2.1

REM Copyright (c) Microsoft. All rights reserved.
REM Licensed under the MIT license. See LICENSE file in the project root for full license information.


echo off
setlocal EnableDelayedExpansion
cls

set usb_drive=%~dp0

if "%dut_name%" EQU "" (
    set dut_name=%1
)
if "%dut_wifi_name%" EQU "" (
    set dut_wifi_name=%2
)
if "%install_simpleremote%" EQU "" (
    set install_simpleremote=1
)

set "dut_password_safe=%dut_password%"
if defined dut_password_safe if not "%dut_password_safe:|=%"=="!dut_password_safe!" (
    set "dut_password_safe=%dut_password_safe:|=^|%"
)

@REM set reboot_prompt=1
echo DUT name             : %dut_name%
echo DUT password         : %dut_password_safe%
echo DUT wifi name        : %dut_wifi_name%
echo Reboot prompt        : %reboot_prompt%
echo Reboot               : %reboot%
echo Local Setup          : %local_setup%
echo Install SimpleRemote : %install_simpleremote%
echo Test Signing         : %test_signing%

rem current drive
rem for %%I in ("%dir%\..\..") do set "usb_drive=%%~fI"
echo Source Drive     : %usb_drive%
set hobl_bin_path=c:\hobl_bin
echo Target folder    : %hobl_bin_path%
set dut_setup_folder=dut_setup


rem system prep

set dut_architecture = "x64"
for /f "tokens=3 delims= " %%a in ('reg.exe query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Processor_Architecture ^| find "Processor_Architecture"') do set "dut_architecture=%%a"
if "%dut_architecture%" EQU "ARM64" (
    set dut_architecture=arm64
)
echo Dut Architecture: !dut_architecture!

@REM Install pwsh
if "!dut_architecture!" EQU "arm64" (
    echo Installing PowerShell arm64
    msiexec.exe /package %usb_drive%\%dut_setup_folder%\pwsh\PowerShell-7.5.4-win-arm64.msi /passive
) else (
    echo Installing PowerShell x64
    msiexec.exe /package %usb_drive%\%dut_setup_folder%\pwsh\PowerShell-7.5.4-win-x64.msi /passive
)
set PATH=%PATH%;C:\Program Files\PowerShell\7;C:\Program Files\PowerShell\7\Modules

@REM if "!dut_architecture!" EQU "arm64" (
@REM     rem Compensate for Windows not setting the system paths properly
@REM     rem setx path "%PATH%;C:\Windows;C:\Windows\System32;C:\Windows\System32\WindowsPowerShell\v1.0"
@REM     setx path "%PATH%;C:\Windows;C:\Windows\SysWow64;C:\Windows\SysWow64\WindowsPowerShell\v1.0;c:\Program Files\PowerShell\7;C:\Program Files\PowerShell\7\Modules"
@REM ) else (
@REM     setx path "%PATH%;C:\Windows;C:\Windows\System32;C:\Windows\System32\WindowsPowerShell\v1.0;c:\Program Files\PowerShell\7;C:\Program Files\PowerShell\7\Modules"
@REM )

rem Set polling rate for powersnap telemetry
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\SRUM\Telemetry" /v IntervalTimerInSeconds /t REG_DWORD /d 60 /f > null 2>&1
reg add "HKLM\Software\Microsoft\Windows NT\CurrentVersion\SRUM\Telemetry" /v MinimumIntervalInSeconds /t REG_DWORD /d 60 /f > null 2>&1

rem Set polling rate for Surface power monitor chips (after all reboots have happened)
reg add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SRUM\\Parameters" /v Tier1Period /t REG_DWORD /d 30 /f > null 2>&1   
reg add "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SRUM\\Parameters" /v Tier2Period /t REG_DWORD /d 120 /f > null 2>&1   
reg add "HKLM\\SYSTEM\\CurrentControlSet\\Services\\intelpep\\Parameters" /v ActiveAccountingIntervalInMs /t REG_DWORD /d 0x2710 /f > null 2>&1   

rem UAC Settings to never prompt for running programs in Admin mode
@REM reg add HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System /v ConsentPromptBehaviorAdmin /t REG_DWORD /d 0 /f > null 2>&1

rem Create Personalization folder in the registry
reg add HKLM\Software\Policies\Microsoft\Windows\Personalization /f > null 2>&1

rem Settings to disable lock screen on sleep
reg add HKLM\Software\Policies\Microsoft\Windows\Personalization /v NolockScreen /t REG_DWORD /d 1 /f > null 2>&1

rem Disable Windows Hello sign-in options so that we can ensure auto-login
reg add HKLM\SOFTWARE\Microsoft\PolicyManager\default\Settings\AllowSignInOptions /v value /t REG_DWORD /d 0 /f > null 2>&1

rem GUIDs to disable "Require password on wake" from shutdown/hibernate       
powercfg -setdcvalueindex 381b4222-f694-41f0-9685-ff5bb260df2e fea3413e-7e05-4911-9a71-700331f1c294 0e796bdb-100d-47d6-a2d5-f7d2daa51f51 0
powercfg -setacvalueindex 381b4222-f694-41f0-9685-ff5bb260df2e fea3413e-7e05-4911-9a71-700331f1c294 0e796bdb-100d-47d6-a2d5-f7d2daa51f51 0

rem Disable sleep
rem Sleep after
powercfg -SETDCVALUEINDEX scheme_balanced sub_sleep STANDBYIDLE 0
powercfg -SETACVALUEINDEX scheme_balanced sub_sleep STANDBYIDLE 0
rem Hibernate after
powercfg -SETDCVALUEINDEX scheme_balanced sub_sleep HIBERNATEIDLE 0
powercfg -SETACVALUEINDEX scheme_balanced sub_sleep HIBERNATEIDLE 0
rem System unattended sleep timeout
powercfg -SETDCVALUEINDEX scheme_balanced sub_sleep 7bc4a2f9-d8fc-4469-b07b-33eb785aaca0 0
powercfg -SETACVALUEINDEX scheme_balanced sub_sleep 7bc4a2f9-d8fc-4469-b07b-33eb785aaca0 0
rem Dim display after
powercfg -SETDCVALUEINDEX scheme_balanced sub_video 17aaa29b-8b43-4b94-aafe-35f64daaf1ee 0
powercfg -SETACVALUEINDEX scheme_balanced sub_video 17aaa29b-8b43-4b94-aafe-35f64daaf1ee 0
rem Turn off display after
powercfg -SETDCVALUEINDEX scheme_balanced sub_video VIDEOIDLE 0
powercfg -SETACVALUEINDEX scheme_balanced sub_video VIDEOIDLE 0
rem Enable Hibernate
powercfg /hibernate on
rem Enable RTC wake timer
powercfg -SETDCVALUEINDEX scheme_current sub_sleep RTCWAKE 1
powercfg -SETACVALUEINDEX scheme_current sub_sleep RTCWAKE 1
powercfg -SETACTIVE scheme_balanced

rem Disable Low and Critivcal Battery Notifications, as these will interfere with automation.
powercfg -SETDCVALUEINDEX SCHEME_CURRENT sub_battery BATFLAGSLOW 0
powercfg -SETACVALUEINDEX SCHEME_CURRENT sub_battery BATFLAGSLOW 0
powercfg -SETDCVALUEINDEX SCHEME_CURRENT sub_battery BATFLAGSCRIT 0
powercfg -SETACVALUEINDEX SCHEME_CURRENT sub_battery BATFLAGSCRIT 0

rem Set action at critical battery level.  On AC don't do anything, on DC hibernate.  This is critical for waking properly after a full rundown.
powercfg -SETDCVALUEINDEX SCHEME_CURRENT sub_battery BATACTIONCRIT 2
powercfg -SETACVALUEINDEX SCHEME_CURRENT sub_battery BATACTIONCRIT 0
rem Set action at low battery level.  Don't do anything, let it go to Critical.  This should be default.
powercfg -SETDCVALUEINDEX SCHEME_CURRENT sub_battery BATACTIONLOW 0
powercfg -SETACVALUEINDEX SCHEME_CURRENT sub_battery BATACTIONLOW 0

rem  Disable the ALS for consistent backlight
Powercfg -setacvalueindex scheme_current sub_video ADAPTBRIGHT 0
Powercfg -setdcvalueindex scheme_current sub_video ADAPTBRIGHT 0
Powercfg -setactive scheme_current

rem  Set screen brightness
rem AC Brightness Level
powercfg -SETACVALUEINDEX scheme_balanced SUB_VIDEO VIDEONORMALLEVEL 100
rem DC Brightness Level
powercfg -SETDCVALUEINDEX scheme_balanced SUB_VIDEO VIDEONORMALLEVEL 65
rem Select Correct Profile
powercfg -SETACTIVE scheme_balanced

rem set dut to sleep on lid closure
powercfg -SETACVALUEINDEX scheme_balanced SUB_BUTTONS 5ca83367-6e45-459f-a27b-476b1d01c936 001
powercfg -SETDCVALUEINDEX scheme_balanced SUB_BUTTONS 5ca83367-6e45-459f-a27b-476b1d01c936 001
powercfg -SETACTIVE scheme_balanced

rem regkey to set remote User Account Control (UAC)
@REM reg add HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\system /v LocalAccountTokenFilterPolicy /t REG_DWORD /d 1 /f

rem Prevent pen First Run Experience notification
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\PenWorkspace /v PenDetachFREComplete /t REG_DWORD /d 1 /f > null 2>&1

rem Reg key to location services.  This is needed to be able to access Wi-Fi settings.
reg add HKLM\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location /v Value /t REG_SZ /d Allow /f
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location /v Value /t REG_SZ /d Allow /f
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location\NonPackaged /v Value /t REG_SZ /d Allow /f
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location /v Value /t REG_SZ /d Allow /f
reg add HKCU\Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location\NonPackaged /v Value /t REG_SZ /d Allow /f

rem Reg key to enable develoger mode
reg add HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock /v AllowDevelopmentWithoutDevLicense /t REG_DWORD /d 1 /f
rem timeout /t 2
rem timeout doesn't work sometimes
ping 127.0.0.1 -n 2 > nul

rem Reg key to enable network drives mapped in privileged mode to be visible in normal mode, and vice versa
reg add HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\Policies\System /v EnableLinkedConnections /t REG_DWORD /d 1 /f

rem if simpleremote is running, kill it
taskkill /IM SimpleRemoteConsole.exe /f > null 2>&1


rem Attempt UI automation to enable location services
echo Attempting UI automation for location services...
pwsh.exe -ExecutionPolicy Bypass -NoProfile -Command "try { Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes; Start-Process 'ms-settings:privacy-location'; Start-Sleep 8; $w = [System.Windows.Automation.AutomationElement]::RootElement.FindFirst(4, (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, 'Settings'))); if ($w) { $toggles = @('DialogToggle', 'SystemSettings_CapabilityAccess_Location_UserGlobal_ToggleSwitch'); foreach ($toggleId in $toggles) { $t = $w.FindFirst(4, (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty, $toggleId))); if ($t) { $p = $t.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern); if ($p.Current.ToggleState -eq 'Off') { $p.Toggle(); Write-Host \"Enabled toggle: $toggleId\" } else { Write-Host \"Already enabled: $toggleId\" } } else { Write-Host \"Not found: $toggleId\" } } } else { Write-Host 'Settings window not found' }; Start-Sleep 2; Get-Process SystemSettings -EA 0 | Stop-Process -Force } catch { Write-Host 'UI automation failed, continuing setup' }"

rem Restart location service to apply changes
echo Restarting location service...
net stop lfsvc >nul 2>&1
ping 127.0.0.1 -n 3 >nul
net start lfsvc >nul 2>&1


rem Rename computer if dut_name variable is set
if "%dut_name%" NEQ "" (
    pwsh -Command rename-computer -NewName "%dut_name%" -ErrorAction SilentlyContinue
    pwsh -ExecutionPolicy Bypass -NoProfile %usb_drive%\%dut_setup_folder%\rename.ps1 -ComputerName "%dut_name%"
)

@REM Install dotnet
if "!dut_architecture!" EQU "arm64" (
    %usb_drive%\%dut_setup_folder%\dotnet\windowsdesktop-runtime-8.0.23-win-arm64.exe /quiet
) else (
    %usb_drive%\%dut_setup_folder%\dotnet\windowsdesktop-runtime-8.0.23-win-x64.exe /quiet
)

rem Scheduled task to minimize apps 60s after reboot.  This is particular for the Teams window that pops up after reboot.
rem powershell.exe -ExecutionPolicy Bypass -NoProfile %usb_drive%\minimize_task_setup.ps1 

REM rem Set auto login
REM set this_reg="HKLM\Software\Microsoft\Windows NT\CurrentVersion\Winlogon" 
REM if "%msa_account%" NEQ "" (
REM     reg add %this_reg% /v DefaultUserName /t REG_SZ /d %msa_account% /f > null 2>&1
REM     reg add %this_reg% /v DefaultPassword /t REG_SZ /d %dut_password% /f > null 2>&1
REM )
REM reg add %this_reg% /v AutoAdminlogon /t REG_SZ /d 1 /f > null 2>&1

rem Copy DeskTopImages, WindowsApplicationDrivers, and InputInject folders to dut hobl_bin folder
robocopy %usb_drive%\%dut_setup_folder%\DeskTopImages %hobl_bin_path%\DesktopImages /S /E
robocopy %usb_drive%\%dut_setup_folder%\WindowsApplicationDriver %hobl_bin_path%\WindowsApplicationDriver /S /E
@REM if "!dut_architecture!" EQU "arm64" (
@REM     robocopy %usb_drive%\%dut_setup_folder%\InputInject\ARM64\Release\net6 %hobl_bin_path%\InputInject /S /E
@REM ) else (
@REM     robocopy %usb_drive%\%dut_setup_folder%\InputInject\x64\Release\net6 %hobl_bin_path%\InputInject /S /E
@REM )
if not exist "%hobl_bin_path%\InputInject" (
    mkdir %hobl_bin_path%\InputInject
)
if "!dut_architecture!" EQU "arm64" (
    copy %usb_drive%\%dut_setup_folder%\InputInject\InputInject_win-arm64.zip %hobl_bin_path%\InputInject
    tar -xf %hobl_bin_path%\InputInject\InputInject_win-arm64.zip -C %hobl_bin_path%\InputInject
    del %hobl_bin_path%\InputInject\InputInject_win-arm64.zip
) else (
    copy %usb_drive%\%dut_setup_folder%\InputInject\InputInject_win-x64.zip %hobl_bin_path%\InputInject
    tar -xf %hobl_bin_path%\InputInject\InputInject_win-x64.zip -C %hobl_bin_path%\InputInject
    del %hobl_bin_path%\InputInject\InputInject_win-x64.zip
)
if not exist "%hobl_bin_path%\ScreenServer" (
    mkdir %hobl_bin_path%\ScreenServer
)
if "!dut_architecture!" EQU "arm64" (
    copy %usb_drive%\%dut_setup_folder%\ScreenServer\ScreenServer_win-arm64.zip %hobl_bin_path%\ScreenServer
    tar -xf %hobl_bin_path%\ScreenServer\ScreenServer_win-arm64.zip -C %hobl_bin_path%\ScreenServer
    del %hobl_bin_path%\ScreenServer\ScreenServer_win-arm64.zip
) else (
    copy %usb_drive%\%dut_setup_folder%\ScreenServer\ScreenServer_win-x64.zip %hobl_bin_path%\ScreenServer
    tar -xf %hobl_bin_path%\ScreenServer\ScreenServer_win-x64.zip -C %hobl_bin_path%\ScreenServer
    del %hobl_bin_path%\ScreenServer\ScreenServer_win-x64.zip
)

rem Copy PolicyFileEditor folder from dut_setup folder to dut Program Files folder
robocopy %usb_drive%\%dut_setup_folder%\PolicyFileEditor "C:\Program Files\WindowsPowerShell\Modules\PolicyFileEditor" /S /E
robocopy %usb_drive%\%dut_setup_folder%\PolicyFileEditor "C:\Program Files (x86)\WindowsPowerShell\Modules\PolicyFileEditor" /S /E

rem Copy dut ini file from dut_setup folder to dut desktop
set desktop_path=%UserProfile%\desktop
copy %usb_drive%\%dut_setup_folder%\*.ini %desktop_path% /v /Y

rem Copy MonitorPowerEvents.exe file from dut_setup folder to dut utilities folder
copy %usb_drive%\%dut_setup_folder%\MonitorPowerEvents.exe %hobl_bin_path% /v /Y

rem Copy RTCWakeCore from dut_setup folder to dut utilities folder
robocopy %usb_drive%\%dut_setup_folder%\RTCWakeCore %hobl_bin_path%\RTCWakeCore /S /E

rem Copy ScreenShot.exe file from dut_setup folder to dut utilities folder
if "!dut_architecture!" EQU "arm64" (
    copy %usb_drive%\%dut_setup_folder%\ScreenShot\ARM64\Release\ScreenShot.exe %hobl_bin_path% /v /Y
) else (
    copy %usb_drive%\%dut_setup_folder%\ScreenShot\x64\Release\ScreenShot.exe %hobl_bin_path% /v /Y
)

rem Copy charge_status.ps1 file from dut_setup folder to dut utilities folder
copy %usb_drive%\%dut_setup_folder%\charge_status.ps1 %hobl_bin_path% /v /Y

rem Copy web_replay helper files from dut_setup folder to dut utilities folder
mkdir %hobl_bin_path%\web_replay
copy %usb_drive%\%dut_setup_folder%\web_replay\set_args.ps1 %hobl_bin_path%\web_replay /v /Y
copy %usb_drive%\%dut_setup_folder%\web_replay\remove_args.ps1 %hobl_bin_path%\web_replay /v /Y

rem Install web_replay certs
pwsh.exe -ExecutionPolicy Bypass -NoProfile %usb_drive%\%dut_setup_folder%\web_replay\install_certs.ps1

rem Copy remote to dut utilities folder
mkdir %hobl_bin_path%\remote
copy %usb_drive%\%dut_setup_folder%\remote\wallpaper.png %hobl_bin_path%\remote /v /Y
if "!dut_architecture!" EQU "arm64" (
    copy %usb_drive%\%dut_setup_folder%\remote\arm64\remote.exe %hobl_bin_path%\remote /v /Y
) else (
    copy %usb_drive%\%dut_setup_folder%\remote\x64\remote.exe %hobl_bin_path%\remote /v /Y
)

rem Install VC++ 2015 runtime
%hobl_bin_path%\WindowsApplicationDriver\vc_redist.x86.exe /install /passive /norestart
rem Install VC++ 2017 runtime for x64 apps (needed by tee.exe)
rem %usb_drive%\%dut_setup_folder%\vc_redist.x64.exe /install /passive /norestart

rem Disabling Windows Update and Configuring Automatic Updates to Disabled
echo Disabling windows update.
sc stop wuauserv
SCHTASKS /Change /TN "\Microsoft\Windows\WindowsUpdate\Scheduled Start" /Disable
reg add HKLM\SYSTEM\CurrentControlSet\Services\wuauserv /v Start /t REG_DWORD /d 3 /f
pwsh.exe -Command Set-ExecutionPolicy Unrestricted -Force
powershell.exe -Command Set-ExecutionPolicy Unrestricted -Force
rem ARM now uses System32, but let's just update both paths to be safe.
pwsh.exe -Command Set-PolicyFileEntry -Path "$env:windir\Sysnative\GroupPolicy\Machine\registry.pol" -Key SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU -ValueName NoAutoUpdate -Data 1 -Type DWord
pwsh.exe -Command Get-PolicyFileEntry -Path "$env:windir\Sysnative\GroupPolicy\Machine\registry.pol" -All
pwsh.exe -Command Set-PolicyFileEntry -Path "$env:windir\System32\GroupPolicy\Machine\registry.pol" -Key SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU -ValueName NoAutoUpdate -Data 1 -Type DWord
pwsh.exe -Command Get-PolicyFileEntry -Path "$env:windir\System32\GroupPolicy\Machine\registry.pol" -All
gpupdate


@REM if "%local_setup%" NEQ "1" (
@REM     rem copy SimpleRemoteServer folder to %dut_setup_folder% folder
@REM     if "%dut_architecture%" EQU "arm64" (
@REM         echo Copying SimpleRemoteServer-arm64 folder
@REM         robocopy %usb_drive%\%dut_setup_folder%\SimpleRemoteServer-arm64 %hobl_bin_path%\SimpleRemoteServer-arm64 /S /E
@REM     ) else (
@REM         echo Copying SimpleRemoteServer-x64 folder
@REM         robocopy %usb_drive%\%dut_setup_folder%\SimpleRemoteServer-x64 %hobl_bin_path%\SimpleRemoteServer-x64 /S /E
@REM     )
@REM )

rem set up wifi
if "%dut_wifi_name%" NEQ "" (
    echo Connecting to %dut_wifi_name%

    if exist %usb_drive%\%dut_setup_folder%\wifi.xml (
        echo Adding profile
        netsh wlan add profile filename=%usb_drive%%dut_setup_folder%\wifi.xml
        echo Adding interface %dut_wifi_name%
        netsh wlan connect name=%dut_wifi_name% interface="Wi-Fi"
        echo Connecting %dut_wifi_name%
        netsh wlan set profileparameter name=%dut_wifi_name% connectionmode=auto nonBroadcast=yes

        rem scheduling task to connect wifi after reboot
        copy %usb_drive%\%dut_setup_folder%\connect_wifi_task.cmd %hobl_bin_path% /v /Y
        SCHTASKS /Delete /TN ConnectWiFi /F
@REM        SCHTASKS /Create /TN connectWifi /TR "%hobl_bin_path%\connect_wifi_task.cmd %dut_wifi_name%" /SC onlogon
        pwsh.exe -ExecutionPolicy Bypass -NoProfile %usb_drive%\%dut_setup_folder%\schedule_connect_wifi.ps1 -network %dut_wifi_name%

    ) else (
        echo Connect manually to desired wifi SSID and then press a key...
        pause
    )
    echo Waiting for 10 seconds for profile to connect
    rem timeout /t 10
    ping 127.0.0.1 -n 10 > nul
)

rem Navigate to the developer settings window
start /realtime ms-settings:developers

echo Waiting for 5 seconds while developer package is installed
rem timeout /t 5
ping 127.0.0.1 -n 5 > nul
taskkill /IM systemsettings.exe /f


rem Bypass feature to keep system from sleeping when using webdriver
setx WEBDRIVER_USE_DEFAULT_APP_PROCESS_BEHAVIOR 1

rem We only run the setup.exe from script (dut_setup or os_install scenario).  The dut_setup.exe expands simple remote directly to c:\hobl_bin on the DUT
rem so this installer doesn't need to be executed when called from dut_setup.exe.
if "%install_simpleremote%" EQU "1" (
    rem execute Simple_Remote installer (based on architecture from ini file)
    if "!dut_architecture!" EQU "arm64" (
        echo Installing simple remote-arm64
        if not exist "%hobl_bin_path%\SimpleRemoteServer_win-arm64" (
            mkdir %hobl_bin_path%\SimpleRemoteServer_win-arm64
        )
        copy %usb_drive%\%dut_setup_folder%\SimpleRemote\SimpleRemoteServer_win-arm64.zip %hobl_bin_path%
        tar -xf %hobl_bin_path%\SimpleRemoteServer_win-arm64.zip -C %hobl_bin_path%\SimpleRemoteServer_win-arm64
        del %hobl_bin_path%\SimpleRemoteServer_win-arm64.zip

    ) else (
        echo Installing simple remote-x64
        if not exist "%hobl_bin_path%\SimpleRemoteServer_win-x64" (
            mkdir %hobl_bin_path%\SimpleRemoteServer_win-x64
        )
        copy %usb_drive%\%dut_setup_folder%\SimpleRemote\SimpleRemoteServer_win-x64.zip %hobl_bin_path%
        tar -xf %hobl_bin_path%\SimpleRemoteServer_win-x64.zip -C %hobl_bin_path%\SimpleRemoteServer_win-x64
        del %hobl_bin_path%\SimpleRemoteServer_win-x64.zip
    )
)

if "%local_setup%" NEQ "1" (
    rem Create task for starting SimpleRemoteConsole based on dut architecture
    if "!dut_architecture!" EQU "arm64" (
        echo Creating StartSimple-arm64 task
        set this_string="%hobl_bin_path%\SimpleRemoteServer_win-arm64\start_admin_console_win-arm64.bat"
        set this_srs="%hobl_bin_path%\SimpleRemoteServer_win-arm64\SimpleRemoteConsole.exe"
    ) else (
        echo Creating StartSimple-x64 task
        set this_string="%hobl_bin_path%\SimpleRemoteServer_win-x64\start_admin_console_win-x64.bat"
        set this_srs="%hobl_bin_path%\SimpleRemoteServer_win-x64\SimpleRemoteConsole.exe"
    )
    pwsh.exe -ExecutionPolicy Bypass -NoProfile %usb_drive%\%dut_setup_folder%\simple_remote_setup.ps1 -cmd_string !this_string! 
    netsh.exe advfirewall firewall add rule name="SimpleRemoteConsole TCP" program=!this_srs! dir=in action=allow enable=yes localport=any protocol=TCP profile=public,private,domain
    netsh.exe advfirewall firewall add rule name="SimpleRemoteConsole UDP" program=!this_srs! dir=in action=allow enable=yes localport=any protocol=UDP profile=public,private,domain
)

netsh.exe advfirewall firewall add rule name="Allow 4723,17556,5901,8020" dir=in action=allow enable=yes localport=4723,17556,5901,8020 protocol=TCP profile=public,private,domain
netsh.exe advfirewall firewall add rule name="Allow ICMPv4" dir=in action=allow enable=yes protocol=icmpv4:8,any profile=public,private,domain

if "%test_signing%" EQU "1" (
    Bcdedit.exe -set TESTSIGNING ON 
)
if "%test_signing%" EQU "0" (
    Bcdedit.exe -set TESTSIGNING OFF
)

if "%local_setup%" NEQ "1" (
    rem Launch SimpleRemote
    if "!dut_architecture!" EQU "arm64" (
        echo Starting SimpleRemote on arm64
        start "SimpleRemoteConsole_Admin" /MIN /D %hobl_bin_path%\SimpleRemoteServer_win-arm64 SimpleRemoteConsole_Admin_win-arm64
    ) else (
        echo Starting SimpleRemote on x64
        start "SimpleRemoteConsole_Admin" /MIN /D %hobl_bin_path%\SimpleRemoteServer_win-x64 SimpleRemoteConsole_Admin_win-x64
    )
    rem Register host name with DNS server
    ipconfig /registerdns
)

rem restart dut
if "%reboot_prompt%" EQU "1" (
    pause
)
if "%reboot%" EQU "1" (
    echo Restarting DUT...
    shutdown /r /f /t 0
) else (
    echo
    echo Setup complete.  This window can be closed now.
)
echo dut_setup version: %dut_setup_version%
:end
