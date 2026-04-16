
## DCARV's PLE version script, with support from Dan Wright
## Used to verify driver and firmware versions on the system  - match INF in supplied $Drivers path (image\support folder).
## Requires SUPPORT Folder - Use PLE's QuickImges, or Choose 'Y' to include Support folder using CreateUSB.ps1

## Version 2.3.12

Param(
    [string] $drivers = "C:\Support" ,
    [string] $Exclude_HWID = "PID_07C6;example",
    # Exclude will now replace * with &, to get around CMD calls and & char

    [string] $Exclude_File = "C:\Tools\PLE\TOAST\Misc\Setup\TrainInformation.xml",
    #[string] $Exclude_File = ".\ExcludeList.xml",

    [string] $testDeviceStatus = "true",
    [string] $testDeviceVersions = "true",
    [string] $testDriverSigning = "true",
    [string] $testFirmwareInf = "true",
    [string] $testFirmwareRollback = "true",
    [string] $testExtensionDrivers = "true",
    [string] $testFileSignatures = "true",
    [string] $testNullCapsules = "true",

    [string] $driversFullPath ,         # Used for translatinig paths to Sever using network automation
    [string] $xmlIteration = "1",       # Results file number or version
    [string] $xmlEnabled = "true"       # Create XML Results file
)
$Script:ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
Start-Transcript -Path "$Script:ScriptPath\VerifyOemDrivers_Transcript.txt" -Force | Out-Null
$Script:LocalExitCode = 0

$Script:ExitResults = [PSCustomObject]@{
    DeviceStateErrors = 0
    DriverSigningErrors = 0
    #DriverSigningExpectedDriversErrors = 0
    #DriverSigningInstalledDriversErrors = 0
    GeneralResultErrors = 0
    OemInfErrors = 0
    DriverSigningAlogrithmErrors = 0
    NullCapsuleErrors = 0
    InfRankErrors = 0
}

if ($testFileSignatures -ne "true") {
    $Script:ExitResults.DriverSigningAlogrithmErrors = "Skipped"
}

$Script:ResultsXmlWriter = $null
$script:ExcludeList = New-Object System.Collections.Generic.List[System.Object]


if (test-path "C:\Tools\PLE\TOAST\Messenger\ToastClientMessenger.exe") {
    c:\Tools\PLE\TOAST\Messenger\ToastClientMessenger.exe -s 0 -d "Running the Verfiy Versions Tool"
}


function Convert-Int32HexToVersionString {
    <#
    .SYNOPSIS
        Convert a 32-bit integer to www.xxx.yyy formatted version string.
    #>

    param (
      [Parameter(Mandatory=$true)]
      # Hex value to convert to www.xxx.yyy formatted version string
      [uint32] $HexNumber,
      # [DanW] Added $NumBits_xxx and $NumBits_yyy params
      [Parameter(Mandatory=$true)]
      [int] $NumBits_xxx,
      [Parameter(Mandatory=$true)]
      [int] $NumBits_yyy
    )
    $number = $HexNumber
    $bitmask = (1 -shl $NumBits_yyy) - 1
    $yyy = $number -band $bitmask

    $number = $number -shr $NumBits_yyy
    $bitmask = (1 -shl $NumBits_xxx) - 1
    $xxx = $number -band $bitmask

    $www = $number -shr $NumBits_xxx

    return "$www.$xxx.$yyy"
}

function Get-EsrtValues {

    param(
        # This parameter will output the results as a hash table. This is good for when you need to use the rusults in a script.
        [switch] $useHashTable
    )


    # Global
    <#
    BIT0   BIT9     MTE 0-255/Customer256-510/Development 512-1023  10 bits
    BIT10   BIT14   Day 1   31  5 bits
    BIT15   BIT18   Month 1   12    4 bits
    BIT19   BIT21   Year offset 0   7 (takes us to 2021)    3 bits
    BIT22   BIT25   Milestone/POC/EV1/EV2/EV3/DV/PV 4 bits
    BIT26   BIT31   Product specific  6 bits
    #>

    $NumBits_Year         = 3
    $NumBits_Month        = 4
    $NumBits_Day          = 5
    $NumBits_Type         = 10
    $NumBits_xxx          = $NumBits_Year + $NumBits_Month + $NumBits_Day
    $NumBits_yyy          = $NumBits_Type

    $fwAttemptStatusLookup = @{
        0 = 'Success'
        1 = 'Unsuccessful'
        2 = 'Insufficient resources'
        3 = 'Incorrect version'
        4 = 'Invalid image format'
        5 = 'Authentication error'
        6 = 'Power event - AC not connected'
        7 = 'Power event - Insufficient battery'
    }

        $fwTypeLookup = @{
        0 = 'Unknown'
        1 = 'System firmware'
        2 = 'Device firmware'
        3 = 'UEFI driver'
    }

    $resultArray = @()
    $resultHash = [ordered] @{}
    $esrtPath = 'HKLM:\HARDWARE\UEFI\ESRT'
    $esrtKeys = Get-ChildItem -Path $esrtPath

    ForEach ($key in $esrtKeys) {

        $keyName = Split-Path -Leaf $key.Name
        $props = Get-ItemProperty -LiteralPath $(Join-Path -Path $esrtPath -ChildPath $keyName)

        $lowestSupportedVersion_Bin = $props.LowestSupportedVersion
        $lastAttemptVersion_Bin     = $props.LastAttemptVersion
        $currVersion_Bin            = $props.Version

        # [DanW] Added -NumBits_xxx and -NumBits_yyy params and vars
        $currVersion_Str            = Convert-Int32HexToVersionString -HexNumber $( $currVersion_Bin ) -NumBits_xxx $NumBits_xxx -NumBits_yyy $NumBits_yyy
        $lastAttemptVersion_Str     = Convert-Int32HexToVersionString -HexNumber $( $lastAttemptVersion_Bin ) -NumBits_xxx $NumBits_xxx -NumBits_yyy $NumBits_yyy
        $lowestSupportedVersion_Str = Convert-Int32HexToVersionString -HexNumber $( $lowestSupportedVersion_Bin ) -NumBits_xxx $NumBits_xxx -NumBits_yyy $NumBits_yyy

        $lowestSupportedVersion_Bin = "0x{0}" -f $lowestSupportedVersion_Bin
        $lastAttemptVersion_Bin     = "0x{0}" -f $lastAttemptVersion_Bin
        $currVersion_Bin            = "0x{0}" -f $currVersion_Bin

        $type_Int = $props.Type
        $type_Str = $fwTypeLookup.$type_Int

        $lastAttemptStatus_Int = $props.LastAttemptStatus
        $lastAttemptStatus_Str = $fwAttemptStatusLookup.$lastAttemptStatus_Int


        $fwName_Guid = $keyName

        $returnProperties = [ordered] @{
            'FirmwareName_GUID' = $fwName_Guid
            'FirmwareName_String' = $fwName_Str
            "FirmwareType_Int" = $type_Int
            "FirmwareType_String" = $type_Str
            "LastInstallResult_Int" = $lastAttemptStatus_Int
            "LastInstallResult_String" = $lastAttemptStatus_Str
            "InstalledVersion_Binary" = $currVersion_Bin
            "InstalledVersion_VerStr" = $currVersion_Str
            "LastAttemptedVersion_Binary" = $lastAttemptVersion_Bin
            "LastAttemptedVersion_VerStr" = $lastAttemptVersion_Str
            "LowestSupportedVersion_Binary" = $lowestSupportedVersion_Bin
            "LowestSupportedVersion_VerStr" = $lowestSupportedVersion_Str
        }
    
        $objProperties = New-Object -TypeName psobject -Property $returnProperties
        $resultArray += $objProperties
        $resultHash.Add($fwName_Guid, $objProperties)
    }

    if ($useHashTable) {
        return $resultHash    # Easier to read for scripts.
    } else {
        return $resultArray    # Easier to read for humans.
    }

}


function TestDeviceStatus {
    $testName = "Checking that all devices are in good status."
    if (IsWttLogger) {Start-WTTTest $testName}

    # Get list of interesting devices
    "Getting devices that have Status codes greater the 0...." | OutputStatusMessage
    $BangedDevices = Get-WmiObject Win32_PNPEntity | Where-Object {$_.ConfigManagerErrorCode -gt 0 }

    # Get ESRT Info
    $esrt = Get-EsrtValues -useHashTable
    
    $NumberofBadDeviceStates = 0
    foreach ($Device in $BangedDevices)
    {
        $BangDeviceName =  $Device.name
        $BangDeviceCode = $Device.ConfigManagerErrorCode
        $BangDeviceID = $Device.deviceID
        $BangHardwareID = $Device.HardwareID

        # Skip excluded devices
        if (CheckForExlcude -deviceHWID $BangHardwareID) {continue}

        # Check firmware version is lower then ESRT Lowest_Supported_Version.  Unable to rollback.
        if ( ($BangDeviceCode -eq 10) -and ($BangDeviceID -like ("*{*}*") ))
        {

            "Firmware: '$BangDeviceName' has status code: $BangDeviceCode" | OutputStatusMessage
            "Checking Lowest Supported Version...." | OutputStatusMessage
            $fwGUID = "{" + $BangDeviceID.Split("{}")[1] + "}"
            
            $fwAttemptVer = $esrt.$fwGUID.LastAttemptedVersion_verstr
            $fwLowestSupportedVer = $esrt.$fwGUID.LowestSupportedVersion_verstr
            $fwInstallVersion = $esrt.$fwGUID.InstalledVersion_VerStr

            # Intel has different versioning
            if ($Device.name -like "ME")
            {
                $fwAttemptVer = Get-ItemPropertyValue "HKLM:\Hardware\UEFI\ESRT\$fwGUID" -Name LastAttemptVersion
                $fwLowestSupportedVer = Get-ItemPropertyValue "HKLM:\Hardware\UEFI\ESRT\$fwGUID" -Name LowestSupportedVersion
                $fwInstallVersion = Get-ItemPropertyValue "HKLM:\Hardware\UEFI\ESRT\$fwGUID" -Name Version
            }

            $logExpectedDriverInfo = "Firmware Info:" +
            "`n  Firmware name:`t`t$fwName" +
            "`n  Installed Version:`t`t$fwInstallVersion" +
            "`n  Last Attempted Version:`t$fwAttemptVer" +
            "`n  Lowest Supported Version:`t$fwLowestSupportedVer"
            $logExpectedDriverInfo | OutputStatusMessage

            if ($esrt.$fwGUID.LastAttemptedVersion_Binary -LT $esrt.$fwGUID.LowestSupportedVersion_Binary)
            {
                "ESRT shows attempted installed Firmware driver is lower than supported rollback version, skipping failure!" | OutputWarningMessage
                # Skip this device
                continue
            }
            

        }

        # Log banged devices to XML
        $DriverType = "Driver"
        if ( ($BangDeviceID -like ("*{*}*") )){
            $DriverType = "Firmware"
        }
        if ($BangDeviceName -eq $null){
            $Script:ResultsXmlWriter.WriteStartElement('Result')
            $Script:ResultsXmlWriter.WriteElementString('InfFilePath', "Unknown Device - This device is missing a driver!")
            $Script:ResultsXmlWriter.WriteElementString('DeviceName', $BangDeviceID)
            $Script:ResultsXmlWriter.WriteElementString('StatusCode', $BangDeviceCode)
            $Script:ResultsXmlWriter.WriteElementString('DriverType', $DriverType)
            $Script:ResultsXmlWriter.WriteEndElement()
        } else {
            $Script:ResultsXmlWriter.WriteStartElement('Result')
            $Script:ResultsXmlWriter.WriteElementString('InfFilePath', "NA")
            $Script:ResultsXmlWriter.WriteElementString('DeviceName', $BangDeviceName)
            $Script:ResultsXmlWriter.WriteElementString('StatusCode', $BangDeviceCode)
            $Script:ResultsXmlWriter.WriteElementString('DriverType', $DriverType)
            $Script:ResultsXmlWriter.WriteEndElement()
        }

        $NumberofBadDeviceStates += 1
        if (IsWttLogger)
        {
            "Device: '$($Device.name)' has status code: $($device.ConfigManagerErrorCode)" | OutputStatusMessage
            Stop-WTTTest -result "fail" -name $testName
        }
    }

    if ($NumberofBadDeviceStates -eq 0)
    {
        # Need at least one Pass/Fail result.
        "All devices are in good state!" | OutputStatusMessage
        if (IsWttLogger) {Stop-WTTTest -result "pass" -name $testName}

    }else{
        "$NumberofBadDeviceStates device(s) are in a bad state!" | OutputStatusMessage
        #DeviceStateErrors
        #$Script:LocalExitCode = 1
        $Script:ExitResults.DeviceStateErrors++
        if (IsWttLogger) {Stop-WTTTest -result "fail" -name $testName}

$DeviceCodes = @"

0 = "This device is working properly.",
1 = "This device is not configured correctly.",
2 = "Windows cannot load the driver for this device.",
3 = "The driver for this device might be corrupted, or your system may be running low on memory or other resources.",
4 = "This device is not working properly. One of its drivers or your registry might be corrupted.",
5 = "The driver for this device needs a resource that Windows cannot manage.",
6 = "The boot configuration for this device conflicts with other devices.",
7 = "Cannot filter.",
8 = "The driver loader for the device is missing.",
9 = "This device is not working properly because the controlling firmware is reporting the resources for the device incorrectly.",
10 = "This device cannot start.",
11 = "This device failed.",
12 = "This device cannot find enough free resources that it can use.",
13 = "Windows cannot verify this device's resources.",
14 = "This device cannot work properly until you restart your computer.",
15 = "This device is not working properly because there is probably a re-enumeration problem.",
16 = "Windows cannot identify all the resources this device uses.",
17 = "This device is asking for an unknown resource type.",
18 = "Reinstall the drivers for this device.",
19 = "Failure using the VxD loader.",
20 = "Your registry might be corrupted.",
21 = "System failure: Try changing the driver for this device. If that does not work, see your hardware documentation. Windows is removing this device.",
22 = "This device is disabled.",
23 = "System failure: Try changing the driver for this device. If that doesn't work, see your hardware documentation.",
24 = "This device is not present, is not working properly, or does not have all its drivers installed.",
25 = "Windows is still setting up this device.",
26 = "Windows is still setting up this device.",
27 = "This device does not have valid log configuration.",
28 = "The drivers for this device are not installed.",
29 = "This device is disabled because the firmware of the device did not give it the required resources.",
30 = "This device is using an Interrupt Request (IRQ) resource that another device is using.",
31 = "This device is not working properly because Windows cannot load the drivers required for this device.
"@    
    $DeviceCodes | OutputStatusMessage

    }
}

