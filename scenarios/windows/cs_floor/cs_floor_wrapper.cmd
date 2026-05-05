@echo off
setlocal enabledelayedexpansion
cls
set wifi_off_duration=%1
echo Wifi off time (sec): %wifi_off_duration%

rem if dut_exec_path is not empty, call button.exe on dut and multiply button_delay by 1000
if [%3] NEQ [] set dut_exec_path=%3
if [%3] NEQ [] echo DUT Path: %dut_exec_path%
if [%3] NEQ [] set /a button_delay=%wifi_off_duration% * 1000
if [%3] NEQ [] echo Button Delay: %button_delay%

for /f "delims=: tokens=2" %%n in ('netsh wlan show interface name="Wi-Fi" ^| findstr ^/R "\<SSID"') do set "this_ssid=%%n"
set "this_ssid=%this_ssid:~1%"
echo %this_ssid%

if [%2] EQU [Disconnected] (
    rem disconnect from wlan
    netsh wlan set profileparameter name="%this_ssid%" connectionmode=manual
    netsh wlan disconnect
) 

rem Sleep for specified duration, if external button presser is used
if [%3] EQU [] c:\hobl_bin\cs_floor_resources\sleep.exe %1

rem Press button to go into standby for %button_delay% milliseconds, if software button being used
if [%3] NEQ [] %dut_exec_path%\button\button.exe -s %button_delay%

if [%2] EQU [Disconnected] (
    netsh wlan set profileparameter name="%this_ssid%" connectionmode=auto nonBroadcast=yes
    netsh wlan connect name="%this_ssid%"
)
