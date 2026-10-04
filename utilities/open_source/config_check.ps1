# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

[CmdletBinding(DefaultParameterSetName = "LogFile")]  
param(
    [Parameter(ParameterSetName = "LogFile")]
    [string] $LogFile,
    [switch] $PreRun,
    [switch] $PostRun,
    [string] $OverrideFile,
    [string] $OverrideString,
    [string] $PreRunFile,
    [switch] $DisableFileLogging,
    [switch] $GetPowerModeOnly
)
#Write-Host (get-date).ToString("hh:mm:ss") "CfgChkLog - Starting config_check"

Add-Type -Assembly System.Windows.Forms
# This module doens't seem to present on some builds
import-module pnpdevice -ErrorAction SilentlyContinue

#Write-Host (get-date).ToString("hh:mm:ss") "CfgChkLog - Finished import"

if (-Not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host -ForegroundColor Red "You do not have Administrator rights to run this script!"
    Write-Host -ForegroundColor Yellow "Please re-run this script as an Administrator!"
    exit
}

# Create log file
if ( !($DisableFileLogging) ) { 
    $global:delim = " "
    # Logging output support
    if (!$LogFile) {
        $ReportFileName = "Config"
        if ($PreRun) {
            $ReportFileName = "ConfigPreRun"
        }
        elseif ($PostRun) {
            $ReportFileName = "ConfigPostRun"
        }
        $TARGETDIR = 'C:\hobl_data'
        if (!(Test-Path -Path $TARGETDIR )) {
            New-Item -ItemType directory -Path $TARGETDIR
        }
        $LogFile = "$TARGETDIR\$ReportFileName"
    }
    $path = $LogFile.Substring(0, $LogFile.LastIndexOf('\'))
    New-Item -Path $path -ItemType Directory -Force | Out-Null    
    Out-File -Encoding ascii -FilePath "$LogFile.csv"
}

$overrideTable = [PSCustomObject]@{ }
if ($OverrideString) {
    Write-Host "Overrides:"
    $overrideTable = $OverrideString | convertFrom-JSON
    $overrideTable | Format-List
}
if ($OverrideFile) {
    Write-Host "Overrides:"
    $overrideTable = (Get-Content $OverrideFile) -join "`n" | ConvertFrom-Json
    $overrideTable | Format-List
}
$preRunTable = [PSCustomObject]@{ }
if ($PostRun) {
    if ($PreRunFile) {
        $preRunTable = (Get-Content $PreRunFile)
        write-host "Reading Pre-Run Configuration from " $PreRunFile ":"
    }
    else {
        # Get PreRunFile from standard location
        $PreRunFile = $path + "\ConfigPreRun.csv"
        $preRunTable = (Get-Content $PreRunFile)
        write-host "Reading Pre-Run Configuration from " $PreRunFile ":"
    }
}

###
### Helper functions
###


$table = [PSCustomObject]@{ }

# Write out the Key-Value pair of configuration, applying any overrides
function Write-KeyVal ($key, $val) {
    $finalVal = $val
    if ($overrideTable.$key) {
        $finalVal = $overrideTable.$key
    }
    $finalVal = ([string]$finalVal).Trim()
    $table | Add-Member -Name "$key" -Value "$finalVal" -MemberType NoteProperty 
}

# Run an executable and return its stdout lines, killing it and returning $null if it doesn't
# exit within the timeout (SMonitor hangs retrying when no accessory is connected).
function Invoke-WithTimeout ($FilePath, $Arguments, $TimeoutSeconds = 0.5) {
    try {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $FilePath
        $psi.Arguments = $Arguments
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true
        $proc = [System.Diagnostics.Process]::Start($psi)
        if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
            try { $proc.Kill() } catch {}
            return $null
        }
        $out = $proc.StandardOutput.ReadToEnd()
        if ([string]::IsNullOrWhiteSpace($out)) { return $null }
        return ($out.TrimEnd("`r", "`n") -split "`r?`n")
    } catch {
        return $null
    }
}

# Power Mode GUID to friendly name mapping
$PowerModeGuidMap = @{
    "961cc777-2547-4f9d-8174-7d86181b8a7a" = "Best Power Efficiency"
    "00000000-0000-0000-0000-000000000000" = "Recommended/Balanced"
    "3af9b8d9-7c97-431d-ad78-34a8bfea439f" = "Better"
    "ded574b5-45a0-4f42-8737-46345c09c238" = "Best Performance"
}

# Add type for PowerGetEffectiveOverlayScheme DLL import
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class PowerOverlay {
    [DllImport("powrprof.dll", SetLastError = true)]
    public static extern UInt32 PowerGetEffectiveOverlayScheme(out Guid EffectiveOverlayGuid);
}
"@

# Get the current effective power mode overlay using powrprof.dll
function Get-PowerModeOverlay {
    try {
        $guid = [Guid]::Empty
        $result = [PowerOverlay]::PowerGetEffectiveOverlayScheme([ref]$guid)
        
        if ($result -eq 0) {
            $guidString = $guid.ToString()
            $name = if ($PowerModeGuidMap.ContainsKey($guidString)) { $PowerModeGuidMap[$guidString] } else { $guidString }
            return @{ Guid = $guidString; Name = $name }
        }
    }
    catch { }
    return @{ Guid = "Error"; Name = "Error" }
}

# If -GetPowerModeOnly is specified, just return the power mode and exit
if ($GetPowerModeOnly) {
    Write-Output (Get-PowerModeOverlay).Name
    exit 0
}

Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume
{
    // f(), g(), ... are unused COM method slots. Define these if you care
    int f(); int g(); int h(); int i();
    int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
    int j();
    int GetMasterVolumeLevelScalar(out float pfLevel);
    int k(); int l(); int m(); int n();
    int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, System.Guid pguidEventContext);
    int GetMute(out bool pbMute);
}
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice
{
    int Activate(ref System.Guid id, int clsCtx, int activationParams, out IAudioEndpointVolume aev);
}
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator
{
    int f(); // Unused
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice endpoint);
}
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDeviceEnumeratorComObject { }
public class Audio
{
    static IAudioEndpointVolume Vol()
    {
        var enumerator = new MMDeviceEnumeratorComObject() as IMMDeviceEnumerator;
        IMMDevice dev = null;
        Marshal.ThrowExceptionForHR(enumerator.GetDefaultAudioEndpoint(/*eRender*/ 0, /*eMultimedia*/ 1, out dev));
        IAudioEndpointVolume epv = null;
        var epvid = typeof(IAudioEndpointVolume).GUID;
        Marshal.ThrowExceptionForHR(dev.Activate(ref epvid, /*CLSCTX_ALL*/ 23, 0, out epv));
        return epv;
    }
    public static float Volume
    {
        get { float v = -1; Marshal.ThrowExceptionForHR(Vol().GetMasterVolumeLevelScalar(out v)); return v; }
        set { Marshal.ThrowExceptionForHR(Vol().SetMasterVolumeLevelScalar(value, System.Guid.Empty)); }
    }
    public static bool Mute
    {
        get { bool mute; Marshal.ThrowExceptionForHR(Vol().GetMute(out mute)); return mute; }
        set { Marshal.ThrowExceptionForHR(Vol().SetMute(value, System.Guid.Empty)); }
    }
}
'@

function Load-AppxPackage {
    try {
        if (!$AppxPackage) { $global:AppxPackage = @(Get-AppxPackage) }
    }
    catch { $global:AppxPackage = @() }
}