function GetDriverVersions {

    # Gather exclude list
    $exclude_HWID_List = $Exclude_HWID -split ';'
    foreach ($path in $exclude_HWID_List) 
    {
        "Excluded Hardware ID's: $path" | OutputStatusMessage
    }

    # Gather installed drivers, based on OEM*.INF
    $installedDrivers = Get-WMIObject WIN32_PnPSignedDriver | Where-Object { ($_.DeviceName -ne $null) -and ($_.InfName -like "oem*.inf") } | Sort-Object -Property DeviceName

    # Loop through installed drivers
    $driverNumber = 0
    $driverNamePrevious = $null
    foreach ($driver in $installedDrivers)
    {
        $driverName = $($driver.DeviceName)
        $driverVersion = $($driver.DriverVersion)
        $driverDate = "NotFound"
        $infInstalled = "NotFound"
        $infupdatedPath = "NA"
        $infUpdatedPath = "NA"
        $infDriverDate = "NA"
        $infDriverVersion = "NA"
        $driverType = "Driver"

        if ($driverName -eq $driverNamePrevious) {
            $driverNumber++
            $driverNameNumber = "_$driverNumber"
        } else {
            $driverNumber=0
            $driverNameNumber = $null
        }
        $driverNamePrevious = $driverName

        # SKIP EXCLUDED
        if (CheckForExlcude -deviceHWID $($driver.HardwareID)) { continue }

        # Driver info
        $d = $($driver.DriverDate)
        # Convert DATE: 20160621000000, to: 06/21/2016
        $driverDate = $d.Substring(4,2) + "/" + $d.Substring(6,2) + "/" + $d.Substring(0,4)
        $driverHWID = $($Driver.HardWareID)
        "Currently installed Date and Version: $driverDate, $driverVersion" | OutputStatusMessage

        $infInstalled = "$ENV:windir\inf\$($driver.InfName)"
        "INF of driver that is installed: $infInstalled" | OutputStatusMessage
        "Hardware ID: $driverHWID"  | OutputStatusMessage

        if ($Driver.HardWareID -match "uefi") {
            "Capsule HWID: $driverHWID" | OutputStatusMessage
        }

        if ( ($driverHWID -match '^UEFI\\') -and ($driver.DeviceClass -eq 'Firmware') ) {
            $driverType = "Firmware"
        }

        try {
            # .CAT will be OEM*.cat, no need to get cat name from INF info.
            $catFilePath = $env:windir + "\System32\CatRoot\{F750E6C3-38EE-11D1-85E5-00C04FC295EE}\" + ((split-path ($infInstalled) -leaf).replace(".inf", ".cat"))
            if (Test-Path -Path $catFilePath) {
                $catFile = Get-Item -Path $catFilePath
                if ($catFile.GetType().Name -match "file") {
                    # Get Catalog details
                    $certInfo = GetCertificateWithInfo -CatalogFile $catFilePath
                    # Check for OEM UEFI

                    $installedSigning = Confirm-Cert -certInfo $certInfo -infName $infInstalled -driverName $driverName

                } else {
                    "$catFilePath is not a file" | OutputStatusMessage
                    $installedSigning = "Catalog Not a file"
                }
            } else {
                "$catFilePath not found." | OutputStatusMessage
                $installedSigning = "$catFile - Not Found"
            }
        } catch {
            "$expectedDescription threw an exception`n$($_.Exception.Message)`n$($_.ScriptStackTrace)" | OutputErrorMessage
        }
          
                    # Log to XML
        # Friendly name, hwid, status, version, result
        $statusCode = (Get-WmiObject Win32_PNPEntity | Where-Object {$_.DeviceID -eq $($driver.DeviceID)} | Select-Object ConfigManagerErrorCode).ConfigManagerErrorCode
        $Script:ResultsXmlWriter.WriteStartElement('Result')
        $Script:ResultsXmlWriter.WriteElementString('InfFilePath', $infUpdatedPath)
        $Script:ResultsXmlWriter.WriteElementString('DriverDate', $driverDate)
        
        $driverName = $(Edit-String -InputString $driverName)
        $Script:ResultsXmlWriter.WriteElementString('DeviceName', $driverName + $driverNameNumber)
        
        $Script:ResultsXmlWriter.WriteElementString('StatusCode', $statusCode)
        $Script:ResultsXmlWriter.WriteElementString('DriverVersionInInfFile', $infDriverDate.trim() + ", " + $infDriverVersion.trim())
        $Script:ResultsXmlWriter.WriteElementString('DriverVersionInSystem', $driverDate.trim() + ", " + $driverVersion.trim())        
        $Script:ResultsXmlWriter.WriteElementString('DriverMatchStatus', "ignore")
        $Script:ResultsXmlWriter.WriteElementString('Rollback', "ignore")
        $Script:ResultsXmlWriter.WriteElementString('ExpectedSigning', "ignore")
        $Script:ResultsXmlWriter.WriteElementString('InstalledSigning', "$installedSigning")
        $Script:ResultsXmlWriter.WriteElementString('DriverType', "$driverType")
        $Script:ResultsXmlWriter.WriteEndElement()

    }
}



Function Get-RailCarID {
    try {
        $OSImageRegPath = 'HKLM:\SOFTWARE\Microsoft\Surface\OSImage'
        "Getting RailCarID value from registry path: $OSImageRegPath" | OutputStatusMessage

        if (Get-Item -Path env:PROCESSOR_ARCHITEW6432 -ErrorAction SilentlyContinue) {
            $HKLMkey = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine, [Microsoft.Win32.RegistryView]::Registry64)
            $OSImageKey = $HKLMkey.OpenSubKey('SOFTWARE\Microsoft\Surface\OSImage')
            [int]$RailCarID = $OSImageKey.GetValue('RailCarID')
        }
        elseif (Test-Path -Path $OSImageRegPath) {
            [int]$RailCarID = (Get-Item -Path $OSImageRegPath).GetValue('RailCarID')
        }
        else {
            throw "Could not determine RailCarID"
        }

        if ($null -eq $RailCarID) {
            throw "RailCarID not found"
        }
    
        "RailCarID: $RailCarID" | OutputStatusMessage
        return $RailCarID
    }
    catch {
        "Exception caught in Get-RailCarID. [Exception: $($_.Exception.Message)] - [Line: $($_.InvocationInfo.ScriptLineNumber)] - [File: $($_.InvocationInfo.ScriptName)]" | OutputStatusMessage
        return $null
    }
}


Function Get-TestNullCapsulesSkip {
    try {
        $RailcarImageRootPath = '\\plewusrv1\V2\_IMAGES'
        # Get Railcar path
        $RailCarID = Get-RailCarID
        if ($RailCarID) {
            if (Test-Path -Path "$RailcarImageRootPath\$RailCarID") {
                $RailcarImagePath = "$RailcarImageRootPath\$RailCarID"
            }
            elseif (Test-Path -Path "$RailcarImageRootPath\$($RailCarID)_BIP") {
                $RailcarImagePath = "$RailcarImageRootPath\$($RailCarID)_BIP"
            }
            elseif (Test-Path -Path "$RailcarImageRootPath\$($RailCarID)_ToCompareOnly") {
                $RailcarImagePath = "$RailcarImageRootPath\$($RailCarID)_ToCompareOnly"
            }
            else {
                throw "Railcar path not found"
            }
        }
        else {
            throw "Error getting RailcarID"
        }
        "Railcar path found: $RailcarImagePath" | OutputStatusMessage
        if (Test-Path -Path "$RailcarImagePath\TestNullCapsulesSkip.txt") {
            return $true
        }
        else {
        "To override the WTT failure, create TestNullCapsulesSkip.txt in this path: $RailcarImagePath" | OutputStatusMessage
        return $null
        }
    }
    catch {
        "Exception caught in Get-TestNullCapsuleSkip. [Exception: $($_.Exception.Message)] - [Line: $($_.InvocationInfo.ScriptLineNumber)] - [File: $($_.InvocationInfo.ScriptName)]" | OutputStatusMessage
        return $null
    }    
}