function List-attachedDevices {

    if ($PreRun) 
        {
            $tempKey =  "Run Start DetectedDevices"
        }
    else
        {
            $tempKey = "Run Stop DetectedDevices"         
        }
    [int]$quickCounter = 0

    $DeviceName = ''
    $Devices = ''
    $list = @()
    $list = Get-PnpDevice -PresentOnly -Class Monitor
    foreach ($item in $list) {       
        if ($item.FriendlyName -match 'PnP' -and $item.FriendlyName -notmatch 'Panel' ) 
        { 
            if ($Devices -eq '') 
            {                
                $Devices += $item.FriendlyName
                $quickCounter++
            }
            else
            {
                $Devices += ' | ' + $item.FriendlyName
                $quickCounter++
            }
        }
    }
    

    $DeviceName2 = ''
    $list = Get-PnpDevice -PresentOnly -Class net
    foreach ($item in $list) {              
        if ($item.FriendlyName -match 'usb') {
            if ($DeviceName2 -eq '') {                
                $DeviceName2 += $item.FriendlyName
                $quickCounter++
                } else {
                $DeviceName2 += ' | ' + $item.FriendlyName
                $quickCounter++
                }
        }
    }   
    
    
    $DeviceName3 = ''
    $list = Get-PnpDevice -PresentOnly -Class audioendpoint
    # checks headphone devices   
    foreach ($item in $list) {
        if ($item.FriendlyName -match 'head'  ) {
            if ($DeviceName3 -eq '') {                
                $DeviceName3 += $item.FriendlyName
                $quickCounter++
                } else {
                $DeviceName3 += ' | ' + $item.FriendlyName
                $quickCounter++
                }
        }             
    }
    

    $DeviceName4 = ''
    $list = Get-PnpDevice -PresentOnly -Class hidclass 2>$null
    # checks pens  
    foreach ($item in $list) {
        if($item.InstanceId -match 'HID\\VID_045E&PID_09AD&COL06*') #$item.FriendlyName -match 'Surface Pen BLE' -or
        {
            if ($DeviceName4 -eq '') {                
                $DeviceName4 += $item.FriendlyName
                $quickCounter++
                } else {
                $DeviceName4 += ' | ' + $item.FriendlyName
                $quickCounter++
                }
        }             
    }
    

    $toggler = $false
    $DeviceName5 = ''
    $list2 = @()
    $list = Get-PnpDevice -PresentOnly -Class usb

    foreach($itm in $list)
    {
        foreach($itm2 in $list2)
        {
            if($itm.FriendlyName -notmatch $itm2.FriendlyName)
            { 
                $toggler = $false                
            }
            else
            {
         
                $toggler = $true             
                break
            }
        }

        if(!$toggler)
        {
         
            $list2 += $itm
            $toggler = $true
        }
    }

    foreach ($item in $list2)
    { 
        if ($item.FriendlyName -match 'USB') 
        {
            if ($item.InstanceId -notmatch 'PCI*')
            {
                if ($item.InstanceId -notmatch 'USB\\ROOT_hub30\\3&*' -and $item.InstanceId -notmatch 'USB\\ROOT_hub30\\4&D*' -and $item.InstanceId -notmatch 'USB\\VID_045E*' -and $item.InstanceId -notmatch 'USB\\VID_05E3*') 
                {
                    if ($item.InstanceId -notmatch 'ACPI\\QCOM*') 
                    {

                        if ($item.InstanceId -notmatch 'USB\\ROOT*') 
                        {
                            if ($DeviceName5 -eq '') 
                            {                
                                $DeviceName5 += $item.FriendlyName
                                $quickCounter++
                            }
                            else 
                            {
                                $DeviceName5 += ' | ' + $item.FriendlyName
                                $quickCounter++
                            }
                        }
                    }
                }
            }
        }

        # checks usb storage devices  
        if ($item.InstanceId -match 'usbstor\\*'){ #-or $item.FriendlyName -match 'USB Mass Storage Device'  ) {
        
            if ($DeviceName5 -eq '') {                
                $DeviceName5 += $item.FriendlyName
                $quickCounter++
                } else {
                $DeviceName5 += ' | ' + $item.FriendlyName
                $quickCounter++
                }
        }
    }
    
    
    $DeviceName6 = ''
    $togglerS = $false
    $list = Get-PnpDevice -PresentOnly -Class scsiadapter
    $listS = @()
    foreach($itm in $list)
    {
        foreach($itmS in $listS)
        {
         
            if($itm.FriendlyName -ne $itmS.FriendlyName)
            { 
                $togglerS = $false                
            }
            else
            {
         
                $togglerS = $true             
                break
            }
        }

        if(!$togglerS)
        {
         
            $listS += $itm
            $togglerS = $true
        }
    }
    foreach ($item in $listS) {
        if ($item.FriendlyName -match 'scsi'  ) {
            if ($DeviceName6 -eq '') {                
            $DeviceName6 += $item.FriendlyName
            $quickCounter++
            } else {
            $DeviceName6 += ' | ' + $item.FriendlyName
            $quickCounter++
            }
        } 
    }
    
     
    $DeviceName7 = ''    
    $listFn = @()
    $togglerFn = $false
    $list = Get-PnpDevice -PresentOnly -Class keyboard    
    foreach ($itm5 in $list) 
    {
        foreach ($itmF in $listFn) 
        {     
            if ($itm5.FriendlyName -ne $itmF.FriendlyName) 
            { 
                $togglerFn = $false                
            }
            else 
            {     
                $togglerFn = $true             
                break
            }
        }
        if (!$togglerFn) 
        {     
            $listFn += $itm5
            $togglerFn = $true
        }
    }

    foreach($itmF in $listFn)
    {
        if ($itmF -notmatch 'HID Keyboard Device') 
        {
            if ($DeviceName7 -eq '') 
            {                
                $DeviceName7 += $itmF.FriendlyName
                #$quickCounter++
            } 
            else 
            {
                $DeviceName7 += ' | ' + $itmF.FriendlyName
                #$quickCounter++
            }
        }
    }
    

    # Dwight request toast popup to tell end user to disable or unplug unneccessary devices attached to DUT in test.
    if ($quickCounter -gt 0) 
    {
        if ($PreRun) 
        {
            Write-KeyVal "Run Start ForeignDevices" "1"
        }
        elseif ($PostRun) 
        {
            Write-KeyVal "Run Stop ForeignDevices" "1"
        }
    }
    else {
        if ($PreRun) 
        {
            Write-KeyVal "Run Start ForeignDevices" "0"
        }
        elseif ($PostRun) 
        {
            Write-KeyVal "Run Stop ForeignDevices" "0"
        }
    }
    if ($Devices -ne '') 
    { 
        $DeviceName += $Devices + " | "
    }
    if ($DeviceName2 -ne '') 
    { 
        $DeviceName +=   $DeviceName2  + " | "
    } 
    if ($DeviceName3 -ne '') 
    { 
        $DeviceName +=  $DeviceName3  + " | "
    } 
    if ($DeviceName4 -ne '') 
    { 
        $DeviceName +=  $DeviceName4  + " | "
    } 
    if ($DeviceName5 -ne '') 
    { 
        $DeviceName +=  $DeviceName5  + " | "
    } 
    if ($DeviceName6 -ne '') 
    { 
        $DeviceName +=  $DeviceName6  + " | "
    }  
    if ($DeviceName7 -ne '') 
    { 
        $DeviceName +=   $DeviceName7 + " | "
    } 
    Write-KeyVal $tempKey  $DeviceName
}

function Load-WindowsPackages {
    if (!$WindowsPackages) { $global:WindowsPackages = @(Get-WindowsPackage -Online | Sort-Object PackageName) }
}

# Get list of Windows Updates that have been applied
function Get-Updates {
    [string]$Updates = ""
    Load-WindowsPackages
    $WindowsPackages | 
        Sort-Object PackageName |
        % { 
            $line = $_.PackageName
            if ( $line.StartsWith("Package_for_KB") ) {
                $temp = $line.TrimStart("Package Identity ; Package_for_")
                $i = $temp.IndexOf('~')
                $temp = $temp.Substring(0, $i)
                $Updates += ($temp + " ")
            }
        }
    return $Updates
}




function GetLTEStatus{
    param(
        [switch]$shortVersion,
        [switch]$prerun
    )
    $list = @()
    try {
        # TODO:  It's not called "Surface Mobile Broadband" on ProX devices.
        $list =  Get-NetAdapter -Name  'Cellular' -ErrorAction Stop
        foreach ($item in $list) 
        {   
            if ($shortVersion) 
            {
                # TODO:  This seems to call it "LTE" if it so much exists, even though WiFi might be the active 
                # connection to the internet.  I think it should check to see which connection is actually
                # the active connection.  One method that would work in conjunciton with net_prep is to get
                # Get-NetIpInterface and check InterfaceMetric for the "Cellular" InterfaceAlias (if it exists).
                # If the metric is 30, then "Cellular" should be the path to the internet (and Wi-Fi should be metric 500).
                # If Wi-Fi were the active route, then it's metric would be 30 and Cellular would be 500.
                Write-KeyVal "Mobility"  "LTE"
                # EDITED PORTION Start ################################################# 

                # Run NAME 
                $val = (((netsh mbn show interface ) | select-string " Name") -split (": "))[1]
                Write-KeyVal "Cellular Name" $val

                # Run Description 
                # $val = (((netsh mbn show interface ) | select-string " Description") -split (": "))[1]
                # Write-KeyVal "Cellular Description" $val

                # Run State 
                $val = (((netsh mbn show interface ) | select-string " State") -split (": "))[1]
                Write-KeyVal "Cellular State" $val

                # Run Cellular Class 
                $val = (((netsh mbn show interface ) | select-string " Cellular Class") -split (": "))[1]
                Write-KeyVal "Cellular Class" $val

                # Run Model 
                $val = (((netsh mbn show interface ) | select-string " Model") -split (": "))[1]
                Write-KeyVal "Cellular Model" $val

                # Run Firmware Version 
                $val = (((netsh mbn show interface ) | select-string " Firmware Version") -split (": "))[1]
                Write-KeyVal "Cellular Firmware Version" $val

                # Run Provider Name
                $val = (((netsh mbn show interface ) | select-string " Provider Name") -split (": "))[1]
                Write-KeyVal "Cellular Provider Name" $val

                # Run Roaming
                $val = (((netsh mbn show interface ) | select-string " Roaming") -split (": "))[1]
                Write-KeyVal "Cellular Roaming" $val

                # Run Signal
                $val = (((netsh mbn show interface ) | select-string " Signal") -split (": "))[1]
                Write-KeyVal "Cellular Signal" $val

                # Run RSSI / RSCP
                $val = (((netsh mbn show interface ) | select-string " RSSI / RSCP") -split (": "))[1]
                Write-KeyVal "Cellular RSSI / RSCP" $val

                # Run SIM ICC Id
                $val = (((netsh mbn show read interface=* ) | select-string " SIM ICC Id") -split (": "))[1]
                Write-KeyVal "Cellular SIM ICC Id" $val

                # Run Telephone #1
                $val = (((netsh mbn show read interface=* ) | select-string " Telephone #1") -split (": "))[1]
                Write-KeyVal "Cellular Telephone #1" $val
            
                # EDITED PORTION END ################################################# 
                break         
            }
            else 
            { 
                if ($item.Status.Equals('Up'))
                {
                    if ($prerun) 
                    {
                        #Cell is connected.
                        Write-KeyVal "Run Start LTE State" 'Connected'
                    }
                    else {                        
                        Write-KeyVal "Run Stop LTE State" 'Connected'
                    }
                    break
                }
                elseif ($item.Status.Equals('Disconnected'))
                {        
                    if ($prerun) 
                    {
                        #Cell is Disconnected.
                        Write-KeyVal "Run Start LTE State" 'Disconnected'
                    }
                    else 
                    {                        
                        Write-KeyVal "Run Stop LTE State" 'Disconnected'
                    }    
                    break
                }                
                 elseif ($item.Status.Equals('Ok'))
                {
                    if ($prerun) 
                    {
                        #Cell is Available.
                        Write-KeyVal "Run Start LTE State" 'Available'
                    }
                    else 
                    {                        
                        Write-KeyVal "Run Stop LTE State" 'Available'
                    }    
                    break                    
                }
          }
        }
    }
    catch 
    {
        if ($shortVersion) {
            Write-KeyVal "Mobility"  "Wi-Fi"
        }
    }
}

#Looking at HKey registry and parsing string at property(CalibrationConfigTypicalBlobFile) for panel substring.
function getDisplayPanel
{
    $path = "HKLM:\HKEY_LOCAL_MACHINE\SYSTEM\ControlSet001\Control\Class\{4d36e96e-e325-11ce-bfc1-08002be10318}"
    $keys = Get-ChildItem $path -ErrorAction SilentlyContinue
    $property = ""

        foreach ($key in $keys){
            try {
                $property = Get-ItemPropertyValue -Path $key.PSPath -Name 'CalibrationConfigTypicalBlobFile' -ErrorAction SilentlyContinue

                if ($property -match "lcd"){
                    Write-KeyVal "Display Panel" "LCD" -Force
                    break
                }elseif($property -match "oled"){
                    Write-KeyVal "Display Panel" "OLED"-Force
                    break
                }else {
                    Write-KeyVal "Display Panel" "Undefined" -Force
                    break
                }
            } catch { 
                Continue
            }
            
        }

}



function Get-AppsOffice 
{
    try {
        $objword = New-Object -ComObject word.application
        # $majorminor = $objword.Build
        # #parse major-minor to get major
        # $major = $majorminor.Split(".")[0]
        # $bld = [System.Diagnostics.FileVersionInfo]::GetVersionInfo("C:\Program Files (x86)\Microsoft Office\Office$major\winword.exe").FileVersion
        # return $bld
        $build =  $objword.Build
        kill -Name winword -force
        return $build
    } catch {
        return "Not present"
    }
}
function GetOfficeActivationStatus
{
    # Check for office activation status
    push-location
    # Get system drive
    $dr = $env:SystemDrive
    #write-host("Drive: " + $dr)
    $office_path1 = $dr + "\Program Files (x86)\Microsoft Office\Office16\ospp.vbs"
    $office_path2 = $dr + "\Program Files\Microsoft Office\Office16\ospp.vbs"

    if (test-path -LiteralPath $office_path1 -pathType leaf){
        $office_path = $dr + "\Program Files (x86)\Microsoft Office\Office16\"
    }

    elseif(test-path -LiteralPath $office_path2 -pathType leaf){
        $office_path = $dr + "\Program Files\Microsoft Office\Office16\"
    }
    else{
        $office_path = ""
    }
    #write-host("This Office path exists: " + $office_path)

    if ($office_path -ne $null){
        #write-host ("Office path: " + $office_path)
        cd $office_path
        #Get-Location
        $status_output = cscript ospp.vbs /dstatus
        #write-host("Status output: " + $status_output)
        pop-location
        # parse the output
        if ($status_output -like ("*---Licensed---*")){
            $status = "Valid License"
        }
        elseif ($status_output -like ("*grace period expired*")){
            $status = "Inactive"
        }
        elseif ($status_output -like("*valid grace period*")){
            $status = "Trial"
        }
        else{
            $status = "Not present"
        }
    }
    else{
        $status = "Not present"
    }
    return $status
    #write-host("Office Activation Status: " + $status)
}

        

###################################################################################
###################################################################################
####
####   Output information
####
###################################################################################
###################################################################################