function VerifyVersions {

    # Get ESRT Info
    $esrt = Get-EsrtValues -useHashTable

    # Track INFs to log all INFS not used
    $InfsUsed =@{}

    # Track Excluded Devices
    $ExcludedDevices = @{}

    $driversFullPath = $driversFullPath.Trim()
    $driversFullPath = $driversFullPath.TrimEnd('\')
    "Drivers Full Path: $driversFullPath" | OutputStatusMessage
    if ([string]::IsNullOrWhitespace($driversFullPath))
    {
        "Drivers Full Path is empty." | OutputErrorMessage
    }
    
    # Gather INF files
    $infs = Get-ChildItem $drivers\* -Filter *.inf -Recurse | Where-Object {!$_.PsIsContainer}
    
    # Check for matching pnp in infs
    "Getting Driver Info" | OutputStatusMessage
    # $Win32PnPEntity = Get-CimInstance -ClassName Win32_PnPEntity
    $Win32SignedDriver = Get-CimInstance -ClassName Win32_PnPSignedDriver | Where-Object { ($_.DeviceName -ne $null) -and ($_.InfName -like "oem*.inf") } | Sort-Object -Property DeviceName
    foreach ($Driver in $Win32SignedDriver) {
        $MatchingDeviceID = (Get-PnpDeviceProperty -InstanceId $Driver.DeviceID -KeyName DEVPKEY_Device_MatchingDeviceId -ErrorAction SilentlyContinue).Data
        $Driver | Add-Member -NotePropertyName "MatchingDeviceID" -NotePropertyValue "$MatchingDeviceID" -Force
    }

    if ($env:PROCESSOR_ARCHITEW6432) {
        $Arch = $env:PROCESSOR_ARCHITEW6432
    }
    else {
        $Arch = $env:PROCESSOR_ARCHITECTURE
    }

    foreach ($inf in $infs) {
        $InfVerifInfo = & $Script:ScriptPath\infverif.$Arch.exe /info $inf.FullName
        foreach ($Driver in $Win32SignedDriver) {
            if (($Driver.MatchingDeviceID -ne "") -and ($null -ne $Driver.MatchingDeviceID)) {
                if ($InfVerifInfo | Select-String -Pattern $Driver.MatchingDeviceID -SimpleMatch) {
                    "Matching PnP Device ID found in inf: $($Driver.MatchingDeviceID) - $($inf.FullName)"| OutputStatusMessage
                    if ($inf.MatchingDeviceID) {
                        $inf.MatchingDeviceID += $Driver.MatchingDeviceID
                    }
                    else {
                        $inf | Add-Member -NotePropertyName "MatchingDeviceID" -NotePropertyValue @("$($Driver.MatchingDeviceID)") -Force
                    }
                }
            }

            # if (Select-String -Path $inf.FullName -Pattern $Driver.MatchingDeviceID -SimpleMatch) {
            #     "Matching Device ID found in inf: $($Driver.MatchingDeviceID) - $($inf.FullName)"| OutputStatusMessage
            #     if ($inf.MatchingDeviceID) {
            #         $inf.MatchingDeviceID += $Driver.MatchingDeviceID
            #     }
            #     else {
            #         $inf | Add-Member -NotePropertyName "MatchingDeviceID" -NotePropertyValue @("$($Driver.MatchingDeviceID)") -Force
            #     }
            # }
        }

        # if (!($inf.MatchingDeviceID)) {    
        #     # Some firmware infs split the PnP ID this section removes the root of the ID and searches for the "GUID" in the inf: MBFW\"{93911229-3868-46B4-90A2-6B52CB5B87DB}"
        #     foreach ($Driver in $Win32SignedDriver) {
        #         if ($Driver.DeviceClass -eq 'Firmware') {
        #             $MatchingDeviceIDFWGUID = $Driver.MatchingDeviceID.Split('\')[1].Trim()
        #             # "Checking Matching Device ID FW GUID: $MatchingDeviceIDFWGUID" | OutputStatusMessage 
        #             if (Select-String -Path $inf.FullName -Pattern $MatchingDeviceIDFWGUID -SimpleMatch) {
        #                 "Matching Device ID FW GUID found in inf: $MatchingDeviceIDFWGUID - $($inf.FullName)"| OutputStatusMessage
        #                 if ($inf.MatchingDeviceID) {
        #                     $inf.MatchingDeviceID += $Driver.MatchingDeviceID
        #                 }
        #                 else {
        #                     $inf | Add-Member -NotePropertyName "MatchingDeviceID" -NotePropertyValue @("$($Driver.MatchingDeviceID)") -Force
        #                 }
        #             }
        #         }
        #     }
        # }

        if (!($inf.MatchingDeviceID)) {
            "-- No matching PnP Device ID found for inf: $($inf.FullName)" | OutputStatusMessage
            $inf | Add-Member -NotePropertyName "Rank" -NotePropertyValue 3 -Force
            $inf | Add-Member -NotePropertyName "RankNote" -NotePropertyValue "No matching PnP Device ID found" -Force
        }
    }

    # Rank Infs Begin
    $infsGroups = $infs | Where-Object {$_.MatchingDeviceID} | Group-Object -Property Name

    foreach ($infsGroup in $infsGroups) {
        # Single inf
        if ($infsGroup.Count -eq 1) {
            "Only 1 inf: $($infsGroup.Group.FullName)" | Write-Host
            $infs | Where-Object {$_.FullName -eq $infsGroup.Group.FullName} | Add-Member -NotePropertyName "Rank" -NotePropertyValue 1 -Force
            $infs | Where-Object {$_.FullName -eq $infsGroup.Group.FullName} | Add-Member -NotePropertyName "RankNote" -NotePropertyValue "Single Inf" -Force
            continue
        }
        else {
            # Check for V2 infs
            [array]$v2FullNames = $infsGroup.Group.FullName | Where-Object {$_ -like "*\v2_w*"}
            if ($v2FullNames.Count -eq 1) {
                "1 v2 fullname $v2FullNames" | Write-Host -ForegroundColor Cyan
                $infs | Where-Object {$_.FullName -eq $v2FullNames} | Add-Member -NotePropertyName "Rank" -NotePropertyValue 1 -Force
                $infs | Where-Object {$_.FullName -eq $v2FullNames} | Add-Member -NotePropertyName "RankNote" -NotePropertyValue "Single v2 Inf" -Force
                continue
            }
            elseif ($v2FullNames.Count -gt 1) {
                $infFullNames = $v2FullNames
            }
            else {
                $infFullNames = $infsGroup.Group.FullName
            }

            # Rank infs by Date and Ver
            foreach ($infFullName in $infFullNames) {
                "Inf Rank Checking: $infFullName" | OutputStatusMessage
                [array]$infData = Get-Content -Path $infFullName
                $DriverVerLine = $infData | Where-Object {$_.Trim() -match "^DriverVer\s*="}
                "DriverVer Line: $DriverVerLine"  | OutputStatusMessage
                [array]$DriverVerArray = $DriverVerLine.Split(';')[0].Trim().Split('=')[1].Split(',')
                [datetime]$InfDate = $DriverVerArray[0] | Get-Date -f MM/dd/yyyy
                [version]$InfVersion = $DriverVerArray[1]

                if ($BestInfDate) {
                    # Newer date wins
                    "inf date: $InfDate" | Write-Host
                    "best inf date: $BestInfDate" | Write-Host
                    if ($InfDate -gt $BestInfDate) {
                        "Newer full name found based on date: $infFullName" | Write-Host -ForegroundColor Green
                        [string]$RankNote = "Better Date"
                        [datetime]$BestInfDate = $InfDate
                        [version]$BestInfVersion = $InfVersion
                        [string]$BestInfFullName = $infFullName
                        continue
                    }
                    # Same date newer version wins
                    elseif (($InfDate -eq $BestInfDate) -and ($InfVersion -gt $BestInfVersion)) {
                        "Newer full name found based on version: $infFullName" | Write-Host -ForegroundColor Green
                        [string]$RankNote = "Better Version"
                        [datetime]$BestInfDate = $InfDate
                        [version]$BestInfVersion = $InfVersion
                        [string]$BestInfFullName = $infFullName
                        continue
                    }
                    # Same date same version
                    elseif (($InfDate -eq $BestInfDate) -and ($InfVersion -eq $BestInfVersion)) {
                        "Full name found based on date and version: $infFullName" | Write-Host -ForegroundColor Green
                        [string]$RankNote = "Equal Date and Version"
                        $infs | Where-Object {$_.FullName -eq $BestInfFullName} | Add-Member -NotePropertyName "RankNote" -NotePropertyValue $RankNote -Force
                        [datetime]$BestInfDate = $InfDate
                        [version]$BestInfVersion = $InfVersion
                        [string]$BestInfFullName = $infFullName
                        $infs | Where-Object {$_.FullName -eq $BestInfFullName} | Add-Member -NotePropertyName "RankNote" -NotePropertyValue $RankNote -Force
                        continue
                    }    
                }
                # First inf checked wins
                else {
                    [string]$RankNote = "First Checked"
                    [datetime]$BestInfDate = $InfDate
                    [version]$BestInfVersion = $InfVersion
                    [string]$BestInfFullName = $infFullName
                    continue
                }
            }
            if ($RankNote -eq "Equal Date and Version") {
                $BestInfName = Split-Path -Path $BestInfFullName -Leaf
                $infs | Where-Object {(($_.Name -eq $BestInfName) -and ($_.RankNote -eq "Equal Date and Version"))} | Add-Member -NotePropertyName "Rank" -NotePropertyValue 1 -Force
            }
            else {
                $infs | Where-Object {$_.FullName -eq $BestInfFullName} | Add-Member -NotePropertyName "Rank" -NotePropertyValue 1 -Force
                $infs | Where-Object {$_.FullName -eq $BestInfFullName} | Add-Member -NotePropertyName "RankNote" -NotePropertyValue $RankNote -Force
            }
            Remove-Variable -Name RankNote -Force
            Remove-Variable -Name BestInfDate -Force
            Remove-Variable -Name BestInfVersion -Force
            Remove-Variable -Name BestInfFullName -Force
            continue
        }
    }

    $infs | Where-Object {$_.Rank -notin (1,3)} | Add-Member -NotePropertyName "Rank" -NotePropertyValue 2 -Force
    $infs | Where-Object {$_.Rank -notin (1,3)} | Add-Member -NotePropertyName "RankNote" -NotePropertyValue "Lower Rank" -Force
    # Rank Infs End
    
    # Gather installed drivers, based on OEM*.INF
    $installedDrivers = Get-WMIObject WIN32_PnPSignedDriver | Where-Object { ($_.DeviceName -ne $null) -and ($_.InfName -like "oem*.inf") } | Sort-Object -Property DeviceName

    # Loop through installed drivers
    $driverNumber = 0
    $driverNamePrevious = $null
    foreach ($driver in $installedDrivers) {
        
        $driverName = $driver.DeviceName
        $driverVersion = $($driver.DriverVersion)
        $driverDate = "NotFound"
        $infDriverDate = "NotFound"
        $infDriverVersion = "NotFound"
        $infInstalled = "NotFound"
        $MatchingDeviceID = "NotFound"
        $inf = $null
        $infUpdatedPath = "NotFound"
        $driverService = "NotFound"
        $driverFile = "NotFound"
        $rollbackPolicy = "False"
        $driverType = "Driver"
        [int]$rank = $null
        [string]$rankNote = $null

        # SKIP EXCLUDED
        if (CheckForExlcude -deviceHWID $($driver.HardwareID)) {
            # Add to list, will store in XML. Check for Duplicates
            if (-not $ExcludedDevices.ContainsKey($driverName)){
                $ExcludedDevices.add($driverName,$true)
            }
            continue
        }

        # Don't allow Duplicate Driver Names'
        if ($driverName -eq $driverNamePrevious) {
            $driverNumber++
            $driverNameNumber = "_$driverNumber"
        } else {
            $driverNumber=0
            $driverNameNumber = $null
        }
        $driverNamePrevious = $driverName

        # Test for OEM* strings
        $testName = "Verify device '$driverName' INF Manufacturer is not using OEM* string."
        if (IsWttLogger) {Start-WTTTest -name $testName}
        if (($driver.Manufacturer -like "OEM*") -and (-not $driver.DriverProviderName -like "OEM*UEFI*") ) {
            "FAIL $($driver.DeviceName) has manufacturer name: $($Driver.Manufacturer)" | OutputStatusMessage
            if (IsWttLogger) {Stop-WTTTest -result "Fail" -name $testName}
        } else {
            if (IsWttLogger) {Stop-WTTTest -result "Pass" -name $testName}
        }

        $testName = "Verify device '$driverName' INF Porvider is not using OEM* string."
        if (IsWttLogger) {Start-WTTTest -name $testName}
        if ( ($driver.DriverProviderName -match "OEM") -and (-not $driver.DriverProviderName -like "OEM*UEFI*") ) {
            "FAIL $($driver.DeviceName) has DriverProviderName name: $($Driver.DriverProviderName)" | OutputStatusMessage
            if (IsWttLogger) {Stop-WTTTest -result "Fail" -name $testName}
        } else {
            if (IsWttLogger) {Stop-WTTTest -result "Pass" -name $testName}
        }

        # Start device testing...
        " --- Looking for matching INF For device: $driverName ---" | OutputStatusMessage
        $testName = "'$driverName' using INF from expected driver share."
        if (IsWttLogger) {Start-WTTTest $testName}

        # Each OEM driver is expected to match.
        $infHash = $(Get-FileHash $ENV:windir\inf\$($driver.InfName)).Hash

        $HashCheckSuccess = $false
        # Loop through the INFs and log if we found a match.
        foreach ($inf in $infs) {

            $fileHash = $(Get-FileHash $inf.FullName).Hash
            $HashCheckSuccess = $false
            if ($fileHash -ne $infHash) {
                continue
            }

            $HashCheckSuccess = $true
            $xmlResult = "Verified"

            # Mark INF As being used - for logging at the end of test
            if (-not ($InfsUsed.ContainsKey($inf))) {
                $InfsUsed.add($inf, $true)
            }

            # Matching INF: $($inf.fullname)"  | OutputStatusMessage
            "Success: $driverName"  | OutputStatusMessage
            break

        }
        
        # Get Hardware ID that the PNP Manager matched on.
        #$escapedDeviceName = $driver.DeviceName -Replace "\(","\(" -replace "\)", "\)"
        # $MatchingDeviceID = $(Get-ChildItem -Path HKLM:\SYSTEM\CurrentControlSet\Control\Class\$($driver.ClassGUID) -exclude Properties | 
        #     Get-ItemProperty | 
        #     Where-Object {$_.DriverDesc -eq $driverName} |
        #     Select-Object -Property MatchingDeviceID).MatchingDeviceId

        $MatchingDeviceID = (Get-PnpDeviceProperty -InstanceId $driver.DeviceID -KeyName DEVPKEY_Device_MatchingDeviceId).Data
        
        if ($HashCheckSuccess -eq $false) {
            "FAILURE: $driverName"  | OutputStatusMessage
            $xmlResult = "INF Hash Mismatch"

            # find INF that has the FriendlyName and matching DeviceID string
            $infMatchingFiles=$(Get-ChildItem -Path $drivers -file -Recurse -include *.inf | 
                                Where-Object { $_ | Select-String -pattern $MatchingDeviceID -SimpleMatch} | 
                                Where-Object { $_ | Select-String -pattern $driverName -SimpleMatch} |
                                Where-Object { -not ($_.Name -eq "SurfaceNullCapsule.inf") } |
                                Get-Unique | Sort-Object LastWriteTime).fullname

            if ($infMatchingFiles.count -eq 1)
            {
                $inf = Get-ChildItem $infMatchingFiles

            } elseif ($infMatchingFiles -gt 1) {
                "WARNING: Multiple INF files found matching this device!  Selecting newest file by write time." | OutputStatusMessage
                $inf = Get-ChildItem $infMatchingFiles[0]

            } else {
                $inf = "NotFound"
                $xmlResult = "INF match Not Found"
            }
        } 
        
        # Gather and Log INF INFO
        $infCatName = "NotFound"
        $infCatFullPath = "NotFound"
        if (($inf -ne "NotFound") -and ($inf.FullName)) {
            $Content = Get-Content -Path $inf.FullName
            $Content | ForEach-Object { if ($_ -like "*DriverVer*=*,*") { $infDriverDate = ($_.Split(","))[0].Split('=')[1] -replace '([^;]*);.*',"`$1" } }
            $Content | ForEach-Object { if ($_ -like "*DriverVer*=*,*") { $infDriverVersion = ($_.Split(","))[1].split(';')[0] -replace '([^;]*);.*',"`$1" } }
            $Content | ForEach-Object { if ($_ -like "*CatalogFile.NT*=*") { $infCatName = ($_.Split(","))[0].Split('=')[1] -replace '([^;]*);.*',"`$1" } }
            $Content | ForEach-Object { if ($_ -like "*CatalogFile*=*") { $infCatName = ($_.Split(","))[0].Split('=')[1] -replace '([^;]*);.*',"`$1"} }
            $infUpdatedPath = $inf.fullname.Replace("C:\ExpectedDrivers",$driversFullPath)
            $infUpdatedPath = $infUpdatedPath.Replace("'","")
            $infCatFullPath = (split-path ($inf.fullname) -parent) + "\" + $infCatName.trim()
            $infCatFullPath = $infCatFullPath.Replace("\\","\")
            $rank = $inf.Rank
            $rankNote = $inf.RankNote
        }
        "Expected INF Driver Date and Version: $infDriverDate, $infDriverVersion" | OutputStatusMessage

        # Driver info
        $d = $($driver.DriverDate)
        # Convert DATE: 20160621000000, to: 06/21/2016
        $driverDate = $d.Substring(4,2) + "/" + $d.Substring(6,2) + "/" + $d.Substring(0,4)
        $driverHWID = $($Driver.HardWareID)
        "Currently installed Date and Version: $driverDate, $driverVersion" | OutputStatusMessage

        # Get the Service Binary (.sys)
        $driverService = (Get-WMIObject Win32_PnPEntity | Where-Object { ($_.DeviceID -ne $null) -and ($_.DeviceID -eq $($driver.DeviceID)) } | Sort-Object -Property DeviceID -Unique | Select-Object Service).Service
        if ($driverService -ne $null) {
            $driverFile = Split-path((Get-ItemProperty HKLM:\System\CurrentControlSet\Services\$driverService -name ImagePath).ImagePath) -leaf
        }

        # Print Info
        $infInstalled = "$ENV:windir\inf\$($driver.InfName)"
        "INF of driver that is installed: $infInstalled" | OutputStatusMessage
        "INF of driver that is expected: $infUpdatedPath" | OutputStatusMessage
        "Hardware ID: $driverHWID"  | OutputStatusMessage
        "PNP Matching HWID: $MatchingDeviceID" | OutputStatusMessage

        # Log result
        if ($HashCheckSuccess -eq $false) {
            "FAIL: Device NOT using INF from the expected Drivers Path. DeviceName: $driverName." | OutputStatusMessage
            if (IsWttLogger) {Stop-WTTTest -result "Fail" -name $testName}
        } else {
            "PASS: Device IS using INF from the expected Drivers. DeviceName: $driverName." | OutputStatusMessage
            if (IsWttLogger) {Stop-WTTTest -result "Pass" -name $testName}
        }

        # Firmware Checks
        if ( ($driverHWID -match '^UEFI\\') -and ($driver.DeviceClass -eq 'Firmware') ) {
            $XmlResultInf = $xmlResult
            $driverType = "Firmware"
            $testname = "'$driverName' firmware installed matches expected INF."
            if (IsWttLogger) {Start-WTTTest $testName}
            "Checking Firmware versions for $($driver.description)" | OutputStatusMessage

            # Get Machines Firmware info
            $fwGUID = "{" + $($driver.deviceID).Split("{}")[1] + "}"
            $fwAttemptVer = $esrt.$fwGUID.LastAttemptedVersion_verstr
            $fwLowestSupportedVer = $esrt.$fwGUID.LowestSupportedVersion_verstr
            $fwInstallVersion = $esrt.$fwGUID.InstalledVersion_VerStr

            # Intel has different versioning
            if ($Device.name -like "ME") {
                $fwAttemptVer = Get-ItemPropertyValue "HKLM:\Hardware\UEFI\ESRT\$fwGUID" -Name LastAttemptVersion
                $fwLowestSupportedVer = Get-ItemPropertyValue "HKLM:\Hardware\UEFI\ESRT\$fwGUID" -Name LowestSupportedVersion
                $fwInstallVersion = Get-ItemPropertyValue "HKLM:\Hardware\UEFI\ESRT\$fwGUID" -Name Version
            }

            # Log info
            $logExpectedDriverInfo = "Firmware Info:" +
            "`n  Firmware name:`t`t$fwName" +
            "`n  Installed Version:`t`t$fwInstallVersion" +
            "`n  Last Attempted Version:`t$fwAttemptVer" +
            "`n  Lowest Supported Version:`t$fwLowestSupportedVer"
            $logExpectedDriverInfo | OutputStatusMessage

            # Check for Lowest Supported Version
            if ($esrt.$fwGUID.LastAttemptedVersion_Binary -LT $esrt.$fwGUID.LowestSupportedVersion_Binary) {
                "WARNING: Firmware driver attempted install will not rollback without Manufacturing Mode !!!!!!!!!!" | OutputStatusMessage
            }

            # XML Updates
            # $driverDate = ""
            # $infDriverDate = ""
            #$xmlResult = "Verified"

            if ($driverHWID -notlike ("*}&*")) {
                $xmlResult = "INF match Not Found"
                "Unable to find hardware ID version, failing version check." | OutputStatusMessage
                if (IsWttLogger) { Stop-WTTTest -result "Fail" -name $testName }
            }
            elseif ($inf -eq "NotFound") {
                $xmlResult = "INF match Not Found"
                "INF Capsule not found, failing version check." | OutputStatusMessage
                if (IsWttLogger) { Stop-WTTTest -result "Fail" -name $testName }
            }
            else {
                
                $infContent = Get-Content -Path $inf.FullName
                $firmwareVerID = $driverHWID.substring($driverHWID.IndexOf("&REV_") + ("&REV_").Length)
                # Check for null capsule
                [array]$FirmwareVersionArray = $infContent | Where-Object { $_ -like 'HKR,,FirmwareVersion,*' }
                $NullCapsule = $true
                foreach ($FirmwareVersion in $FirmwareVersionArray) {
                    if ($FirmwareVersion -notmatch ',1$') {
                        $NullCapsule = $false
                    }
                }
                if ($NullCapsule) {
                    # Null Capsule
                    if (($driverName -in ('Surface DPP', 'Surface Elabeling (STAMPS)', 'Surface TOUCH')) -and ($infDriverVersion -like ("1.0.*")) -and ([datetime]$infDriverDate -lt [datetime]"01/01/2000") ) {
                        $xmlResult = "Factory Null Capsule (Passing)"
                        "INF Capsule does not contain Firmware (Factory Null Capsule)" | OutputStatusMessage
                        if (IsWttLogger) { Stop-WTTTest -result "Pass" -name $testName }
                    }
                    else {
                        $xmlResult = "NULL capsule, unable to get version"
                        "INF Capsule does not contain Firmware (NULL CAPSULE), failing version check." | OutputStatusMessage

                        # Check to see if SkipNullCapsuleTest.txt file exists
                        if ($testNullCapsules -eq 'true') {
                            if (Get-TestNullCapsulesSkip) { $testNullCapsules = 'false' }
                        }
                        
                        # Null Capsule WTT Test Result
                        if ( ($fwName -eq "Jupiter Touch" -and $fwInstallVersion -eq "660.0.256") -or ($fwName -eq "Cardinal EC" -and $fwInstallVersion -eq "117.1288.257") ) {
                            "$fwName firmware matches factory released version, changing failure to WARNING to null capsule." | OutputWarningMessage
                            if (IsWttLogger) { Stop-WTTTest -result "Pass" -name $testName }
                        }
                        elseif ($testNullCapsules -eq 'false') {
                            "Param testNullCapsules set to false" | OutputStatusMessage
                            if (IsWttLogger) { Stop-WTTTest -result "Pass" -name $testName }
                        }
                        else {
                            if (IsWttLogger) { Stop-WTTTest -result "Fail" -name $testName }
                            $Script:ExitResults.NullCapsuleErrors++
                        }
                    }
                }
                else {
                    # Real Capsule 
                    if ($infContent -like ("*firmwareversion*$firmwareVerID")) {
                        "Found HWID Version in INF" | OutputStatusMessage
                        if (IsWttLogger) { Stop-WTTTest -result "Pass" -name $testName }
                        $XmlResult = $XmlResultInf
                    }
                    else {
                        "Installed Firmware Revision: $firmwareVerID" | OutputStatusMessage
                        $driverVersion = $driverVersion + ", 0x$firmwareVerID"

                        $xmlResult = "Hardware (HWID Rev) Version Mismatch"
                        "ERROR: Did Not Find the installed firmware HWID in expected INF" | OutputStatusMessage

                        $infFirmwareVersionLine = $infContent -like ("*DriverVer*")
                        "Expected Version: $infFirmwareVersionLine" | OutputStatusMessage

                        $infFirmwareVersionLine = $infContent -like ("*firmwareversion*")
                        $infRev = $infFirmwareVersionLine.substring($infFirmwareVersionLine[0].IndexOf(",0x") + (",0x").Length)
                        "INF Firmware Revision: $infFirmwareVersionLine" | OutputStatusMessage
                        $infDriverVersion = $infDriverVersion + ", 0x$infRev"
                        if (IsWttLogger) { Stop-WTTTest -result "Fail" -name $testName }
                    }
                }
            }

            # Firmware Rollback Policy Check
            if (($inf.FullName) -and (test-path $inf.FullName)) {
                $rollbackPolicy = $false
                $infLine = Get-Content -path $Inf.FullName | Select-String -pattern ",Policy,%REG_DWORD%,1"
                if ( ($infLine -ne $null) -and ($inf.FullName -notlike "*OEM*UEFI.inf") ) {
                    $rollbackPolicy = $true
                }

                if ($testFirmwareRollback -eq "true") {
                    $testName = "Verify INF '$($inf.FullName)' is not setting a Policy Rollback registry key."
                    if (IsWttLogger) {Start-WTTTest -name $testName}
                    if ($rollbackPolicy -eq $true) {
                        "FAIL '$($inf.FullName)' has Policy Rollback registry key. Found: '$infLine'" | OutputStatusMessage
                        if (IsWttLogger) {Stop-WTTTest -result "Fail" -name $testName}
                    } else {
                        "PASS '$($inf.FullName)' Policy string not found." | OutputStatusMessage
                        if (IsWttLogger) {Stop-WTTTest -result "Pass" -name $testName}
                    }
                }else {
                    "testFirmwareRollback:$testFirmwareRollback - Skipping Firmware Rollback Policy check." | OutputStatusMessage
                }
            } 

        } # Capsule check

        #region DriverSigningTest
        "Getting Signing info..." | OutputStatusMessage
        $testName = "Verify Expected device '$driverName' driver is signed correctly."
        $testPassed = $false
        $expectedSigning = "NotFound"
        $catFile = "NotFound"

        # Verify Signing on Expected drivers
        try {
            if (Test-Path -Path $infCatFullPath) {
                $catFile = Get-Item -Path $infCatFullPath
                if ($catFile.GetType().Name -match "file") {

                    # Get Catalog details
                    $certInfo = GetCertificateWithInfo -CatalogFile $infCatFullPath
                    $expectedSigning = Confirm-Cert -certInfo $certInfo -infName $infUpdatedPath -driverName $driverName
                    if ($expectedSigning -in ("WHQL","OEMUEFI")) {$testPassed = $true}

                } else {
                    "$catFilePath is not a file" | OutputStatusMessage
                    $expectedSigning = "Catalog Not a file"
                }
            } else {
                "$infCatFullPath not found." | OutputStatusMessage
                if ($inf -ne "NotFound") {
                    $expectedSigning = "$infCatFullPath - Not Found"
                } else {
                    $expectedSigning = "N/A"
                }
            }
        } catch {
            "$expectedDescription threw an exception`n$($_.Exception.Message)`n$($_.ScriptStackTrace)" | OutputErrorMessage
        }

        # Log Pass Fail as requested
        if ($testDriverSigning -eq "true"){
            if (IsWttLogger) {Start-WTTTest -name $testName}
            if ($testPassed) {
                if (IsWttLogger) {Stop-WTTTest -result "Pass" -name $testName}
            } else {
                "  Inf File Path: $infUpdatedPath" | OutputStatusMessage
                "  Inf Catalog Path: $catFilePath" | OutputStatusMessage
                "  Inf Catalog FULL Path: $infCatFullPath" | OutputStatusMessage
                if (IsWttLogger) { Stop-WTTTest -result "Fail" -name $testName}

                # Update Return code if Signing issue Found
                if ( ($expectedSigning -ne "WHQL") -and ($expectedSigning -ne "OEMUEFI") ) {
                    "Signing Check Failed, Setting Exit to 1" | OutputStatusMessage
                    #DriverSigningErrors
                    #$Script:LocalExitCode = 1
                    $Script:ExitResults.DriverSigningErrors++
                }
            }
        } else {
            " - Skipping Signing Check" | OutputStatusMessage
        }

        # Verify Signing on the Installed Drivers
        $testName = "Verify Installed device '$driverName' driver is signed correctly."
        $testPassed = $false
        $installedSigning = "NotFound"
        $catFile = "NotFound"
        try {
            # .CAT will be OEM*.cat, no need to get cat name from INF info.
            $catFilePath = $env:windir + "\System32\CatRoot\{F750E6C3-38EE-11D1-85E5-00C04FC295EE}\" + ((split-path ($infInstalled) -leaf).replace(".inf", ".cat"))
            if (Test-Path -Path $catFilePath) {
                $catFile = Get-Item -Path $catFilePath
                if ($catFile.GetType().Name -match "file") {
                    # Get Catalog details
                    $certInfo = GetCertificateWithInfo -CatalogFile $catFilePath
                    # Check for OEM UEFI
                    $installedSigning = Confirm-Cert -certInfo $certInfo -infName $infInstalled -driverName $driverName
                    if ($installedSigning -in ("WHQL","OEMUEFI")) {$testPassed = $true}
                } else {
                    "$catFilePath is not a file" | OutputStatusMessage
                    $installedSigning = "Catalog Not a file"
                }
            } else {
                "$catFilePath not found." | OutputStatusMessage
                $installedSigning = "$catFile - Not Found"
            }
        } catch {
            "$expectedDescription threw an exception`n$($_.Exception.Message)`n$($_.ScriptStackTrace)" | OutputErrorMessage
        }

        # Log Pass Fail as requested
        if ($testDriverSigning -eq "true"){
            if (IsWttLogger) {Start-WTTTest -name $testName}
            if ($testPassed) {
                if (IsWttLogger) {Stop-WTTTest -result "Pass" -name $testName}
            } else {
                "  Inf File Path: $infUpdatedPath" | OutputStatusMessage
                "  Inf Catalog Path: $catFilePath" | OutputStatusMessage
                if (IsWttLogger) { Stop-WTTTest -result "Fail" -name $testName}

                # Update Return code if Signing issue Found
                if ( ($installedSigning -ne "WHQL") -and ($installedSigning -ne "OEMUEFI") ) {
                    "Signing Check Failed, Setting Exit to 1" | OutputStatusMessage
                    #DriverSigningErrors
                    #$Script:LocalExitCode = 1
                    $Script:ExitResults.DriverSigningErrors++
                }
            }
        } else {
            " - Skipping Signing Check" | OutputStatusMessage
        }

        "Getting Signing info... Complete." | OutputStatusMessage
        #endregion DriverSigningTest

        # Override - Null Capsule Faulure (Log this info, although not fail)
        if ($xmlResult -eq "NULL capsule, unable to get version") {
            if ($testNullCapsules -eq 'false') {
                "Override Null Capsule failure, Setting NullCapsuleErrors to [Skipped]" | OutputStatusMessage
                #NullCapsuleErrors
                #$Script:LocalExitCode = 0
                $Script:ExitResults.NullCapsuleErrors = "Skipped"
            }
        }
        # Fail on Result and Rollback Policy
        elseif ( (($xmlResult -notin ("Verified","Factory Null Capsule (Passing)")) -or ($($rollbackPolicy) -ne $false)) -and ($inf.FullName -notlike "*\autorun.inf") ) {
            "Version or Rollback failed, Setting Exit to 1" | OutputStatusMessage
            #GeneralResultErrors
            #$Script:LocalExitCode = 1
            $Script:ExitResults.GeneralResultErrors++
        }

        $testName = "Rank Test"
        if (IsWttLogger) {Start-WTTTest -name $testName}
        if (($rank -ne 1) -and ($xmlResult -eq 'Verified')) {
            "  Unexpected inf rank" | OutputStatusMessage
            if (IsWttLogger) { Stop-WTTTest -result "Fail" -name $testName}
            $xmlResult = 'Unexpected Version'
            $Script:ExitResults.InfRankErrors++
            if ($inf.Name) {
                $expectedInf = $infs | Where-Object {(($_.Name -eq $inf.Name) -and ($_.Rank -eq 1))}
                if ($expectedInf.FullName) {
                    [array]$expectedInfData = Get-Content -Path $expectedInf.FullName
                    $DriverVerLine = $expectedInfData | Where-Object {$_.Trim() -match "^DriverVer\s*="}
                    # [array]$DriverVerLineSplit = $DriverVerLine.Split('=')
                    [array]$DriverVerArray = $DriverVerLine.Split('=')[1].Split(',')
                    [string]$infDriverDate = $DriverVerArray[0] | Get-Date -f MM/dd/yyyy
                    [string]$infDriverVersion = $DriverVerArray[1]
                }
            }
        }
        else {
            if (IsWttLogger) {Stop-WTTTest -result "Pass" -name $testName}
        }

        # Log to XML as requested
        if ($xmlEnabled -eq "true") { 
            $statusCode = (Get-WmiObject Win32_PNPEntity | Where-Object {$_.DeviceID -eq $($driver.DeviceID)} | Select-Object ConfigManagerErrorCode).ConfigManagerErrorCode
            $Script:ResultsXmlWriter.WriteStartElement('Result')
            $Script:ResultsXmlWriter.WriteElementString('InfFilePath', $infUpdatedPath)
            $Script:ResultsXmlWriter.WriteElementString('DriverDate', $driverDate)

            $driverName = $(Edit-String -InputString $driverName)
            $Script:ResultsXmlWriter.WriteElementString('DeviceName', $driverName + $driverNameNumber)

            $Script:ResultsXmlWriter.WriteElementString('DriverFile', $driverFile)
            $Script:ResultsXmlWriter.WriteElementString('DriverVersionInInfFile', $infDriverDate.trim() + ", " + $infDriverVersion.trim())
            $Script:ResultsXmlWriter.WriteElementString('DriverVersionInSystem', $driverDate.trim() + ", " + $driverVersion.trim())
            $Script:ResultsXmlWriter.WriteElementString('DriverMatchStatus', $xmlResult)
            $Script:ResultsXmlWriter.WriteElementString('StatusCode', $statusCode)
            $Script:ResultsXmlWriter.WriteElementString('Rollback', $($rollbackPolicy))
            $Script:ResultsXmlWriter.WriteElementString('ExpectedSigning', $expectedSigning)
            $Script:ResultsXmlWriter.WriteElementString('InstalledSigning', $installedSigning)
            $Script:ResultsXmlWriter.WriteElementString('DriverType', $driverType)
            $Script:ResultsXmlWriter.WriteElementString('HwIDMatch', $MatchingDeviceID)
            $Script:ResultsXmlWriter.WriteElementString('Rank', $rank)
            $Script:ResultsXmlWriter.WriteElementString('RankNote', $rankNote)
            $Script:ResultsXmlWriter.WriteEndElement()
        }
    }

    # INF Tests
    foreach ($inf in $infs) {
        if ($null -eq $inf.FullName) {continue}
        # Log INFS not installed, and signing
        if ( ($xmlEnabled -eq "true") -and (-not ($InfsUSed.ContainsKey($inf))) -and ($inf.FullName -notlike "*\autorun.inf") ) {
            # Skip if extension driver
             if (($inf.FullName) -and (Get-Content $inf.FullName | select-string -pattern "e2f84ce7-8efa-411c-aa69-97454ca4cb57")) {
                continue
             }

            # Get Sigining Info
            $Content = Get-Content -Path $inf.FullName
            $Content | ForEach-Object { if ($_ -like "*CatalogFile.NT*=*") { $infCatName = ($_.Split(","))[0].Split('=')[1] -replace '([^;]*);.*',"`$1" } }
            $Content | ForEach-Object { if ($_ -like "*CatalogFile*=*") { $infCatName = ($_.Split(","))[0].Split('=')[1] -replace '([^;]*);.*',"`$1"} }
            $infCatFullPath = (split-path ($inf.fullname) -parent) + "\" + $infCatName.trim()
            $infCatFullPath = $infCatFullPath.Replace("\\","\")
            
            "inf: $($inf.FullName)" | OutputStatusMessage
            "infCatFullPath: $infCatFullPath" | OutputStatusMessage

            $certInfo = GetCertificateWithInfo -CatalogFile $infCatFullPath
            $signed = Confirm-Cert -certInfo $certInfo -infName $inf.Name -driverName $inf.Name

            # Firmware Rollback Policy Check
            if (test-path $inf.FullName ) {
                $rollbackPolicy = $false
                $infLine = Get-Content -path $Inf.FullName | Select-String -pattern ",Policy,%REG_DWORD%,1"
                if ( ($infLine -ne $null) -and ($inf.FullName -notlike "*OEM*UEFI.inf") ) {
                    $rollbackPolicy = $true
                }

                if ($testFirmwareRollback -eq "true") {
                    $testName = "Verify INF '$($inf.FullName)' is not setting a Policy Rollback registry key."
                    if (IsWttLogger) {Start-WTTTest -name $testName}
                    if ($rollbackPolicy -eq $true) {
                        "FAIL '$($inf.FullName)' has Policy Rollback registry key. Found: '$infLine'" | OutputStatusMessage
                        if (IsWttLogger) {Stop-WTTTest -result "Fail" -name $testName}
                    } else {
                        "PASS '$($inf.FullName)' Policy string not found." | OutputStatusMessage
                        if (IsWttLogger) {Stop-WTTTest -result "Pass" -name $testName}
                    }
                }else {
                    "testFirmwareRollback:$testFirmwareRollback - Skipping Firmware Rollback Policy check." | OutputStatusMessage
                }
            } 

            "Not installed: $($inf.FullName)" | OutputStatusMessage
            $Script:ResultsXmlWriter.WriteStartElement('NotFound')
            $Script:ResultsXmlWriter.WriteElementString('NotInstalled', $($inf.FullName))
            $Script:ResultsXmlWriter.WriteElementString('Rollback', $($rollbackPolicy))
            $Script:ResultsXmlWriter.WriteElementString('Signed', $($signed))
            $Script:ResultsXmlWriter.WriteElementString('Rank', $inf.rank)
            $Script:ResultsXmlWriter.WriteElementString('RankNote', $inf.rankNote)
            $Script:ResultsXmlWriter.WriteEndElement()
       }
    }


    # Loop Excluded Devices
    if ($ExcludedDevices -ne $null) {
        foreach ($excludedDevice in $ExcludedDevices.GetEnumerator())
        {
            # Log if requested
            if ($xmlEnabled -eq "true")
            {
                "Excluded Device $($excludedDevice.name)" | OutputStatusMessage
                $Script:ResultsXmlWriter.WriteStartElement('Excluded')
                $Script:ResultsXmlWriter.WriteElementString('ExcludedDevice', $($excludedDevice.name))
                $Script:ResultsXmlWriter.WriteEndElement()
            }
        }
    }
}

function VerifyExtensionDrivers {
    "-- VerifyExtensionDrivers Start" | OutputStatusMessage
    Write-Progress -Activity "Getting OEM Drivers Info"
    # Track INFs to log all INFS not used
    $InfsUsed =@{}

    # Gather INSTALLED Extension INF's
    $ExtensionDrivers = ((Get-ChildItem -Recurse -Path $env:SystemRoot\System32\DriverStore\FileRepository -Filter *.inf | Where-Object {!$_.PsIsContainer -and $_.name -ne "c_extension.inf"}) | Where-Object {Get-Content $_.pspath | Select-String -pattern "e2f84ce7-8efa-411c-aa69-97454ca4cb57"}).FullName

    # Gather EXPECTED INF Extension INF's
    $infs = (Get-ChildItem $drivers\* -Filter *.inf -Recurse | Where-Object {!$_.PsIsContainer} | Where-Object {Get-Content $_.pspath | Select-String -pattern "e2f84ce7-8efa-411c-aa69-97454ca4cb57"}).fullname

    # Get OEM extension infs from $env:windir\inf
    [array]$OemInfs = Get-ChildItem $env:windir\inf\oem*.inf -Recurse | Where-Object {!$_.PsIsContainer} | Where-Object {Get-Content $_.pspath | Select-String -pattern "e2f84ce7-8efa-411c-aa69-97454ca4cb57"}
    $DriverCount = 0
    foreach ($OemInf in $OemInfs) {
        $DriverCount++
        $PercentComplete = [math]::floor([decimal]($DriverCount / $OemInfs.Count * 100))
        #Write-Progress -Activity "Verifying Drivers" -Completed
        Write-Progress -Activity "Getting OEM Drivers Info" -Status "$PercentComplete% Complete - File Name: $($OemInf.Name)" -PercentComplete $PercentComplete

        # # Get OEM inf hash values
        # $FileHash = $(Get-FileHash -Path $OemInf.FullName).Hash
        # "Oem Inf File: $($OemInf.FullName) - Hash: $FileHash" | OutputStatusMessage
        # $OemInf | Add-Member -NotePropertyName 'FileHash' -NotePropertyValue $FileHash
        
        # Get OEM inf driver info
        [array]$OemInfDriverInfo = Get-WindowsDriver -Driver $OemInf.Name -Online
        $OemInf | Add-Member -MemberType NoteProperty -Name "OemInfDriverInfo" -Value $OemInfDriverInfo
    }
    Write-Progress -Activity "Getting OEM Drivers Info" -Completed

    # Get ExtendedConfigurationIdsData per device for OEM extension inf data
    "Getting PnP Device Info" | OutputStatusMessage
    $Win32PnPEntity = Get-CimInstance -ClassName Win32_PnPEntity
    Write-Progress -Activity "Getting Extension Drivers Info"
    foreach ($Device in $Win32PnPEntity) { 
        $DeviceCount++
        $PercentComplete = [math]::floor([decimal]($DeviceCount / $Win32PnPEntity.Count * 100))
        #Write-Progress -Activity "Verifying Drivers" -Completed
        Write-Progress -Activity "Getting Extension Drivers Info" -Status "$PercentComplete% Complete - Device: $($Device.Name)" -PercentComplete $PercentComplete
        if ($Device.DeviceID) {
            $ExtendedConfigurationIdsData = (Get-PnpDeviceProperty -InstanceId $Device.DeviceID -KeyName DEVPKEY_Device_ExtendedConfigurationIds -ErrorAction SilentlyContinue).Data
            $Device | Add-Member -NotePropertyName 'ExtendedConfigurationIdsData' -NotePropertyValue $ExtendedConfigurationIdsData 
        }
    }
    Write-Progress -Activity "Getting Extension Drivers Info" -Completed

    # Loop through all Expected Extension INF's
    foreach ($inf in $infs) {
        "--- Checking $inf" | OutputStatusMessage
        $driverDate = "NotFound"
        $driverVersion = "NotFound"
        $DriverFullName = "NotFound"
        $DriverCatName = "NotFound"
        $catFilePath = "NotFound"
        $installedSigning = "NotFound"
        $infDriverDate = "NotFound"
        $infDriverVersion = "NotFound"
        $infCatName = "NotFound"
        $infCatFullPath = "NotFound"
        $infUpdatedPath = "NotFound"
        $xmlResult = "NotMatched"
        $ExtDeviceName = "NotFound"

        $infHash = $(Get-FileHash $inf).Hash
        #"Looking at: $inf with HASH: $infhash" | OutputStatusMessage
        [array]$InfDriverFiles = $null
        [array]$DriverFileExtensions = @('*.inf','*.cat','*.sys','*.bin')
        $infParentPath = Split-Path -Path $inf -Parent
        if (Test-Path -Path $infParentPath) {
            "-- Inf driver path: $infParentPath" | OutputStatusMessage
            [array]$InfDriverFiles = Get-ChildItem -Path "$infParentPath\*" -Include $DriverFileExtensions
            #"-- Inf driver files: `n$(($InfDriverFiles.Name | Out-String).Trim())" | OutputStatusMessage
            # Get file hash values
            if ($InfDriverFiles) {
                foreach ($InfDriverFile in $InfDriverFiles) {
                    $FileHash = $(Get-FileHash -Path $InfDriverFile.FullName).Hash
                    #"-- Inf Driver File: $($InfDriverFile.FullName)" | OutputStatusMessage
                    #"-- Hash: $FileHash" | OutputStatusMessage
                    $InfDriverFile | Add-Member -NotePropertyName 'FileHash' -NotePropertyValue $FileHash
                }
            }
        }

        # Loop through the INSTALLED INFs and look for a match.
        foreach ($driver in $ExtensionDrivers) {
            # $ExtDeviceName = Split-Path -Path $driver -Leaf
            # "========= Checking $driver" | OutputStatusMessage
            $ExtDeviceName = "NotFound"
            $fileHash = $(Get-FileHash $driver).Hash
            if ($fileHash -ne $infHash) {
                continue
            }
            else {
                if ($InfDriverFiles) {
                    $ExtensionDriverParentPath = Split-Path -Path $driver -Parent
                    if (Test-Path -Path $ExtensionDriverParentPath) {
                        #"++ Driver store path: $ExtensionDriverParentPath" | OutputStatusMessage
                        [array]$ExtensionDriverFiles = Get-ChildItem -Path "$ExtensionDriverParentPath\*" -Include $DriverFileExtensions
                        #"++ Driver store files: `n$(($ExtensionDriverFiles.Name | Out-String).Trim())" | OutputStatusMessage
                        # Get file hash values
                        if ($ExtensionDriverFiles) {
                            foreach ($ExtensionDriverFile in $ExtensionDriverFiles) {
                                $FileHash = $(Get-FileHash -Path $ExtensionDriverFile.FullName).Hash
                                #"++ Extension Driver File: $($ExtensionDriverFile.FullName)" | OutputStatusMessage
                                #"++ Hash: $FileHash" | OutputStatusMessage
                                $ExtensionDriverFile | Add-Member -NotePropertyName 'FileHash' -NotePropertyValue $FileHash
                            }

                            $DriverMatch = $false
                            foreach ($InfDriverFile in $InfDriverFiles) {
                                if ($InfDriverFile.Name -in ($ExtensionDriverFiles.Name)) {
                                    "Checking $($InfDriverFile.Name) for hash match" | OutputStatusMessage
                                    "Hash: $($InfDriverFile.FileHash)" | OutputStatusMessage
                                    if ($InfDriverFile.FileHash -in ($ExtensionDriverFiles.FileHash)) {
                                        "Matched" | OutputStatusMessage
                                        $DriverMatch = $true
                                        continue
                                    }
                                    else {
                                        "No match" | OutputStatusMessage
                                        $DriverMatch = $false
                                        break
                                    }
                                }
                            }

                            if ($DriverMatch -ne $true) {
                                "**** Driver match not found" | OutputStatusMessage
                                continue
                            }
                        }
                    }
                }
            }

            # Mark DRIVER As being used - for logging at the end of test
            if (-not ($InfsUsed.ContainsKey($driver))) {
                $InfsUsed.add($driver, $true)
            }

            $xmlResult = "Verified"

            #"Matching INF: $inf"  | OutputStatusMessage
            "SUCCESS!! - Found Matching INF: $driver" | OutputStatusMessage
            break
        }

        if ($xmlResult -ne "Verified") { 
            "FAIL!! - Did not find matching INF" | OutputStatusMessage
            $driver = "NotFound"
        } 

        # Get info from Expected INF
        $Content = Get-Content -Path $inf
        $Content | ForEach-Object { if ($_ -like "*DriverVer*=*,*") { $infDriverDate = ($_.Split(","))[0].Split('=')[1] -replace '([^;]*);.*',"`$1" } }
        $Content | ForEach-Object { if ($_ -like "*DriverVer*=*,*") { $infDriverVersion = ($_.Split(","))[1].split(';')[0] -replace '([^;]*);.*',"`$1" } }
        $Content | ForEach-Object { if ($_ -like "*CatalogFile.NT*=*") { $infCatName = ($_.Split(","))[0].Split('=')[1] -replace '([^;]*);.*',"`$1" } }
        $Content | ForEach-Object { if ($_ -like "*CatalogFile*=*") { $infCatName = ($_.Split(","))[0].Split('=')[1] -replace '([^;]*);.*',"`$1"} }
        $infUpdatedPath = $inf.Replace("C:\ExpectedDrivers",$driversFullPath)
        $infUpdatedPath = $infUpdatedPath.Replace("'","")
        $infCatFullPath = (split-path $inf -parent) + "\" + $infCatName.trim()
        $infCatFullPath = $infCatFullPath.Replace("\\","\")

        # Check the Expected Driver INF, or log NotFound.  This is from C:\Support folder
        "Getting Signing info..." | OutputStatusMessage
        $expectedSigning = "NotFound"  
        $catFile = "NotFound"
        try {
            if (Test-Path -Path $infCatFullPath) {
                $catFile = Get-Item -Path $infCatFullPath
                if ($catFile.GetType().Name -match "file") {
                    $DriverInfName = Split-Path $inf -Leaf
                    # Get Catalog details
                    $certInfo = GetCertificateWithInfo -CatalogFile $infCatFullPath
                    $expectedSigning = Confirm-Cert -certInfo $certInfo -infName $DriverInfName -driverName $DriverInfName -infType "Extension"

                } else {
                    "$catFilePath is not a file" | OutputStatusMessage
                    $expectedSigning = "Catalog Not a file"
                }
            } else {
                "$infCatFullPath not found." | OutputStatusMessage
                if ($inf -ne "NotFound") {
                    $expectedSigning = "Not Found"
                } else {
                    $expectedSigning = "N/A"
                }
            }
        } catch {
            "$expectedDescription threw an exception`n$($_.Exception.Message)`n$($_.ScriptStackTrace)" | OutputErrorMessage  
        }

        if ($Driver -ne "NotFound") {

            # Verify Signing on the Installed Driver -
            $testPassed = $false
            try {

                $Content = Get-Content -Path $Driver
                $Content | ForEach-Object { if ($_ -like "*DriverVer*=*,*") { $DriverDate = ($_.Split(","))[0].Split('=')[1] -replace '([^;]*);.*',"`$1" } }
                $Content | ForEach-Object { if ($_ -like "*DriverVer*=*,*") { $DriverVersion = ($_.Split(","))[1].split(';')[0] -replace '([^;]*);.*',"`$1" } }
                $Content | ForEach-Object { if ($_ -like "*CatalogFile.NT*=*") { $DriverCatName = ($_.Split(","))[0].Split('=')[1] -replace '([^;]*);.*',"`$1" } }
                $Content | ForEach-Object { if ($_ -like "*CatalogFile*=*") { $DriverCatName = ($_.Split(","))[0].Split('=')[1] -replace '([^;]*);.*',"`$1"} }
                $infCatFullPath = (split-path ($driver) -parent) + "\" + $DriverCatName.trim()
                $infCatFullPath = $infCatFullPath.Replace("\\","\")
                $DriverFullName = (split-path $driver -Parent).Split('\')[-1]

                $DriverInfName = Split-Path $Driver -Leaf
                "Cat File Path: $infCatFullPath" | OutputStatusMessage
                if (Test-Path -Path $infCatFullPath) {
                    $catFile = Get-Item -Path $infCatFullPath
                    if ($catFile.GetType().Name -match "file") {
                        # Get Catalog details
                        $certInfo = GetCertificateWithInfo -CatalogFile $infCatFullPath
                        $installedSigning = Confirm-Cert -certInfo $certInfo -infName $DriverInfName -driverName $DriverInfName -infType "Extension"

                    } else {
                        "$infCatFullPath is not a file" | OutputStatusMessage
                        $installedSigning = "Catalog Not a file"
                    }
                } else {
                    "$infCatFullPath not found." | OutputStatusMessage
                    $installedSigning = "Not Found"
                }

                # Get Device Name for extension driver
                if ($OemInfs.Count -gt 0) {
                    $OemInfPathMatch = $OemInfs | Where-Object {$_.OemInfDriverInfo.OriginalFileName -contains $driver}
                    if ($OemInfPathMatch) {
                        "Oem inf match found for: $driver - Oem inf: $($OemInfPathMatch.Name)" | OutputStatusMessage
                        [array]$DeviceData = $Win32PnPEntity | Where-Object {$_.ExtendedConfigurationIdsData -like "*$($OemInfPathMatch.Name)*"}
                        if ($DeviceData) {
                            "Devices found using $($OemInfPathMatch.Name): `n$(($DeviceData.FriendlyName | Out-String).Trim())" | OutputStatusMessage
                            foreach ($Device in $DeviceData) {
                                if ($Device.FriendlyName) {
                                    $ExtDeviceName = $Device.FriendlyName
                                }
                                else {
                                    $ExtDeviceName = 'NoFriendlyName'
                                }

                                if ($xmlEnabled -eq "true") { 
                                    $Script:ResultsXmlWriter.WriteStartElement('ExtensionDriver')
                                    $Script:ResultsXmlWriter.WriteElementString('DeviceName', $ExtDeviceName)
                                    $Script:ResultsXmlWriter.WriteElementString('ExtensionFolder', $DriverFullName)
                                    $Script:ResultsXmlWriter.WriteElementString('ExtensionExpectedPath', $infUpdatedPath)
                                    $Script:ResultsXmlWriter.WriteElementString('DriverVersionExpected', $infDriverDate.trim() + ", " + $infDriverVersion.trim())
                                    $Script:ResultsXmlWriter.WriteElementString('DriverVersionInInfSystem', $DriverDate.trim() + ", " + $DriverVersion.trim())
                                    $Script:ResultsXmlWriter.WriteElementString('ExpectedSigning', $expectedSigning)
                                    $Script:ResultsXmlWriter.WriteElementString('InstalledSigning', $installedSigning)
                                    $Script:ResultsXmlWriter.WriteElementString('DriverMatchStatus', $xmlResult)
                                    $Script:ResultsXmlWriter.WriteEndElement()
                                }
                            }
                            continue
                        }
                        else {
                            "No device data found for oem inf: $($OemInfPathMatch.Name)" | OutputStatusMessage
                            $ExtDeviceName = "NotFound"
                        }
                    }
                    else {
                        "Oem inf match not found for: $driver" | OutputStatusMessage
                    }
                }
            } catch {
                "$expectedDescription threw an exception`n$($_.Exception.Message)`n$($_.ScriptStackTrace)" | OutputErrorMessage
            }
        }

        # Log to XML as requested
        if ($xmlEnabled -eq "true") { 
            $Script:ResultsXmlWriter.WriteStartElement('ExtensionDriver')
            $Script:ResultsXmlWriter.WriteElementString('DeviceName', $ExtDeviceName)
            $Script:ResultsXmlWriter.WriteElementString('ExtensionFolder', $DriverFullName)
            $Script:ResultsXmlWriter.WriteElementString('ExtensionExpectedPath', $infUpdatedPath)
            $Script:ResultsXmlWriter.WriteElementString('DriverVersionExpected', $infDriverDate.trim() + ", " + $infDriverVersion.trim())
            $Script:ResultsXmlWriter.WriteElementString('DriverVersionInInfSystem', $DriverDate.trim() + ", " + $DriverVersion.trim())
            $Script:ResultsXmlWriter.WriteElementString('ExpectedSigning', $expectedSigning)
            $Script:ResultsXmlWriter.WriteElementString('InstalledSigning', $installedSigning)
            $Script:ResultsXmlWriter.WriteElementString('DriverMatchStatus', $xmlResult)
            $Script:ResultsXmlWriter.WriteEndElement()
        }
    } # for each extension driver
    "-- VerifyExtensionDrivers End" | OutputStatusMessage
}

function VerifyNoGenericFirmwareInstalled {

    # Get all Fimware devices
    $installedDrivers = Get-WMIObject WIN32_PnPSignedDriver | Where-Object {($_.Deviceclass -eq "firmware")}

    "Verifing a Firmware capsule is installed, not generic driver." | OutputStatusMessage
    foreach ($device in $installedDrivers)
    {
        $deviceName = $device.DeviceName
        $deviceHardwareID = $device.HardwareID

        # SKIP EXCLUDED
        if (CheckForExlcude -deviceHWID $deviceHardwareID) { continue }

        # Verify device name is not 'Device Firmware'
        $testName = "'$deviceName' (HardwareID:'$deviceHardwareID') Should not have name: 'Device Firmware'. If this fails the Firmware Capsule is missing."
        if (IsWttLogger) {Start-WTTTest $testName}
        if ($deviceName -eq "Device Firmware" -or $deviceName -eq "System Firmware")
        {
            "  FAIL HardwareID:'$deviceHardwareID' Should not have generic INF name of 'Device Firmware' driver." | OutputStatusMessage
            if (IsWttLogger) {Stop-WTTTest -result "Fail" -name $testName}
        } else {
            "  PASS HardwareID:'$deviceHardwareID is not installed with 'Device Firmware' generic driver." | OutputStatusMessage
            if (IsWttLogger) {Stop-WTTTest -result "Pass" -name $testName}
        }

        # Verify INF is OEM*.inf
        "Verifing Firmware class devices are using OEM inf..." | OutputStatusMessage
        $deviceName = $($device.DeviceName)
        $deviceHardwareID = $device.HardwareID
        $inf = $($device.InfName)
        $testName = "'$deviceName' (HardwareID:'$deviceHardwareID') should not be using Windows Generic firmware INF. If this fails the Firmware Capsule is missing."
        if (IsWttLogger) {Start-WTTTest $testName}
        if ($inf -notlike "oem*.inf")
        {
            "  FAIL HardwareID:'$deviceHardwareID' expected to be using an OEM driver, not OS Generic firmware INF." | OutputStatusMessage
            if (IsWttLogger) {Stop-WTTTest -result "Fail" -name $testName}
            "Setting Exit to 1" | OutputStatusMessage
            #OemInfErrors
            #$Script:LocalExitCode = 1
            $Script:ExitResults.OemInfErrors++

            # Log failure to XML
            $Script:ResultsXmlWriter.WriteStartElement('Result')
            $Script:ResultsXmlWriter.WriteElementString('InfFilePath', "System Firmware - This device is missing a driver!")
            $Script:ResultsXmlWriter.WriteElementString('DeviceName', $deviceHardwareID)
            $Script:ResultsXmlWriter.WriteElementString('DriverType', "Firmware")
            $Script:ResultsXmlWriter.WriteEndElement()

        } else {
            "  PASS '$deviceName' using OEM INF driver." | OutputStatusMessage
            if (IsWttLogger) {Stop-WTTTest -result "Pass" -name $testName}

        }
    }


}

#****************************************************************************************
function GetCertificateWithInfo {
    param(
        [Parameter(Mandatory=$true, Position = 0)]
        $CatalogFile
    )
    $CatalogFile = $CatalogFile -replace '"', ''
    $SignerCertificate = $(Get-AuthenticodeSignature -FilePath $CatalogFile).SignerCertificate
    if ($SignerCertificate -ne $null){
        $Cert = $SignerCertificate.DnsNameList.Unicode
        $Issuer = $SignerCertificate.GetIssuerName()
        $EnhancedKeyUsageList = $SignerCertificate.EnhancedKeyUsageList.FriendlyName
    } else {
        $isNotSigned = $true
    }

    $isWHQLStyleCert = ($Cert -in @("Microsoft Windows Hardware Compatibility Publisher","Microsoft Windows Hardware Abstraction Layer Publisher"))
    $isPreProdCert   = $Issuer -eq "C=US, S=Washington, L=Redmond, O=Microsoft Corporation, CN=Microsoft Windows PCA 2010"
    $isAttestionSigned = (("Windows Hardware Driver Attested Verification" -in $EnhancedKeyUsageList) -or ($null -in $EnhancedKeyUsageList))

    $certInfo = [pscustomobject] @{
        PreProductionCert = $isPreProdCert
        WHQLStyleCert = $isWHQLStyleCert
        AttestationSigned = $isAttestionSigned
        NotSigned = $isNotSigned
        Cert = $Cert
        Issuer = $Issuer
    }

    return $certInfo
}


Function Confirm-Cert
{
    param (
        [Parameter(Mandatory=$true)]
        [PSCustomObject] $certInfo,
        [Parameter(Mandatory=$true)]
        [string] $infName,
        [Parameter(Mandatory=$false)]
        [string] $infType,
        [Parameter(Mandatory=$true)]
        [string] $driverName
    )

    #"Confirm-Cert params: infName: [$infName], driverName: [$driverName], infType: [$infType]" | OutputStatusMessage

    if ( ($certInfo.Cert -like "OEM*Leaf" -or $certInfo.AttestationSigned) -and $($infName) -like "OEM*UEFI*" -and $infType -ne "Extension"){
        "Found OEM UEFI, skipping cert check" | OutputStatusMessage
        $signed = "OEMUEFI"
    } elseif ($certInfo.AttestationSigned) {
        "$driverName is Attestation signed" | OutputStatusMessage
        $signed = "AtTestation"
    } elseif ($certInfo.WHQLStyleCert -and $certInfo.PreProductionCert) {
        "$driverName is PreProduction signed" | OutputStatusMessage
        $signed = "PreProduction"
    } elseif ($CertInfo.NotSigned){ 
        $signed = "NoCertSigner"
    } elseif (-not $certInfo.WHQLStyleCert) {
        "$driverName is Not WHQL signed" | OutputStatusMessage
        $signed = "Not-WHQL"
    } else {
        $signed = "WHQL"
    }
    #"Confirm-Cert return: [$signed]" | OutputStatusMessage
    return $signed
}


#****************************************************************************************
function PerformResultsXmlProcessing {

    if ($xmlEnabled -ne "true")
    { 
        "Skipping XML($xmlEnabled)" | OutputStatusMessage
        return
    }
    
    if ($Script:ResultsXmlWriter -ne $null) {return}

    $Script:ResultsXmlWriter = New-Object System.Xml.XmlTextWriter(".\results_drivers$xmlIteration.xml", $Null) -Verbose
    $Script:ResultsXmlWriter.Formatting = 'Indented'
    $Script:ResultsXmlWriter.Indentation = '4'
    $Script:ResultsXmlWriter.WriteStartDocument()
    $XsltPropertyText = 'type="text/xsl" href="results_driverVer12.xsl" '
    $Script:ResultsXmlWriter.WriteProcessingInstruction('xml-stylesheet', $XsltPropertyText)
    $Script:ResultsXmlWriter.WriteStartElement('Results')

    write-host "Created Results XML"

}

#****************************************************************************************
function AddDeviceInfoNodeXML {

    if ($xmlEnabled -ne "true") { 
        return
    }

    $imageName = 'Not Found'
    $systemSKU = 'Not Found'

    $registry_Key = $null
    if (test-path "HKLM:\SOFTWARE\Microsoft\Surface\OSImage") {
        $registry_Key= Get-ItemProperty -path "HKLM:\SOFTWARE\Microsoft\Surface\OSImage" -name "ImageVersion" -ErrorAction Continue
        if($registry_Key) {
            $OSimageName =  $registry_Key.ImageVersion
        }
    } else {
        if (test-path "C:\Windows\SysNative\Reg.exe"){
                $regOutput = C:\Windows\sysnative\reg.exe query "HKLM\SOFTWARE\Microsoft\Surface\OSImage" /v "ImageVersion"
            try { 
                $OSimageName = $regOutput.split(" ")[14]
            } catch {}
        }
    }

    $registry_Key = $null
    if (test-path "HKLM:\SOFTWARE\Microsoft\Surface\OSImage") {
        # $registry_Key= Get-ItemProperty -path "HKLM:\SOFTWARE\Microsoft\Surface\OSImage" -name "ImageProductName" -ErrorAction Continue
        # if($registry_Key) {
        #     $ImageProductName =  $registry_Key.ImageProductName
        # }
        $ImageProductName = Get-ImageProductName
    } else {
        if (test-path "C:\Windows\SysNative\Reg.exe"){
                $regOutput = C:\Windows\sysnative\reg.exe query "HKLM\SOFTWARE\Microsoft\Surface\OSImage" /v "ImageProductName"
            try { 
                $ImageProductName = $regOutput.split(" ")[14]
            } catch {}
        }
    }

    $registry_Key = $null
    if (test-path "HKLM:\SOFTWARE\Microsoft\Surface\OSImage") {
        $registry_Key= Get-ItemProperty -path "HKLM:\SOFTWARE\Microsoft\Surface\OSImage" -name "ImageName" -ErrorAction Continue
        if($registry_Key) {
            $ImageName =  $registry_Key.ImageName
        }
    } else {
        if (test-path "C:\Windows\SysNative\Reg.exe"){
                $regOutput = C:\Windows\sysnative\reg.exe query "HKLM\SOFTWARE\Microsoft\Surface\OSImage" /v "ImageName"
            try { 
                $ImageName = $regOutput.split(" ")[14]
            } catch {}
        }
    }
    
    $registry_Key = $null
    if (test-path "HKLM:\HARDWARE\DESCRIPTION\System\BIOS") {
        $registry_Key = Get-ItemProperty -path "HKLM:\HARDWARE\DESCRIPTION\System\BIOS" -name "SystemSKU" -ErrorAction Continue
        if($registry_Key) {
            $SystemSKU = $registry_Key.SystemSKU
        }
    } else {
        if (test-path "C:\Windows\SysNative\Reg.exe"){
                $regOutput = C:\Windows\sysnative\reg.exe query "HKLM\HARDWARE\DESCRIPTION\System\BIOS" /v "SystemSKU"
            try { 
                $SystemSKU = $regOutput.split(" ")[14]
            } catch {}
        }
    }

    # get OS info
    $os_version = (cmd /c ver).split(" ")[4].trim("][")
    $os_ID = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").ReleaseId
    
    # Get KB articles
    [string]$hotfix = systeminfo /fo csv | ConvertFrom-Csv | Select-Object hotfix*
    if ($hotfix) {$hotfix = ($hotfix.split(",",2).trim("}"))[1]}
    
    $CPU = $env:PROCESSOR_ARCHITECTURE
    $ComputerName = $env:COMPUTERNAME

    if (Get-Item -Path env:PROCESSOR_ARCHITEW6432 -ErrorAction SilentlyContinue) {
        $HKLMkey = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine, [Microsoft.Win32.RegistryView]::Registry64)
        $CurrentVersionKey =  $HKLMkey.OpenSubKey('SOFTWARE\Microsoft\Windows NT\CurrentVersion')
        # 22h2, 21h1, etc
        $DisplayVersion = $CurrentVersionKey.GetValue('DisplayVersion')
        if ($null -eq $DisplayVersion) {$DisplayVersion = "Unknown"}
        # if > 19043 then we need to add _W11 or _W10 to the string
        [int]$OSBuild = $CurrentVersionKey.GetValue('CurrentBuild')
        if ($null -eq $OSBuild) {$OSBuild = 0}
    }
    else {
    # 22h2, 21h1, etc
    $DisplayVersion = (Get-Item "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").GetValue('DisplayVersion')
    
    # if > 19043 then we need to add _W11 or _W10 to the string
    [int]$OSBuild = (Get-Item "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").GetValue('CurrentBuild')
}

    if (($OSBuild -gt 19043) -and ($OSBuild -lt 22000)){
        $DisplayOS = '_w10'
        $OSVerString = $DisplayVersion + $DisplayOS
    }
    elseif ($OSBuild -ge 22000 ){
        $DisplayOS = '_w11'
        $OSVerString = $DisplayVersion + $DisplayOS
    }
    else {
        $OSVerString = $DisplayVersion + "_$OSBuild"
    }

    $RailCarID = "Unknown"
    $RailCarName = "Unknown"
    $OSImageRegPath = 'HKLM:\SOFTWARE\Microsoft\Surface\OSImage'
    if (Get-Item -Path env:PROCESSOR_ARCHITEW6432 -ErrorAction SilentlyContinue) {
        $HKLMkey = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine, [Microsoft.Win32.RegistryView]::Registry64)
        $OSImageKey =  $HKLMkey.OpenSubKey('SOFTWARE\Microsoft\Surface\OSImage')
        [int]$RailCarID = $OSImageKey.GetValue('RailCarID')
        if ($null -eq $RailCarID) {$RailCarID = "Unknown"}
        $RailCarName = $OSImageKey.GetValue('RailCarName')
        if ($null -eq $RailCarName) {$RailCarName = "Unknown"}
    }
    elseif (Test-Path -Path $OSImageRegPath) {
        Write-Host "Getting RailCarID value from registry path: $OSImageRegPath"
        if (Get-ItemProperty -Path $OSImageRegPath -Name 'RailCarID' -ErrorAction SilentlyContinue) {
            $RailCarID = Get-ItemPropertyValue -Path $OSImageRegPath -Name 'RailCarID'
            Write-Host "RailCarID value is: $RailCarID" 
        }
        else {
            Write-Host -ForegroundColor Yellow "RailCarID not found in registry path: $OSImageRegPath"
        }

        Write-Host "Getting RailCarName value from registry path: $OSImageRegPath"
        if (Get-ItemProperty -Path $OSImageRegPath -Name 'RailCarName' -ErrorAction SilentlyContinue) {
            $RailCarName = Get-ItemPropertyValue -Path $OSImageRegPath -Name 'RailCarName'
            Write-Host "RailCarName value is: $RailCarName" 
        }
        else {
            Write-Host -ForegroundColor Yellow "RailCarName not found in registry path: $OSImageRegPath"
        }
    }
    else {
        Write-Host -ForegroundColor Yellow "Registry path not found: $OSImageRegPath"
    }

    $Script:ResultsXmlWriter.WriteStartElement('DeviceInfo')
    $Script:ResultsXmlWriter.WriteElementString('OSVerString',$OSVerString)
    $Script:ResultsXmlWriter.WriteElementString('OS', $os_id + "_$os_version")
    $Script:ResultsXmlWriter.WriteElementString('HotFixes', $hotfix)
    $Script:ResultsXmlWriter.WriteElementString('ComputerName', $ComputerName)
    $Script:ResultsXmlWriter.WriteElementString('BuildImage', $OSimagename)
    $Script:ResultsXmlWriter.WriteElementString('ImageProductName', $ImageProductName)
    $Script:ResultsXmlWriter.WriteElementString('ImageName', $ImageName)
    $Script:ResultsXmlWriter.WriteElementString('SystemSKU', $SystemSKU)
    $Script:ResultsXmlWriter.WriteElementString('CPU', $CPU)
    $Script:ResultsXmlWriter.WriteElementString('Iteration', $xmlIteration)
    $Script:ResultsXmlWriter.WriteElementString('RailCarID', $RailCarID)
    $Script:ResultsXmlWriter.WriteElementString('RailCarName', $RailCarName)
    $Script:ResultsXmlWriter.WriteEndElement()
    
    #XMLClose
    #GenHTML
}


function AddTimeStampNodeXML {
    if ($xmlEnabled -ne "true") { 
        return
    }

    $Script:ResultsXmlWriter.WriteStartElement('ReportGeneratedAt')
    $Script:ResultsXmlWriter.WriteElementString('TimeStamp',(Get-Date))
    $Script:ResultsXmlWriter.WriteEndElement()

    XMLClose
    GenHTML
}

Function GenHTML {
     # Transform results to HTML  
    [void] [System.Reflection.Assembly]::LoadWithPartialName("'System.IO.File")
    [void] [System.Reflection.Assembly]::LoadWithPartialName("'System.Xml.XmlReader")
    [void] [System.Reflection.Assembly]::LoadWithPartialName("'System.Xml.XmlTextWriter")
    $outputFileName = ".\results_drivers$xmlIteration.html"  
    if ($testFileSignatures -eq "true") {
        $transformFilePath = ".\results_driverVer13.xsl"  
    }
    else {
        $transformFilePath = ".\results_driverVer12.xsl"
    }
        
    if(-not (test-path $transformFilePath)) {
        Write-Host "You must run this report from the directory containing $transformFilePath"
    }
    else
    {
        if(test-path $outputFileName)
        {
            #if exists remove and replace with new
            Remove-Item -Path $outputFileName -Force
        }    
        $tempReportPath = ".\results_drivers$xmlIteration.xml"
        $XSLInputElement = New-Object System.Xml.Xsl.XslCompiledTransform;
        $XSLInputElement.Load($transformFilePath)
        $reader = [System.Xml.XmlReader]::Create($tempReportPath)
        $writer = [System.Xml.XmlTextWriter]::Create($outputFileName)

        try {
            $XSLInputElement.Transform($reader, $writer)
            write-host "Created Results HTML"
        }
        catch {    
            Write-Host 'Crash hit while attempting to transform the XML file'
        }

        try {
            $writer.Close()
        }
        catch {
            Write-Host 'Crash hit while attempting to close the writer'
        } 

        try {
            $reader.Close()
        }
        catch {
            Write-Host 'Crash hit while attempting to close the reader'
        } 
        XMLClose
    }
}

function XMLClose {
    if ($xmlEnabled -ne "true" -or $Script:ResultsXmlWriter -eq $null ) { return }

    $Script:ResultsXmlWriter.WriteEndElement()
    $Script:ResultsXmlWriter.WriteEndDocument()
    $Script:ResultsXmlWriter.Flush()
    $Script:ResultsXmlWriter.Close()

    $Script:ResultsXmlWriter = $null
    
}

function CheckForExlcude {
    Param(
        [string] $DeviceHWID
    )

    # Skip if excluded
    $exclude = $false
    foreach ($excludeDevice in $script:ExcludeList) 
    {        
        if ($DeviceHWID -like "*$excludeDevice*")
        {
            $exclude = $true
            "--------------- Excluding Device: $DeviceHWID" | OutputStatusMessage
            break
        }
    }

    return $exclude
}

function CreateExcludeList {

    # Show Exclude List param   
    "Excluded List Param: $exclude_HWID" | OutputStatusMessage
    $exclude_HWID=$exclude_HWID.Replace('*','&') 
    "Excluded List Param (updated): $exclude_HWID" | OutputStatusMessage

    # Update using paramater
    $exclude_HWID_List = $Exclude_HWID -split ';'
    foreach ($excluded_HWID in $exclude_HWID_List)
    {
        if ($excluded_HWID.Length -lt 3) {
            "PARAM String - HWID exclusion length less than 3, not valid: [$excluded_HWID]" | OutputStatusMessage
            continue
        }
        $script:excludeList.add($excluded_HWID)
        "PARAM String - Excluded Hardware ID: $excluded_HWID" | OutputStatusMessage
    }
   
    # Check for TOAST or PARAMATER XML containing excluded HWID's
    if ( ($Exclude_File -ne $null) -and (test-path($Exclude_File)) )
    {
        [xml]$xmlExclude = get-content $Exclude_File
        $xmlExcludes = $xmlExclude.DataStore.Whitelist.exclude.DeviceHWID
        foreach ($excluded_HWID in $xmlExcludes)
        {
            if ($excluded_HWID.Length -lt 3) {
                "PARAM Exclude File - HWID exclusion length less than 3, not valid: [$excluded_HWID]" | OutputStatusMessage
                continue
            }
            $script:excludeList.add($excluded_HWID)
            "PARAM Exclude File - Excluded Hardware ID: $excluded_HWID" | OutputStatusMessage
        }
    }
    
    # Check for LOCAL XML containing excluded HWID's
    $Exclude_File = ".\ExcludeList.xml"
    if ( ($Exclude_File -ne $null) -and (test-path($Exclude_File)) )
    {
        [xml]$xmlExclude = get-content $Exclude_File
        $xmlExcludes = $xmlExclude.DataStore.Whitelist.exclude.DeviceHWID
        foreach ($excluded_HWID in $xmlExcludes)
        {
            if ($excluded_HWID.Length -lt 3) {
                "DIR (local) Exclude File - HWID exclusion length less than 3, not valid: [$excluded_HWID]" | OutputStatusMessage
                continue
            }
            $script:excludeList.add($excluded_HWID)
            "DIR (local) Exclude File - Excluded Hardware ID: $excluded_HWID" | OutputStatusMessage
        }
    }
}


function Edit-String {
    param (
        [Parameter(Mandatory=$true)]
        [AllowEmptyString()]
        [string] $InputString
    )

    # Char reference
    # \xAE = Registered Trademark
    # \xA9 = Copyright
    # \x22 = Double Quote
    # \x27 = Single Quote
    $OutputString = $InputString -replace '[\xAE|\xA9|\x22|\x27]',''
    return $OutputString
}


function Get-ImageProductName {
    try {
        # Get ImageProductName (OEMXX) from the registy.  
        # Return ImageProductName or Null.
        $OSImageRegPath = 'HKLM:\SOFTWARE\Microsoft\Surface\OSImage'
        Write-Host "Getting ImageProductName value from registry path: $OSImageRegPath"
        if (Test-Path -Path $OSImageRegPath) {
            if (Get-ItemProperty -Path $OSImageRegPath -Name 'ImageProductName' -ErrorAction SilentlyContinue) {
                $ImageProductName = Get-ItemPropertyValue -Path $OSImageRegPath -Name 'ImageProductName'
                Write-Host "ImageProductName value is: $ImageProductName" 
                if ($ImageProductName -eq "") {
                    return $null
                }
                else {
                    $CpuName = (get-wmiobject win32_Processor).Name
                    $ImageProductName = Confirm-ImageProductName -ImageProductName $ImageProductName -CpuName $CpuName
                    Write-Host "ImageProductName is: $ImageProductName"
                    return $ImageProductName
                }
            }
            else {
                Write-Host -ForegroundColor Yellow "ImageProductName not found in registry path: $OSImageRegPath"
                return $null
            }
        }
        else {
            Write-Host -ForegroundColor Yellow "Registry path not found: $OSImageRegPath"
            return $null
        }
    }
    catch {
        Write-Host -ForegroundColor Red "Exception caught in Get-ImageProductName. [Exception: $($_.Exception.Message)] - [Line: $($_.InvocationInfo.ScriptLineNumber)] - [File: $($_.InvocationInfo.ScriptName)]"
        return $null
    }
}


function Confirm-ImageProductName {
    param (
        [Parameter(Mandatory = $true)]
        [string] $CpuName,
        [Parameter(Mandatory = $true)]
        [string] $ImageProductName
    )
    try {
        # Update ImageProductName by validating against CPU name string.  
        # Return input ImageProductName or updated ImageProductName based on CPU name string.
        Write-Host "Confirming ImageProductName"
        switch ($ImageProductName) {
            {$_ -in ('OEMHB','OEMSR')} {  
                if ($CpuName -like 'Microsoft*SQ1*') {
                    $ImageProductName = 'OEMHB'
                }
                elseif ($CpuName -like 'Microsoft*SQ2*') {
                    $ImageProductName = 'OEMSR'
                }
            }

            {$_ -in ('OEMLO','OEMVL')} {  
                if ($CpuName -like '*Intel*') {
                    $ImageProductName = 'OEMLO'
                }
                elseif ($CpuName -like 'Microsoft*SQ3*') {
                    $ImageProductName = 'OEMVL'
                }
            }

            {$_ -in ('OEMID')} {  
                if ($CpuName -like '*Intel*') {
                    $ImageProductName = 'OEMID'
                }
            }

            {$_ -in ('OEMCA','OEMCA_SP6')} {  
                if ($CpuName -like '*-8*') {
                    $ImageProductName = 'OEMCA_SP6'
                }
            }

            {$_ -in ('OEMLA','OEMLA_SL2')} {  
                if ($CpuName -like '*-8*') {
                    $ImageProductName = 'OEMLA_SL2'
                }
            }
        }
        return $ImageProductName
    }
    catch {
        Write-Host -ForegroundColor Red "Exception caught in Confirm-ImageProductName. [Exception: $($_.Exception.Message)] - [Line: $($_.InvocationInfo.ScriptLineNumber)] - [File: $($_.InvocationInfo.ScriptName)]"
        return $ImageProductName
    }
}


function Test-FileSignatures {
    param (
        [Parameter(Mandatory = $true)]
        [string]$SupportFilesPath,
        [Parameter(Mandatory = $true)]
        [int]$xmlIteration,
        [Parameter(Mandatory = $false)]
        [string]$driversFullPath
    )
    try {
        $SigErrors = 0
        $OutputCsvPath = ".\FileSigMetadata.csv"
        $OutputXmlPath = ".\results_drivers$xmlIteration.xml"
        if (Test-Path -Path $OutputXmlPath) {
            "Getting XML file data from: [$OutputXmlPath]" | OutputStatusMessage
            [xml]$XmlData = Get-Content -Path $OutputXmlPath
        }
        else {
            "XML file path not found: [$OutputXmlPath]" | OutputWarningMessage
            $XmlData = $null
        }

        [array]$SupportFilesExtenstions = @('.cat'<#,'.sys','.inf','.dll'#>)
        [array]$InvalidAlgorithmNamePatterns = @('SHA0','SHA-0','SHA1','SHA-1')

        if (Test-Path -Path $SupportFilesPath) {
            "Getting file data from: [$SupportFilesPath]" | OutputStatusMessage
            $Files = Get-ChildItem -Path $SupportFilesPath -Recurse -File -ErrorAction Stop | Where-Object { $_.Extension -in $SupportFilesExtenstions }
            if ($Files.Count -gt 0) {
                "Checking file signatures for [$($SupportFilesExtenstions -join ', ')] extensions" | OutputStatusMessage
                foreach ($File in $Files) {
                    $SigMatch = $null
                    $Sig = Get-AuthenticodeSignature -FilePath $File.FullName -ErrorAction Stop
                    if ($Sig.SignerCertificate.SignatureAlgorithm.FriendlyName -match ($InvalidAlgorithmNamePatterns -join '|')) {
                        [string]$SigMatch = $Matches.Values[0]
                        $SigMatch = $SigMatch.Replace('-','')
                        $File | Add-Member -NotePropertyName "SignerCertSigAlgoStatus" -NotePropertyValue "Fail $($SigMatch.ToUpper())" -ErrorAction Stop | Out-Null
                        $SigErrors++
                    }
                    elseif ($null -eq $Sig.SignerCertificate.SignatureAlgorithm.FriendlyName) {
                        $File | Add-Member -NotePropertyName "SignerCertSigAlgoStatus" -NotePropertyValue "Pass" -ErrorAction Stop | Out-Null
                    }
                    else {
                        $File | Add-Member -NotePropertyName "SignerCertSigAlgoStatus" -NotePropertyValue "Pass" -ErrorAction Stop | Out-Null
                    }

                    if ($XmlData) {
                        [array]$XmlDataMatches = @()

                        $XmlDataMatches += $XmlData.Results.Result | Where-Object {$_.InfFilePath -like "$($File.DirectoryName)\*"}
                        $XmlDataMatches += $XmlData.Results.NotFound | Where-Object {$_.NotInstalled -like "$($File.DirectoryName)\*"}
                        $XmlDataMatches += $XmlData.Results.ExtensionDriver | Where-Object {$_.ExtensionExpectedPath -like "$($File.DirectoryName)\*"}
                        if ($driversFullPath) {
                            $infUpdatedPath = $File.DirectoryName.Replace($SupportFilesPath,$driversFullPath)
                            $XmlDataMatches += $XmlData.Results.Result | Where-Object {$_.InfFilePath -like "$($infUpdatedPath)\*"}
                            $XmlDataMatches += $XmlData.Results.NotFound | Where-Object {$_.NotInstalled -like "$($infUpdatedPath)\*"}
                            $XmlDataMatches += $XmlData.Results.ExtensionDriver | Where-Object {$_.ExtensionExpectedPath -like "$($infUpdatedPath)\*"}
                        }


                        foreach ($XmlDataMatch in $XmlDataMatches) {
                            if ($XmlDataMatch.SigAlgo) {
                                if ($XmlDataMatch.SigAlgo -like "Fail*") {
                                    continue
                                }
                                elseif ($XmlDataMatch.SigAlgo -eq "Pass") {
                                    continue
                                }
                                else {
                                    $XmlDataMatch.SigAlgo = $File.SignerCertSigAlgoStatus
                                    continue
                                }
                            }
                            else {
                                $XmlSigAlgo = $XmlData.CreateElement("SigAlgo")
                                $XmlSigAlgo.InnerText = $File.SignerCertSigAlgoStatus
                                $XmlDataMatch.AppendChild($XmlSigAlgo) | Out-Null
                                continue
                            }
                        }
                    }
    
                    $File | Add-Member -NotePropertyName "SignatureType" -NotePropertyValue $Sig.SignatureType -ErrorAction Stop | Out-Null
                    if ($Sig.SignerCertificate.Handle) {
                        $File | Add-Member -NotePropertyName "SignerCertHandle" -NotePropertyValue "=`"$($Sig.SignerCertificate.Handle)`"" -ErrorAction Stop | Out-Null
                    }
                    else {
                        $File | Add-Member -NotePropertyName "SignerCertHandle" -NotePropertyValue "" -ErrorAction Stop | Out-Null
                    }
                
                    $File | Add-Member -NotePropertyName "SignerCertNotAfter" -NotePropertyValue $Sig.SignerCertificate.NotAfter -ErrorAction Stop | Out-Null
                    $File | Add-Member -NotePropertyName "SignerCertSigAlgoName" -NotePropertyValue $Sig.SignerCertificate.SignatureAlgorithm.FriendlyName -ErrorAction Stop | Out-Null
                    $File | Add-Member -NotePropertyName "SignerCertSigAlgoValue" -NotePropertyValue $Sig.SignerCertificate.SignatureAlgorithm.Value -ErrorAction Stop | Out-Null
                    $File | Add-Member -NotePropertyName "SignerCertThumbprint" -NotePropertyValue $Sig.SignerCertificate.Thumbprint -ErrorAction Stop | Out-Null
                    $File | Add-Member -NotePropertyName "SignerCertDnsNameList" -NotePropertyValue $Sig.SignerCertificate.DnsNameList.Punycode -ErrorAction Stop | Out-Null
                    if ($Sig.SignerCertificate.EnhancedKeyUsageList.FriendlyName) {
                        $File | Add-Member -NotePropertyName "SignerCertEnhKeyUsageListFriendlyName" -NotePropertyValue $Sig.SignerCertificate.EnhancedKeyUsageList.FriendlyName[0] -ErrorAction Stop | Out-Null
                    }
                    else {
                        $File | Add-Member -NotePropertyName "SignerCertEnhKeyUsageListFriendlyName" -NotePropertyValue "" -ErrorAction Stop | Out-Null
                    }
                    if ($Sig.SignerCertificate.EnhancedKeyUsageList.ObjectId) {
                        $File | Add-Member -NotePropertyName "SignerCertEnhKeyUsageListObjectId" -NotePropertyValue $Sig.SignerCertificate.EnhancedKeyUsageList.ObjectId[0] -ErrorAction Stop | Out-Null
                    }
                    else {
                        $File | Add-Member -NotePropertyName "SignerCertEnhKeyUsageListObjectId" -NotePropertyValue "" -ErrorAction Stop | Out-Null
                    }
                    continue
                }

                if ($XmlData) {
                    "Saving XML data: [$OutputXmlPath]" | OutputStatusMessage
                    $XmlData.Save($OutputXmlPath) | Out-Null
                }

                "Saving CSV data: [$OutputCsvPath]" | OutputStatusMessage
                $FileMetadataSubSet = $Files | Select-Object    SignerCertSigAlgoStatus, `
                                                                SignatureType, `
                                                                SignerCertSigAlgoName, `
                                                                Name, `
                                                                Extension, `
                                                                DirectoryName, `
                                                                SignerCertHandle, `
                                                                SignerCertNotAfter, `
                                                                SignerCertSigAlgoValue, `
                                                                SignerCertThumbprint, `
                                                                SignerCertDnsNameList
    
                $FileMetadataSubSet | Export-Csv -Path $OutputCsvPath -NoTypeInformation -ErrorAction Stop | Out-Null
    
                if ($SigErrors -ne 0) {
                    "Errors found in file signatures.  Error count: [$SigErrors] Check .csv for details: [$OutputCsvPath]" | OutputErrorMessage
                    return 1
                }
                else {
                    "All file signatures passed. Check .csv for details: [$OutputCsvPath]" | OutputStatusMessage
                    return 0
                }
            }
            else {
                "No files with these extensions [$($SupportFilesExtenstions -join ', ')] found in path: [$SupportFilesPath]" | OutputErrorMessage
                return 1
            }

        }
        else {
            "Support files path not found: [$SupportFilesPath]" | OutputErrorMessage
            return 1
        }
    }
    catch {
        "Exception caught in Test-FileSignatures. [Exception: $($_.Exception.Message)] - [Line: $($_.InvocationInfo.ScriptLineNumber)] - [File: $($_.InvocationInfo.ScriptName)]" | OutputErrorMessage
        return 1
    }
}

Function Convert-XmlResultsToJson {
    param (
        [Parameter(Mandatory = $false)]
        [string]$XmlResultsPath
    )
    try {
            "-- Convert-XmlResultsToJson Start" | OutputStatusMessage
            $XmlResultsPath = ".\results_drivers$xmlIteration.xml"
            $JsonResultsPath = ".\results_drivers$xmlIteration.json"
            if (Test-Path -Path $XmlResultsPath) {
                [xml]$XmlResultsData = Get-Content -Path $XmlResultsPath

                [array]$ResultsNames = ($XmlResultsData.results | Get-Member -MemberType Property).Name
                [PSCustomObject]$ResultsObj = @{}
                foreach ($ResultsName in $ResultsNames) {
                    [array]$ResultsData = $XmlResultsData.results.$ResultsName 
                    if ($ResultsData.Count -eq 0) {
                        "No data for $ResultsName" | OutputStatusMessage
                        continue
                    }
                    elseif ($ResultsData.Count -eq 1) {
                        "Adding $ResultsName - Count: $($ResultsData.Count)" | OutputStatusMessage
                        $ResultsObj | Add-Member -MemberType NoteProperty -Name $ResultsName -Value @{}
                        [array]$ResultsDataNames = ($ResultsData | Get-Member -MemberType Property).Name
                        foreach ($ResultsDataName in $ResultsDataNames) {
                            $ResultsObj.$ResultsName.Add($ResultsDataName, $ResultsData.$ResultsDataName)
                        }
                    }
                    else {
                        "Adding $ResultsName - Count: $($ResultsData.Count)" | OutputStatusMessage
                        $ResultsObj | Add-Member -MemberType NoteProperty -Name $ResultsName -Value @()
                        foreach ($ResultEntry in $ResultsData) {
                            $ResultEntryData = @{}
                            [array]$ResultsEntryNames = ($ResultEntry | Get-Member -MemberType Property).Name
                            foreach ($ResultsEntryName in $ResultsEntryNames) {
                                $ResultEntryData.Add($ResultsEntryName, $ResultEntry.$ResultsEntryName)
                            }
                            $ResultsObj.$ResultsName += $ResultEntryData
                        }
                    }
                }

                $ResultsObj | ConvertTo-Json | Out-File -FilePath $JsonResultsPath -Encoding ascii -Force | Out-Null
            }
            else {
                "XmlResults path not found: $XmlResultsPath" | OutputErrorMessage
            }
            "-- Convert-XmlResultsToJson End" | OutputStatusMessage
            return $null
    }
    catch {
        "Exception caught in Convert-XmlResultsToJson. [Exception: $($_.Exception.Message)] - [Line: $($_.InvocationInfo.ScriptLineNumber)] - [File: $($_.InvocationInfo.ScriptName)]" | OutputErrorMessage
        return $null
    }
}


#region main
############################
# MAIN
############################

$global:ErrorActionPreference = 'stop'
$IsWTTLogger = $false
# $Script:LocalExitCode = 0

# Tools

# WTT LOGGING
$WttLogFileName = "VerifyOemDriverVersions.wtl"
Invoke-Expression ". '$PSScriptRoot\PSWttLogger.ps1'" -ErrorAction Stop


# Initialize WTT Logging
try
{
    # Will throw exception if unable to load WTT Logging
    [void] (Start-WTTLog $WttLogFileName);
    'WTT Log started, beginning test!' | OutputStatusMessage
    $IsWTTLogger = $true

} catch {
    Write-Host "Failed to connect to WTT Logger.  Make sure WTTLog is available, or WTT Client is installed."
}

# Execute
try
{

    # Generate an exclude list from XML, and paramter
    CreateExcludeList

    # Creat Support Folder if needed
    if ((Test-Path -Path 'c:\Support') -and ((Get-ChildItem -Path 'c:\Support' -Filter *.inf -File -Recurse).Count -gt 10)) {
        "Support Folder exists" | OutputStatusMessage
    }else{
        & "$Script:ScriptPath\Create-SupportFolder.ps1"
        if ($LastExitCode -ne 0) {
            throw "There was a problem creating the support folder"
        }
    }

    # Log versions when $Drivers path invalid
    if ([string]::IsNullOrWhitespace($drivers)) { 
        $driverFolderExists = $false
        if ($IsWTTLogger) {Start-WTTTest "Record Versions"}
        PerformResultsXmlProcessing
        GetDriverVersions
        AddDeviceInfoNodeXML
        AddTimeStampNodeXML
        if ($IsWTTLogger) {Stop-WTTTest -result "Pass" -name "Record Versions"}
        exit $Script:LocalExitCode
    }

    # We have a valid Driver Folder (C:\Support)
    "Drivers Folder: $drivers" | OutputStatusMessage
  
    # Check for banged out devices
    if ($testDeviceStatus -eq "true") {
        PerformResultsXmlProcessing
        TestDeviceStatus
    }

    # Verify Firmware drivers are not generic (in-build)
    if ($testFirmwareInf -eq "true") {
        VerifyNoGenericFirmwareInstalled
    }

    # Verify all OEM Infs match inf in expected directory
    if ($testDeviceVersions -eq "true") {
        PerformResultsXmlProcessing
        VerifyVersions
        if ($testExtensionDrivers -eq "true") {
            VerifyExtensionDrivers
        }
        AddDeviceInfoNodeXML
        AddTimeStampNodeXML
    } elseif ($testExtensionDrivers -eq "true") {
        PerformResultsXmlProcessing
        VerifyExtensionDrivers
        AddDeviceInfoNodeXML
        AddTimeStampNodeXML
    }
    
    if ($testFileSignatures -eq "true") {
        if ($IsWTTLogger) {
            Start-WTTTest "Test-FileSignatures"
            $ret = Test-FileSignatures -SupportFilesPath $drivers -xmlIteration $xmlIteration -driversFullPath $driversFullPath
            "Test-FileSignatures return [$ret]" | OutputStatusMessage
            if ($ret -eq 0) {
                #"Test-FileSignatures passed" | OutputStatusMessage
                Stop-WTTTest -result "Pass" -name "Test-FileSignatures"
            }
            else {
                #"Test-FileSignatures failed" | OutputErrorMessage
                Stop-WTTTest -result "Fail" -name "Test-FileSignatures"
                #DriverSigningAlogrithmErrors
                #$Script:LocalExitCode = 1
                $Script:ExitResults.DriverSigningAlogrithmErrors++
            }
        }
        else {
            Test-FileSignatures -SupportFilesPath $drivers -xmlIteration $xmlIteration  -driversFullPath $driversFullPath | Out-Null
        }
        GenHTML
    }

} catch {

    if ( $IsWTTLogger -eq $false) {
        Write-Host "----- TRAP ----"
        Write-Host "Unhandled Exception: $_"
        $_ | Format-List -Force
        #pause

    } else {
        GetErrorInfo | OutputStatusMessage
        Start-WTTTest "Catch Exception"
        Stop-WTTTest -result "Fail" -name "Catch Exception"

    }
    $Script:LocalExitCode = 1


} finally {
    if ($Script:ResultsXmlWriter -ne $null){
        XMLClose
    }

    $outputFileName = ".\results_drivers$xmlIteration.html"
    if (!(Test-Path -Path $outputFileName)) {
        '<html><h1 style="font-size: 4em;">Verify OEM Drivers Report Generation Failed</h1></html>' | Out-File -FilePath $outputFileName -Encoding ascii
    }

    Convert-XmlResultsToJson | Out-Null
    #"Exit Results: `n$(($Script:ExitResults | Format-List | Out-String).Trim())" | OutputStatusMessage
    [array]$ExitArr = $Script:ExitResults | Get-Member | Where-Object {$_.MemberType -eq 'NoteProperty'} | Where-Object {$Script:ExitResults.($_.Name) -ne "Skipped"} | ForEach-Object {"[$($Script:ExitResults.($_.Name))] $($_.Name)"}
    [array]$SkippedArr = $Script:ExitResults | Get-Member | Where-Object {$_.MemberType -eq 'NoteProperty'} | Where-Object {$Script:ExitResults.($_.Name) -eq "Skipped"} | ForEach-Object {"[$($Script:ExitResults.($_.Name))] $($_.Name)"}
    "Exit Results: `n$(($ExitArr | Format-List | Out-String).Trim()) `n`nSkipped Tests: `n$(($SkippedArr | Format-List | Out-String).Trim())" | OutputStatusMessage
    if ($Script:LocalExitCode -eq 0) {
        $Script:ExitResults | Get-Member | Where-Object {$_.MemberType -eq 'NoteProperty'} | ForEach-Object {if ($Script:ExitResults.($_.Name) -is [int]){$Script:LocalExitCode += $Script:ExitResults.($_.Name)}}
    }
    "LocalExitCode [$Script:LocalExitCode]" | OutputStatusMessage


    if ($IsWTTLogger) {Stop-WTTLog}
    
    if (test-path "C:\Tools\PLE\TOAST\Messenger\ToastClientMessenger.exe") {
        c:\Tools\PLE\TOAST\Messenger\ToastClientMessenger.exe -s 1 -d "Marking machine READY."
    }
    Stop-Transcript | Out-Null
    exit $Script:LocalExitCode
    #endregion main
}