if ($PreRun) {
    #Write-Host (get-date).ToString("hh:mm:ss") "CfgChkLog - Starting PreRun()"

    # Study Type
    # How to get?

    # Run Command
    # How to get?

    # Scenario
    [datetime]$today = get-date
    Write-KeyVal "Test Name" ""
    Write-KeyVal "Scenario" ""

    # Run Start Time
    [datetime]$today = get-date
    Write-KeyVal "Run Start Time" $today.ToString("yyyy-MM-dd HH:mm:ss")


    # Run Energy Drained (mWh)
    # $batt2 = Get-WmiObject Win32_Battery
    # $battCount2 = $batt2.Count 
    # If ($battCount2 -le "1") {
    #     $battCount2 = "1"
    # }
    $ErrorActionPreference = 'SilentlyContinue'
    $battFCC2 = (Get-WmiObject -Class "BatteryFullChargedCapacity" -Namespace "ROOT\WMI").FullChargedCapacity
    $battCount2 = $battFCC2.Count
    $battCycles2 = (Get-WmiObject -Class "BatteryCycleCount" -Namespace "ROOT\WMI").CycleCount
    if ($battCount2 -eq 1) {
        $totalFCC2 = $battFCC2
        Write-KeyVal "Run Start Battery 1 Cycle Count" $battCycles2
    }
    else {
        $totalFCC2 = $battFCC2[0] + $battFCC2[1]
        Write-KeyVal "Run Start Battery 1 Cycle Count" $battCycles2[0]
        Write-KeyVal "Run Start Battery 2 Cycle Count" $battCycles2[1]
    }

    #Write-Host (get-date).ToString("hh:mm:ss") "CfgChkLog - Got FCC"

    # Run Start Battery State (%)
    $totalSoC2 = [Math]::round(([System.Windows.Forms.SystemInformation]::PowerStatus.BatteryLifePercent) * 100, 2)
    Write-KeyVal "Run Start Battery State (%)" $totalSoC2
    
    # $startenergy2 = $totalFCC2 * ($totalSoC2 / 100)
    # Write-KeyVal "Start Battery Level (mWh)" $startenergy2

    # Run Start SAM Battery State (%)  ## Only on Surface devices
    try {
        if (Test-Path "C:\Tools\SMonitor\SMonitorUAP.exe") 
        {
            $SmonRSOC = C:\Tools\SMonitor\SMonitorUAP.exe /batteryrsoc 2>$null
        } 
        else 
        {
            $SmonRSOC = C:\Tools\SMonitor\SMonitor.exe /batteryrsoc 2>$null
        }
        $SmonRSOC = [System.Convert]::ToString($SmonRSOC.split("  ")[2], 10) 
        Write-KeyVal "Run Start SAM Battery State (%)" $SmonRSOC
    } catch {}

    # Run Start KIP Battery State (%)  ## Only on Surface devices
    if ($battCount2 -gt 1) {
        try {
            if (Test-Path "C:\Tools\SMonitor\SMonitorUAP.exe") 
            {
                $SmonKIPRSOC = C:\Tools\SMonitor\SMonitorUAP.exe /mcu kip /batteryrsoc 2>$null
            } 
            else 
            {
                $SmonKIPRSOC = C:\Tools\SMonitor\SMonitor.exe /mcu kip /batteryrsoc 2>$null
            }
            $SmonKIPRSOC = [System.Convert]::ToString($SmonKIPRSOC.split("  ")[2], 10) 
            Write-KeyVal "Run Start KIP Battery State (%)" $SmonKIPRSOC
        } catch {}
    }

    # Run Start SAM BPM Status  ## Only on Surface devices
    try {
        if (Test-Path "C:\Tools\SMonitor\SMonitorUAP.exe") 
        {
            $SmonSAMBPM = C:\Tools\SMonitor\SMonitorUAP.exe /mcu sam /getbatterybpmstatus 1 2>$null
        } 
        else 
        {
            $SmonSAMBPM = C:\Tools\SMonitor\SMonitor.exe /mcu sam /getbatterybpmstatus 1 2>$null
        }
        $SmonSAMBPM = [System.Convert]::ToString($SmonSAMBPM.split("  ")[2], 10) 
    } catch {}

    # Run Start KIP BPM Status  ## Only on multi-batt Surface devices
    if ($battCount2 -gt 1) {
        try {
            if (Test-Path "C:\Tools\SMonitor\SMonitorUAP.exe") 
            {
                $SmonKIPBPM = C:\Tools\SMonitor\SMonitorUAP.exe /mcu kip /getbatterybpmstatus 1 2>$null
            } 
            else 
            {
                $SmonKIPBPM = C:\Tools\SMonitor\SMonitor.exe /mcu kip /getbatterybpmstatus 1 2>$null
            }
            $SmonKIPBPM = [System.Convert]::ToString($SmonKIPBPM.split("  ")[2], 10) 
        } catch {}
    }

    if ($SmonSAMBPM -or $SmonKIPBPM)
    {
        if ($SmonSAMBPM -ne "0" -or $SmonKIPBPM -ne "0")
        {
            Write-KeyVal "Run Start BPM Status" "1"
        }
        else 
        {
            Write-KeyVal "Run Start BPM Status" "0"
        }
    }
    else {
        Write-KeyVal "Run Start BPM Status" "NA"
    }

    # Run Start SAM BPM Time  ## Only on Surface devices
    try {
        if (Test-Path "C:\Tools\SMonitor\SMonitorUAP.exe") 
        {
            $BPMTIME = C:\Tools\SMonitor\SMonitorUAP.exe /batteryrsoc 2>$null
        } 
        else 
        {
            $BPMTIME = C:\Tools\SMonitor\SMonitor.exe /batteryrsoc 2>$null
        }
        $BPMTIME = [System.Convert]::ToString($BPMTIME.split("  ")[2], 10) 
        Write-KeyVal "Run Start SAM BPM Time" $BPMTIME
    } catch {}

    # Run Start KIP BPM Time  ## Only on Surface devices
    if ($battCount2 -gt 1) {
        try {
            if (Test-Path "C:\Tools\SMonitor\SMonitorUAP.exe") 
            {
                $BPMTIME = C:\Tools\SMonitor\SMonitorUAP.exe /mcu kip /batteryrsoc 2>$null
            } 
            else 
            {
                $BPMTIME = C:\Tools\SMonitor\SMonitor.exe /mcu kip /batteryrsoc 2>$null
            }
            $BPMTIME = [System.Convert]::ToString($BPMTIME.split("  ")[2], 10) 
            Write-KeyVal "Run Start KIP BPM Time" $BPMTIME
        } catch {}
    }
    $ErrorActionPreference = 'Continue'

    #Write-Host (get-date).ToString("hh:mm:ss") "CfgChkLog - Finished SMON"

    # Run WiFi State
    $val = get-netadapter | % { if ($_.Name -eq "Wi-Fi") { $_.Status } }
    Write-KeyVal "Run Start WiFi State" $val

    # Run WiFi Connection
    $val = (((netsh wlan show interfaces) | select-string " SSID") -split (": "))[1]
    Write-KeyVal "Run Start WiFi Connection" $val

    #Write-Host (get-date).ToString("hh:mm:ss") "CfgChkLog - Finished WiFi"
    
    # Run LTE Net State
    GetLTEStatus -prerun

    #Write-Host (get-date).ToString("hh:mm:ss") "CfgChkLog - Finished LTE"

    # Run Bluetooth State
    $val = "Disconnected"
    Get-WmiObject Win32_PNPEntity | % { if ($_.name -eq "Microsoft Bluetooth Enumerator") { $val = "Up" } }
    Write-KeyVal "Run Bluetooth State" $val

    # Run Bluetooth Connection
    $val = ""
    Get-WmiObject Win32_PNPEntity | % { if (($_.service -eq "BthEnum" -or $_.service -eq "BthLEEnum") -and $_.Name -notmatch "Enumerator") { $val += ($_.Name) + ", " } }
    Write-KeyVal "Run Bluetooth Connection" $val

    #Write-Host (get-date).ToString("hh:mm:ss") "CfgChkLog - Finished BT"

    # Run Audio Volume (%)
    $vol = 0
    if ([audio]::Mute) {
        $vol = "MUTED"
        Write-KeyVal "Run Start Audio Volume (%)" $vol
    }
    ELSE {
        $vol = "{0:N0}" -f ([audio]::Volume * 100)
        Write-KeyVal "Run Start Audio Volume (%)" $vol
    }
    
    #Write-Host (get-date).ToString("hh:mm:ss") "CfgChkLog - Finished Volume"

    # Run Screen Brightness (%)
    Write-KeyVal "Run Start Screen Brightness (%)" (Get-WmiObject -Class WmiMonitorBrightness -Namespace root/WMI -ErrorAction SilentlyContinue).CurrentBrightness

    #Write-Host (get-date).ToString("hh:mm:ss") "CfgChkLog - Finished Brightness"

    # Run Charge State
    $Chargestatus = (Get-WmiObject -Class Win32_Battery -ea 0).BatteryStatus
    switch ($Chargestatus) {
        1 { $val = "Battery is discharging" }
        2 { $val = "On AC" }
        3 { $val = "Fully Charged" }
        4 { $val = "Battery Low" }
        5 { $val = "Critical" }
        6 { $val = "Charging" }
        7 { $val = "Charging and High" }
        8 { $val = "Charging and Low" }
        9 { $val = "Charging and Critical " }
        10 { $val = "Unknown State" }
        11 { $val = "Partially Charged" }
        default { $val = "Unknown state" }       
    }
    Write-KeyVal "Run Start Charge State" $val

    #Write-Host (get-date).ToString("hh:mm:ss") "CfgChkLog - Finished Charge State"

    # Run EPP value
    # with slider
    $ErrorActionPreference = 'SilentlyContinue'
    $val = "UNKNOWN"
    try {
        $val = [convert]::toint16(((powercfg /QH SCHEME_BALANCED SUB_PROCESSOR PERFEPP | select-string -pattern "Current DC") -split ":" | select -last 1).TrimStart(), 16)
    }
    catch {
        try {
            $val = [convert]::toint16(((powercfg /qh overlay_scheme_current | select-string -pattern "Current DC") -split ":" | select -last 1).TrimStart(), 16)
        }
        catch {}
    }
    Write-KeyVal "Run Start EPP" $val
    $ErrorActionPreference = 'Continue'

    #Write-Host (get-date).ToString("hh:mm:ss") "CfgChkLog - Finished EPP"

    #check and list for attached devices (commenting out, fails too often)
    #List-attachedDevices

    # Run Num Processes ??
}
elseif ($PostRun) {
    # Run Completed
    # How to get?
    # Passed on command line

    # Run Audio Volume (%)
    $vol = 0
    if ([audio]::Mute) {
        $vol = "MUTED"
        Write-KeyVal "Run Stop Audio Volume (%)" $vol
    }
    ELSE {
        $vol = "{0:N0}" -f ([audio]::Volume * 100)
        Write-KeyVal "Run Stop Audio Volume (%)" $vol
    }

    # Run Stop Screen Brightness (%)
    Write-KeyVal "Run Stop Screen Brightness (%)" (Get-WmiObject -Class WmiMonitorBrightness -Namespace root/WMI -ErrorAction SilentlyContinue).CurrentBrightness

    # Stop Charge State
    $Chargestatus = (Get-WmiObject -Class Win32_Battery -ea 0).BatteryStatus
    switch ($Chargestatus) {
        1 { $val = "Battery is discharging" }
        2 { $val = "On AC - not charging" }
        3 { $val = "Fully Charged" }
        4 { $val = "Battery Low" }
        5 { $val = "Critical" }
        6 { $val = "Charging" }
        7 { $val = "Charging and High" }
        8 { $val = "Charging and Low" }
        9 { $val = "Charging and Critical " }
        10 { $val = "Unknown State" }
        11 { $val = "Partially Charged" }
        default { $val = "Unknown state" }       
    }
    Write-KeyVal "Run Stop Charge State" $val

    # Run WiFi State
    $val = get-netadapter | % { if ($_.Name -eq "Wi-Fi") { $_.Status } }
    Write-KeyVal "Run Stop WiFi State" $val

    # Run WiFi Connection
    $val = (((netsh wlan show interfaces) | select-string " SSID") -split (": "))[1]
    Write-KeyVal "Run Stop WiFi Connection" $val

    # Run LTE Net State
    GetLTEStatus

    # Run Stop Bluetooth State
    $val = "Disconnected"
    Get-WmiObject Win32_PNPEntity | % { if ($_.name -eq "Microsoft Bluetooth Enumerator") { $val = "Up" } }
    Write-KeyVal "Run Stop Bluetooth State" $val
    
    # Run EPP value
    # with slider
    $ErrorActionPreference = 'SilentlyContinue'
    $val = "UNKNOWN"
    try {
        $val = [convert]::toint16(((powercfg /QH SCHEME_BALANCED SUB_PROCESSOR PERFEPP | select-string -pattern "Current DC") -split ":" | select -last 1).TrimStart(), 16)
    }
    catch {
        try {
            $val = [convert]::toint16(((powercfg /qh overlay_scheme_current | select-string -pattern "Current DC") -split ":" | select -last 1).TrimStart(), 16)
        }
        catch {}
    }    
    Write-KeyVal "Run Stop EPP" $val
    $ErrorActionPreference = 'Continue'
    
    # Run Stop Time
    [datetime]$today = get-date
    $stopTime = $today.ToString("yyyy-MM-dd HH:mm:ss")
    Write-KeyVal "Run Stop Time" $stopTime

    # Run Stop Battery State (%)
    $stopSoC = [Math]::round(([System.Windows.Forms.SystemInformation]::PowerStatus.BatteryLifePercent) * 100, 2)
    Write-KeyVal "Run Stop Battery State (%)" $stopSoC

    # Calculated by reading PreRun file.
    $startTime = (($preRunTable | Select-String -Pattern "Run Start Time") -split ",")[1]
    $startSoC = (($preRunTable | Select-String -Pattern "Run Start Battery State (%)" -SimpleMatch) -split ",")[1]

    # Run Duration (min)
    $_min = NEW-TIMESPAN -Start $startTime -End $stopTime
    $duration = [math]::round($_min.TotalMinutes, 2)
    Write-KeyVal "Run Duration (min)" $duration

    # Run Energy Drained (mWh)
    # $batt = Get-WmiObject Win32_Battery
    # $battCount = $batt.Count 
    # If ($battCount -le "1") {
    #     $battCount = "1"
    # }
    $ErrorActionPreference = 'SilentlyContinue'
    $battFCC = (Get-WmiObject -Class "BatteryFullChargedCapacity" -Namespace "ROOT\WMI").FullChargedCapacity
    $battCount = $battFCC.Count
    
    if ($battCount -eq 1) {
        $totalFCC = $battFCC
    }
    else {
        $totalFCC = $battFCC[0] + $battFCC[1]
    }
    $ErrorActionPreference = 'Continue'

    $chargeDelta = $startSoC - $stopSoC
    $totalEnergyUsed = $totalFCC * ($chargeDelta / 100)    
    $stopenergy = $totalFCC * ($stopSoC / 100)
    # Write-KeyVal "Stop Battery Level (mWh)" $stopenergy
    $e_rounded = [int]$totalEnergyUsed
    Write-KeyVal "Run Energy Drained (mWh)" $e_rounded

    # Run Drain Rate (mW)
    $rate = $totalEnergyUsed / ($duration / 60)
    $rate = [int]$rate
    Write-KeyVal "Run Drain Rate (mW)" $rate
        
    #check and list for attached devices (commenting out, fails too often)
    #List-attachedDevices

}
# Static system configuration
else { 
    # Specified in profile
    # Study Type
    Write-KeyVal "Study Type" ""
    # Accessories
    Write-KeyVal "Accessories" ""
    # Hardware Version
    Write-KeyVal "Hardware Version" ""
    # Screen Size
    Write-KeyVal "Screen Size (in)" ""

    # Product
    if (!$Win32_ComputerSystem) { $global:Win32_ComputerSystem = @(Get-WmiObject Win32_ComputerSystem) }
    # TODO: we need to lookup product name from database/list for unreleased products
    Write-KeyVal "Product" $Win32_ComputerSystem.Model
    Write-KeyVal "Product Mfg" $Win32_ComputerSystem.Manufacturer

    # Get Wi-Fi vs LTE
    GetLTEStatus -shortVersion

    # Serial Number
    $serialNumber = (Get-WmiObject -class Win32_Bios).SerialNumber
    Write-KeyVal "Serial Number" $serialNumber

    # Device Name
    Write-KeyVal "Device Name" (Get-WmiObject -Class Win32_ComputerSystem -Property Name).Name

    # MAC Address
    $val = get-netadapter | % { if ($_.Name -eq "Wi-Fi") { $_.MacAddress } }
    Write-KeyVal "MAC Address" $val

    # MSA Account
    #$val = Get-ChildItem HKCU:\Software\Microsoft\IdentityCRL\UserExtendedProperties\ | select psChildName
    $val = ""
    if(Get-ChildItem HKCU:\Software\Microsoft\IdentityCRL\UserExtendedProperties\ -ErrorAction Ignore | select psChildName){
        $val = (Get-ChildItem HKCU:\Software\Microsoft\IdentityCRL\UserExtendedProperties\ -ErrorAction Ignore | select psChildName)
        $val = $val -split('=')
        $val = $val[1]
        $val = $val.TrimEnd('}')    
    }
    
    Write-KeyVal "MSA Account" $val

    # Check if button.exe is installed
    $val = Get-WMIObject Win32_PnPEntity | where {$_.Name -like "Power Button*"}
    If ($val -eq $null) {
        $val = "NOT INSTALLED"
    } else {
        $val = "INSTALLED"
    }
    Write-KeyVal "Button.exe" $val

    # OS Build
    $buildnum = Get-ItemProperty -Path "Registry::HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion" -Name CurrentBuild -ErrorAction SilentlyContinue
    $ubr = Get-ItemProperty -Path "Registry::HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion" -Name UBR -ErrorAction SilentlyContinue
    Write-KeyVal "OS Build" "$($buildnum.CurrentBuild).$($ubr.UBR)"

    # Boot Image Version
    $image = ""
    $RegPath = "HKEY_LOCAL_MACHINE\Software"
    # foreach ($RegRoot in @("Microsoft\Windows\CurrentVersion","Microsoft\Surface\OSImage")) {
    foreach ($RegRoot in @("Microsoft\Surface\OSImage")) {
        try {
            # $tempreg = Get-ItemProperty -Path "$RegPath\$RegRoot" -Name ImageVersion -ErrorAction SilentlyContinue
            # $imageVersion = $tempreg.ImageVersion
            $tempreg = & reg.exe QUERY "$RegPath\$RegRoot" /v ImageVersion 2>&1
            if ($lastexitcode -eq 0) {
                $imageVersion = ($tempreg[2].split(' ', [system.StringSplitOptions]::RemoveEmptyEntries))[2]
            }
            else {
                $tempreg = & "$env:windir\sysnative\reg.exe" QUERY "$RegPath\$RegRoot" /v ImageVersion 2>&1
                if ($lastexitcode -eq 0) {
                    $imageVersion = ($tempreg[2].split(' ', [system.StringSplitOptions]::RemoveEmptyEntries))[2]
                }
            }
        }
        catch { }
        try {
            # $tempreg   = Get-ItemProperty -Path "$RegPath\$RegRoot" -Name ImageName -ErrorAction SilentlyContinue
            # $imageName = $tempreg.ImageName
            $tempreg = & reg.exe QUERY "$RegPath\$RegRoot" /v ImageName 2>&1
            if ($lastexitcode -eq 0) {
                $imageName = ($tempreg[2].split(' ', [system.StringSplitOptions]::RemoveEmptyEntries))[2]
            }
            else {
                $tempreg = & "$env:windir\sysnative\reg.exe" QUERY "$RegPath\$RegRoot" /v ImageName 2>&1
                if ($lastexitcode -eq 0) {
                    $ImageName = ($tempreg[2].split(' ', [system.StringSplitOptions]::RemoveEmptyEntries))[2]
                }
            }
        }
        catch { }
    }
    Write-keyVal "Boot Image Version" "$($imageVersion)"
    Write-keyVal "Boot Image Name" "$($imageName)"

    # CPU Name
    $proc = Get-WmiObject -Class Win32_Processor
    $name = $proc.name
    If ($name -like "*Pentium*") {
        $name = "Pentium " + $proc.Name.Substring(24, 5)
    }
    elseif ($name -like "*Snapdragon*") {
        $name = "Snapdragon " + $proc.Name.Substring(16, 3)
    }
    elseif($name -like "*Ryzen*") {
        $name = "Ryzen" + $proc.Name.Substring(10, 2)
    }
    elseif($name -like "*Fabrikams*"){
        $name = "Fabrikams" + $proc.Name.Substring(9, 4)
    }
    else {
        # $name_length = $proc.Name.length
        # if ($name_length -ge 15){
        #     $name = $name.Substring(0,15)
        # }
    }
    Write-KeyVal "CPU Name" $name

    # CPU Mfg
    $cpu_mfg = (Get-WmiObject -Class Win32_Processor).manufacturer
    If ($cpu_mfg -like "*Intel*") {
        $cpu_mfg = "INT"
    }
    elseif ($cpu_mfg -like "*AMD*") {
            $cpu_mfg = "AMD"
    }
    elseif ($cpu_mfg -like "*Qualcomm*") {
        $cpu_mfg = "QC"
    }
    else {
        $cpu_mfg
    }
    Write-KeyVal "CPU Mfg" $cpu_mfg


    # CPU Stepping
    if ($proc.Caption -match "Stepping (\d+)") {
        Write-KeyVal "CPU Stepping" ($matches[1])
    } 

    # GPUs
    $iGpu = "Not present"
    $dGpu = "Not present"
    $gpus = Get-WmiObject Win32_PnPSignedDriver | % {
        if ($_.DeviceClass -like "*DISPLAY*") {
            # if ($_.Manufacturer -like "*Intel*" -Or $_.Manufacturer -like "*Qualcomm*") {
            if ($_.Manufacturer -like "*nvidia*") {
                $dGpu = $_.DeviceName + " " + $_.DriverVersion
            }
            else {
                $iGpu = $_.DeviceName + " " + $_.DriverVersion
            }
        }
    }
    Write-KeyVal "Integrated GPU" $iGpu
    Write-KeyVal "Discrete GPU" $dGpu

    # Display Panel (OLED, LCD or Undefined)
    getDisplayPanel

    # Display Resolution
    $resobj = @()
    $resobj = Get-WmiObject -Class Win32_videocontroller
    foreach ($objItem in $resobj )
    {
        if ($null -ne $objItem.CurrentHorizontalResolution) 
        {   
            $res = [string]$objItem.CurrentHorizontalResolution + 'x' + [string]$objItem.CurrentVerticalResolution
            Write-KeyVal "Display Resolution"  $res
            break
        }   
    }

    # Memory Mfg
    get-ciminstance -class "cim_physicalmemory" | % { $Mfg = $_.Manufacturer }
    Write-KeyVal "Memory Mfg" $Mfg

    # Memory Size (GB)
    $capacity = 0
    get-ciminstance -class "cim_physicalmemory" | % { $capacity += $_.Capacity }
    $memsize = (($capacity / 1MB) / 1kB)
    Write-KeyVal "Memory Size (GB)" $memsize

    $drive = ""
    Get-WmiObject -Class win32_diskdrive | % { if ($_.DeviceID -like "*PHYSICALDRIVE0") { $drive = $_ } }
    if ($drive -eq "") {
        Get-WmiObject -Class win32_diskdrive | % { if ($_.DeviceID -like "*PHYSICALDRIVE*") { $drive = $_ } }
    }

    # Storage Mfg
    $val = $drive.Model
    If ($val.LastIndexOf(' ') -gt 0) {
    
        # Strip off the model number and just keep the manufacturer
        $val = $val.SubString(0, $val.LastIndexOf(' '))
    }
    Write-KeyVal "Storage Mfg" $val

    # Storage Size (GB)
    $size = $drive.Size
    $size = [int64]($size / 1000000000)
    if ($size -ge 60 -AND $size -le 65) { $size = 64 }
    Write-KeyVal "Storage Size (GB)" $size

    # Storage Firmware
    $val = $drive.FirmwareRevision
    Write-KeyVal "Storage Firmware" $val

    # Battery details
    # Battery Full Charge Capacity (mWh)
    # Battery Energy Drained (mWh)
    # Battery 1 Mfg
    # Battery 2 Mfg
    # Battery 1 ID
    # Battery 2 ID
    # Battery 1 Cycle Count
    # Battery 2 Cycle Count
    # Battery Charge State (%)
    # Battery Status
    # $batt = Get-WmiObject Win32_Battery
    # $battCount = $batt.Count 
    # If ($battCount -le "1") {
    #     $battCount = "1"
    # }
    $ErrorActionPreference = 'SilentlyContinue'
    $battSoC = $batt.EstimatedChargeRemaining
    $battFCC = (Get-WmiObject -Class "BatteryFullChargedCapacity" -Namespace "ROOT\WMI").FullChargedCapacity
    $battCount = $battFCC.Count
    $battCycles = (Get-WmiObject -Class "BatteryCycleCount" -Namespace "ROOT\WMI").CycleCount
    $battStatic = (Get-WmiObject -Class "BatteryStaticData" -Namespace "ROOT\WMI")
    if ($battCount -eq 1) {
        $totalFCC = $battFCC
        [int]$batt1EnergyUsed = $battFCC * (1 - ($battSoC / 100))
        $totalEnergyUsed = $batt1EnergyUsed
        $status = $batt.BatteryStatus
        Write-KeyVal "Battery 1 ID" ($batt.Name)
        Write-KeyVal "Battery 1 Cycle Count" $battCycles
        Write-KeyVal "Battery 1 Mfg" $battStatic.ManufactureName
        $battDesignCap = [Math]::round($battStatic.DesignedCapacity / 1000)
    }
    else {
        $totalFCC = $battFCC[0] + $battFCC[1]
        [int]$batt1EnergyUsed = $battFCC[0] * (1 - ($battSoC[0] / 100))
        [int]$batt2EnergyUsed = $battFCC[1] * (1 - ($battSoC[1] / 100))
        $totalEnergyUsed = $batt1EnergyUsed + $batt2EnergyUsed
        $status = $batt.BatteryStatus[0]
        Write-KeyVal "Battery 1 ID" ($batt.Name)[0]
        Write-KeyVal "Battery 2 ID" ($batt.Name)[1]
        Write-KeyVal "Battery 1 Cycle Count" $battCycles[0]
        Write-KeyVal "Battery 2 Cycle Count" $battCycles[1]
        Write-KeyVal "Battery 1 Mfg" $battStatic.ManufactureName[0]
        Write-KeyVal "Battery 2 Mfg" $battStatic.ManufactureName[1]
        $battDesignCap = [Math]::round(($battStatic.DesignedCapacity[0] + $battStatic.DesignedCapacity[1]) / 1000)
    }
    Write-KeyVal "Battery Total Designed Capacity (Wh)" $battDesignCap
    Write-KeyVal "Battery Full Charge Capacity (mWh)" $totalFCC
    Write-KeyVal "Battery Energy Drained (mWh)" $totalEnergyUsed
    $totalSoC = [Math]::round(([System.Windows.Forms.SystemInformation]::PowerStatus.BatteryLifePercent) * 100)
    Write-KeyVal "Battery Charge State (%)" $totalSoC
    switch ($status) {
        1 {Write-KeyVal "Battery Status" "Drain"}
        2 {Write-KeyVal "Battery Status" "Charge"}
        default {Write-KeyVal "Battery Status" "Unknown"}
    }
    
    # gets battery firmware
    # $smonitorPath = "c:\Tools\SMonitor"
    # if(Test-Path -Path $smonitorPath)
    # {
    #     pushd c:\Tools\SMonitor
    #     $battFirmware = (.\SMonitorUAP.exe /readbatteryfwversion)
    #     popd

    #     # extracts the firmware from the string returned by SMonitorUAP.exe
    #     $formattedBattFirmware = $battFirmware.split(' ')[2]

    #     # writes battery firmware info
    #     Write-KeyVal "Battery Firmware Version" $formattedBattFirmware
    # }

    $smonitorPath = "c:\Tools\SMonitor"
    if(Test-Path -Path $smonitorPath)
    {
        
        if (Test-Path "C:\Tools\SMonitor\SMonitorUAP.exe") 
        {
            $battFirmware = C:\Tools\SMonitor\SMonitorUAP.exe /readbatteryfwversion 2>$null
        } 
        else 
        {
            $battFirmware = C:\Tools\SMonitor\SMonitor.exe /readbatteryfwversion 2>$null
        }
        # $battFirmware = (.\SMonitorUAP.exe /readbatteryfwversion)
        

        # extracts the firmware from the string returned by SMonitorUAP.exe
        $formattedBattFirmware = $battFirmware.split(' ')[2]

        # writes battery firmware info
        Write-KeyVal "Battery Firmware Version" $formattedBattFirmware
    }
    $ErrorActionPreference = 'Continue'

    # Windows Updates
    Write-KeyVal "Windows Updates" (Get-Updates)

    # Firmware Versions
    $ErrorActionPreference = 'SilentlyContinue'
    if (!$Win32_PNPSignedDriver) { $global:Win32_PNPSignedDriver = @(Get-WmiObject Win32_PNPSignedDriver) }
    Get-ChildItem -Path HKLM:\HARDWARE\UEFI\ESRT | % { 
        $esrt = $_
        $fwGuid = $esrt.Name.Split('{')[1].TrimEnd('}') | ? { $_.Length -eq 36 }
        $fwDriverInfo = $Win32_PNPSignedDriver | Where-Object -FilterScript { $_.HardwareID -like "*$fwGuid*" } 
        if ($fwDriverInfo.Description -like "*UEFI*") {
            Write-KeyVal "UEFI Version" $($fwDriverInfo.DriverVersion)
        }
        if ($fwDriverInfo.Description -like "*System Aggregator*") {
            Write-KeyVal "SAM Version" $($fwDriverInfo.DriverVersion)
        }
        if ($fwDriverInfo.Description -like "*Management*") {
            Write-KeyVal "ME Version" $($fwDriverInfo.DriverVersion)
        }
        if ($fwDriverInfo.Description -like "*Touch*") {
            Write-KeyVal "Touch Version" $($fwDriverInfo.DriverVersion)
        }
        if ($fwDriverInfo.Description -like "*Embedded Controller*") {
            Write-KeyVal "Controller Version" $($fwDriverInfo.DriverVersion)
        }
    }
    $ErrorActionPreference = 'Continue'

    # HOBL Version
    # TODO: if git can't be found, use hardcoded path to tools.  What if no git at all?  File in repo?
    # try {
    #     $ver = git -C $PSScriptRoot describe
    # }
    # catch {
    #     $ver = "ERROR"
    #     Write-Host -ForegroundColor Red "ERROR - git commmand failed"
    # }
    Write-KeyVal "HOBL Version" ""
    # try {
    #     $status = git -C $PSScriptRoot status --porcelain
    #     if ($status.Count) {
    #         Write-Host -ForegroundColor Yellow "WARNING - PowerTools working tree is not clean."
    #         Write-Host -ForegroundColor Yellow "$status"
    #     }
    # }
    # catch {
    #     Write-Host -ForegroundColor Red "ERROR - git commmand failed"
    # }

    
    # Office Version
    Write-KeyVal "Office Activation" (GetOfficeActivationStatus)

    # ErrorAction needs to be "Stop" for try/catch to catch a failure
    $ErrorActionPreference = 'Stop'

    # Office Version
    # Write-KeyVal "Office Version" (Get-AppsOffice)
    $ver = (get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\O365ProPlusRetail* | select-object DisplayVersion).DisplayVersion
    if (!$ver) {
        # Check 32b version
        $ver = (get-ItemProperty HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\O365ProPlusRetail* | select-object DisplayVersion).DisplayVersion
    }
    Write-KeyVal "Office Version" $ver

    # # Netflix Version
    # Load-AppxPackage
    # $ver = $AppxPackage | % { if ($_.Name -like "*Netflix*") { return $_.Version } }
    # Write-KeyVal "Netflix Version" $ver

    # Movies and TV Version
    Load-AppxPackage
    $ver = $AppxPackage | % { if ($_.Name -like "*ZuneVideo*") { return $_.Version } }
    Write-KeyVal "Movies and TV Version" $ver
	
    # Media Player Version
    $ver = $AppxPackage | % { if ($_.Name -like "*ZuneMusic*") { return $_.Version } }
    Write-KeyVal "Media Player Version" $ver

    # Windows Store Zune App Version
    # $zuneApp = Get-AppxPackage | Where-Object {$_.Name -like "*ZuneVideo*"}
    # Write-KeyVal "MS Zune App Version" $zuneApp

    # Old Edge Version
    # Load-AppxPackage
    # $ver = $AppxPackage | % { if ($_.Name -like "*MicrosoftEdge*") { return $_.Version } }
    # Write-KeyVal "Edge Version" $ver

    # Edge Version
    try {
        $ver = [System.Diagnostics.FileVersionInfo]::GetVersionInfo("C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe").FileVersion
        Write-KeyVal "Edge Version" $ver
    }
    catch {
        Write-KeyVal "Edge Version" "Not present"
    }

    # Edge Dev Version
    try {
        $ver = [System.Diagnostics.FileVersionInfo]::GetVersionInfo("C:\Program Files (x86)\Microsoft\Edge Dev\Application\msedge.exe").FileVersion
        Write-KeyVal "Edge Dev Version" $ver
    }
    catch {
        Write-KeyVal "Edge Dev Version" "Not present"
    }

    # Edge Beta Version
    try {
        $ver = [System.Diagnostics.FileVersionInfo]::GetVersionInfo("C:\Program Files (x86)\Microsoft\Edge Beta\Application\msedge.exe").FileVersion
        Write-KeyVal "Edge Beta Version" $ver
    }
    catch {
        Write-KeyVal "Edge Beta Version" "Not present"
    }

    # Edge Canary Version
    try {
        $ver = [System.Diagnostics.FileVersionInfo]::GetVersionInfo("c:\users\$env:username\appdata\local\microsoft\edge sxs\application\msedge.exe").FileVersion
        Write-KeyVal "Edge Canary Version" $ver
    }
    catch {
        Write-KeyVal "Edge Canary Version" "Not present"
    }

    # Chrome Version
    try {
        $ver = [System.Diagnostics.FileVersionInfo]::GetVersionInfo("c:\Program Files (x86)\Google\Chrome\Application\chrome.exe").FileVersion
        Write-KeyVal "Chrome Version" $ver
    }
    catch {
        Write-KeyVal "Chrome Version" "Not present"
    }

    # Chrome Canary Version
    try {
        $ver = [System.Diagnostics.FileVersionInfo]::GetVersionInfo("c:\users\$env:username\appdata\local\google\chrome sxs\application\chrome.exe").FileVersion
        Write-KeyVal "Chrome Canary Version" $ver
    }
    catch {
        Write-KeyVal "Chrome Canary Version" "Not present"
    }

    # Teams Version
    try {
        # $ver = (Get-Content "c:\users\$env:username\appdata\roaming\microsoft\teams\settings.json") | ConvertFrom-Json | Select Version
        $ver = (Get-AppxPackage -name msteams).Version
        Write-KeyVal "Teams Version" $ver
    }
    catch {
        Write-KeyVal "Teams Version" "Not present"
    }

    # Screen Brightness
    Write-KeyVal "Screen Brightness (%)" (Get-WmiObject -Class WmiMonitorBrightness -Namespace root/WMI -ErrorAction SilentlyContinue).CurrentBrightness

    # Adaptive Brightness Sensor
    if (((powercfg.exe /Q SCHEME_CURRENT SUB_VIDEO ADAPTBRIGHT | Select-String -Pattern "Current AC") -split ":" | select -last 1) -band 0x00000001) {
        $val = "Enabled"
    }
    else {
        $val = "Disabled"
    }
    Write-keyVal "Adaptive Brightness Sensor" $val


    # Audio Volume
    $vol = 0
    if (![audio]::Mute) {
        $vol = "{0:N0}" -f ([audio]::Volume * 100)
    }
    Write-KeyVal "Audio Volume (%)" $vol

    # RailCarID
    $railcar = Get-ItemProperty -Path "Registry::HKEY_LOCAL_MACHINE\Software\Microsoft\Surface\OSImage" -Name RailCarID -ErrorAction SilentlyContinue
    if ($railcar -ne $null) {
        Write-KeyVal "RailCarID" $railcar.RailCarID
    }

    # RailCarName
    $railcar = Get-ItemProperty -Path "Registry::HKEY_LOCAL_MACHINE\Software\Microsoft\Surface\OSImage" -Name RailCarName -ErrorAction SilentlyContinue
    if ($railcar -ne $null) {
        Write-KeyVal "RailCarName" $railcar.RailCarName
    }

   # Bitlocker State
    $blStatus = 'Off'
    # & "$env:SystemRoot\system32\manage-bde.exe"
    try {
        if (  manage-bde.exe -status | Where-Object { $_.Contains('Protection On') }) {
            $blStatus = 'On'
        }
    }
    catch {}
    Write-KeyVal "Bitlocker State" $blStatus

    # Secure Boot
    $ErrorActionPreference = 'SilentlyContinue'
    $sec_boot = Confirm-SecureBootUEFI
    if ($sec_boot -eq $true) {
        $val = "Enabled"
    }
    elseif ($Value -eq $false) {
        $val = "Disabled"
    }
    else {
        $val = "Not Supported" 
    }
    Write-KeyVal "Secure Boot" $val
    $ErrorActionPreference = 'Continue'

    # Desktop Image
    $wallpaper = (Get-ItemProperty -Path 'HKCU:\Control Panel\Desktop' -Name Wallpaper).Wallpaper
    if ($wallpaper) {
        Write-KeyVal "Desktop Image" (Split-Path $wallpaper -Leaf)
    }
    else {
        Write-KeyVal "Desktop Image" "None"
    }

    # Power Plan
    $val = ((Get-WmiObject -Class win32_powerplan -Namespace 'root/cimv2/power' | where { $_.IsActive -eq $true }).ElementName)
    Write-keyVal "Power Plan" $val

    # Power Mode Overlay (Effective)
    $powerMode = Get-PowerModeOverlay
    Write-KeyVal "Power Mode" $powerMode.Name
    # Write-KeyVal "Power Mode GUID" $powerMode.Guid

    $level = ((powercfg /Q SCHEME_BALANCED SUB_BATTERY BATLEVELCRIT | select-string -pattern "Current DC") -split ":" | select -last 1)
    Write-KeyVal "Critical Battery Level (%)" $level
    $val = ((powercfg /Q SCHEME_BALANCED SUB_VIDEO VIDEOIDLE | select-string -pattern "Current DC") -split ":" | select -last 1)
    Write-KeyVal "DC Turn Off Display After (min)" $val
    $val = ((powercfg /Q SCHEME_BALANCED SUB_VIDEO VIDEOIDLE | select-string -pattern "Current AC") -split ":" | select -last 1)
    Write-KeyVal "AC Turn Off Display After (min)" $val
    $val = ((powercfg /Q SCHEME_BALANCED SUB_SLEEP STANDBYIDLE | select-string -pattern "Current DC") -split ":" | select -last 1)
    Write-KeyVal "DC Sleep After (min)" $val
    $val = ((powercfg /Q SCHEME_BALANCED SUB_SLEEP STANDBYIDLE | select-string -pattern "Current AC") -split ":" | select -last 1)
    Write-KeyVal "AC Sleep After (min)" $val
    $val = ((powercfg /Q SCHEME_BALANCED SUB_SLEEP HIBERNATEIDLE | select-string -pattern "Current DC") -split ":" | select -last 1)
    Write-KeyVal "DC Hibernate After (min)" $val
    $val = ((powercfg /Q SCHEME_BALANCED SUB_SLEEP HIBERNATEIDLE | select-string -pattern "Current AC") -split ":" | select -last 1)
    Write-KeyVal "AC Hibernate After (min)" $val

    # Pen Config Info  ## Only on Surface devices - try SAM first, then KIP stops when it first finds config data. 
    $penParsed = $false
    foreach ($mcu in @("sam", "kip")) {
        try {
            if (Test-Path "C:\Tools\SMonitor\SMonitorUAP.exe") 
            {
                $penconfig = Invoke-WithTimeout "C:\Tools\SMonitor\SMonitorUAP.exe" "/mcu $mcu /wlcdevicestatus"
            } 
            else 
            {
                $penconfig = Invoke-WithTimeout "C:\Tools\SMonitor\SMonitor.exe" "/mcu $mcu /wlcdevicestatus"
            }
            # Output line should be on success calls: /wlcgetdevicestatus:  0x028B...  (double space -> token index 2 is the 0x value)
            $penraw = $penconfig.split("  ")[2].Substring(2)

            # First byte: 00 = no pen, 01 = docked not charging, 02 = charging
            $penByte = $penraw.Substring(0, 2)
            switch ($penByte) {
                "00" { $penStatus = "No pen" }
                "01" { $penStatus = "Docked not charging" }
                "02" { $penStatus = "Charging" }
                default { $penStatus = "Not Supported" }
            }

            Write-KeyVal "Pen Status" $penStatus
            # Charge value (second-to-last byte, hex->decimal) is only valid when a pen is present
            if ($penByte -eq "01" -or $penByte -eq "02") {
                $penRSOC = [System.Convert]::ToInt32($penraw.Substring($penraw.Length - 4, 2), 16)
                Write-KeyVal "Pen RSOC" $penRSOC
            }
            $penParsed = $true
            break
        } catch {
            continue
        }
    }
    if (-not $penParsed) {
        Write-KeyVal "Pen Status" "Not Supported"
    }   

    # Capture Time
    [datetime]$today = get-date
    Write-KeyVal "Capture Time" $today.ToString("yyyy-MM-dd HH:mm")

}

$table | Format-List

if ($LogFile -and -not $DisableFileLogging) {
    Write-Host "Writing configuration to $LogFile.csv"
    $table.PSObject.Properties | foreach-object {
        $line = $_.Name + "," + $_.Value
        $line | Out-File -Encoding ascii -Append -FilePath "$LogFile.csv"
    }
} 

#Write-Host (get-date).ToString("hh:mm:ss") "CfgChkLog - Finished everything"

exit 0


