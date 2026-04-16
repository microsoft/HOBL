
$Script:ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Script:ScriptName = Split-Path -Leaf $MyInvocation.MyCommand.Definition
$Script:LogFile = "$Script:ScriptPath\$($Script:ScriptName -replace '.ps1$','.log')"
if (!(Test-Path -Path $Script:LogFile)) {
    New-Item -Path $Script:LogFile -ItemType File -Force | Out-Null
}
$Script:SupportDriversPath = 'c:\Support'
$Script:ExpectedDriversRoot = 'c:\ExpectedDrivers'

# if (Test-Path -Path "$Script:ExpectedDriversRoot\results_drivers1.html") {
#     Copy-Item -Path "$Script:ExpectedDriversRoot\results_drivers1.html" -Destination "$Script:ScriptPath\results_drivers1.Original.html" | Out-Null
# }



# $Script:SupportDriversTempPath = 'c:\SupportDrivers'
# if (Test-Path -Path $Script:SupportDriversTempPath) {
#     Remove-Item -Path $Script:SupportDriversTempPath -Recurse -Force | Out-Null
# }

# if (!(Test-Path -Path $Script:SupportDriversTempPath)) {
#     New-Item -Path $Script:SupportDriversTempPath -ItemType Directory -Force | Out-Null
# }

$Script:InstallLogPath = 'c:\Logs\Install\log.txt' # drivers added to image log

$Script:SetupApiSetupLogPath = "$env:windir\inf\setupapi.setup.log"

# setupapi.offline.20240401_072605.log 
$Script:SetupApiOfflineLogPath = "$env:windir\inf\setupapi.offline.log"

# setupapi.dev.20250311_233050.log
$Script:SetupApiDevLogPath = "$env:windir\inf\setupapi.dev.log"

[array]$SetupLogPaths = @("c:\Logs\Install\log.txt","$env:windir\inf\setupapi.setup*.log","$env:windir\inf\setupapi.offline*.log","$env:windir\inf\setupapi.dev*.log")


Function Logit () {
    param ( 
        [Parameter(Position = 0, ValueFromPipeline = $true)] [object] $InputObject = "",
        [Parameter(Mandatory = $false)] [switch]$Warn,
        [Parameter(Mandatory = $false)] [switch]$Err,
        [Parameter(Mandatory = $false)] [switch]$Pass,
        [Parameter(Mandatory = $false)] [switch]$Fail,
        [Parameter(Mandatory = $false)] [switch]$Silent
    )

    if (!$Silent) {
        if (($Err) -or ($Fail)) {
            Write-Host $InputObject -ForegroundColor Red
        }
        elseif ($Warn) {
            Write-Host $InputObject -ForegroundColor Yellow
        }
        elseif ($Pass) {
            Write-Host $InputObject -ForegroundColor Green
        }
        else {
            Write-Host $InputObject
        }
    }

    if ($Err) {
        $InputObject = "ERROR: $InputObject"
    }
    elseif ($Fail) {
        $InputObject = "FAIL:  $InputObject"
    }
    elseif ($Warn) {
        $InputObject = "WARN:  $InputObject"
    }
    elseif ($Pass) {
        $InputObject = "PASS:  $InputObject"
    }
    else {
        $InputObject = "-----  $InputObject"
    }

    $currentDate = (Get-Date -UFormat "%d-%m-%Y")
    $currentTime = (Get-Date -UFormat "%T")
    $InputObject = $InputObject -join (" ")
    "[$currentDate $currentTime] $InputObject" | Out-File $Script:LogFile -Append
}

Function Get-InfVersionElements {
    param (
        [Parameter(Mandatory = $true)]
        [array]$InfData
    )
    try {
        # "Getting Version Elements" | Logit
        [array]$VersionElementNames = @('Signature', 'Class', 'ClassGuid', 'Provider', 'ExtensionId', 'DriverVer', 'PnpLockDown', 'CatalogFile', 'CatalogFile.nt', 'CatalogFile.ntx86', 'CatalogFile.ntia64', 'CatalogFile.ntamd64', 'CatalogFile.ntarm', 'CatalogFile.ntarm64')
        [PSCustomObject]$VersionElementsObj = @{}
        foreach ($ElementName in $VersionElementNames) {
            $VersionElementsObj | Add-Member -NotePropertyName $ElementName -NotePropertyValue ''
            foreach ($Line in $InfData) {
                $Line = $Line.Trim()
                #if ($Line.StartsWith($ElementName, 'CurrentCultureIgnoreCase')) {
                if ($Line -match "^$ElementName\s*=") {
                    [array]$LineSplit = $Line.Split('=')
                    $ElementValue = $LineSplit[1]
                    if ($ElementValue) {
                        $ElementValue = $ElementValue.Split(';')
                        $ElementValue = $ElementValue[0]
                        $ElementValue = $ElementValue.Trim()
                        $ElementValue = $ElementValue.Replace('"', '')
                        $ElementValue = $ElementValue.Replace("'", '')
                        # "$ElementName = $ElementValue" | Logit
                        $VersionElementsObj.$ElementName = $ElementValue
                    }
                }
            }
        }
    
        return $VersionElementsObj
    }
    catch {
        "!!! Exception caught in Get-InfVersionElements. [Exception: $($_.Exception.Message)] - [Line: $($_.InvocationInfo.ScriptLineNumber)] - [File: $($_.InvocationInfo.ScriptName)]" | Logit
        return $null
    }
}


function Main {
    try {

        if ((Test-Path -Path $Script:SupportDriversPath) -and (Test-Path -Path "$($Script:SupportDriversPath)_Previous\CopyComplete.txt")) {
            "Path found: $($Script:SupportDriversPath)_Previous\CopyComplete.txt" | Logit
            "Removing $Script:SupportDriversPath" | Logit
            Remove-Item -Path $Script:SupportDriversPath -Recurse -Force | Out-Null
        } 
        elseif (Test-Path -Path $Script:SupportDriversPath){
            if (Test-Path -Path "$($Script:SupportDriversPath)_Previous") {
                Remove-Item -Path "$($Script:SupportDriversPath)_Previous" -Recurse -Force | Out-Null
            }
            "Creating $($Script:SupportDriversPath)_Previous" | Logit
            New-Item -Path "$($Script:SupportDriversPath)_Previous" -ItemType Directory | Out-Null
            [array]$RobocopyArgs = @("`"$Script:SupportDriversPath`"","`"$($Script:SupportDriversPath)_Previous`"",'/E','/COPYALL','/NP',"/UNILOG+:$Script:LogFile")
            "RobocopyArgs: $($RobocopyArgs -join ' ' | Out-String)" | Logit
            Robocopy.exe $RobocopyArgs | Out-Null
            "Robocopy Exit Code: $LASTEXITCODE" | Logit
            if ($LASTEXITCODE -lt 8) {
                "Creating $($Script:SupportDriversPath)_Previous\CopyComplete.txt" | Logit
                New-Item -Path "$($Script:SupportDriversPath)_Previous\CopyComplete.txt" -ItemType File | Out-Null
                "Removing $Script:SupportDriversPath" | Logit
                Remove-Item -Path $Script:SupportDriversPath -Recurse -Force | Out-Null
            }
            else {
                throw "Robocopy copy error, exit code: $LASTEXITCODE"
            }
        }

        if (!(Test-Path -Path $Script:SupportDriversPath)) {
            "Creating $Script:SupportDriversPath" | Logit
            New-Item -Path $Script:SupportDriversPath -ItemType Directory -Force | Out-Null
        }

        # =================================================================================================
        # parse log.txt for the infs, these infs should be found in the setupapi.setup.log
        if (Test-Path -Path $Script:InstallLogPath) {
            Copy-Item -Path $Script:InstallLogPath -Destination $Script:ScriptPath -Force | Out-Null
            #     $LogTxtData = Get-Content -Path $Script:InstallLogPath

            #     # [0219-21:06:12] [NORMAL]  Searching for driver packages to install...
            #     # [0219-21:06:14] [NORMAL]  Found 125 driver package(s) to install.
            #     # [0219-21:06:14] [NORMAL]  Installing 1 of 125 - C:\Support\graphicsbase\content\amd64\release\drv\CtaChildDriver\CtaChildDriver.inf: The driver package was successfully installed.
            #     # [0219-21:06:15] [NORMAL]  Installing 2 of 125 - C:\Support\graphicsbase\content\amd64\release\drv\cui_dch.inf: The driver package was successfully installed.
            #     # [0219-21:06:15] [NORMAL]  Installing 3 of 125 - C:\Support\graphicsbase\content\amd64\release\drv\GSCAuxDriver.inf: The driver package was successfully installed.
            #     # [0219-21:06:15] [NORMAL]  Installing 4 of 125 - C:\Support\graphicsbase\content\amd64\release\drv\gscheci.inf: The driver package was successfully installed.
            #     # [0219-21:06:15] [NORMAL]  Installing 5 of 125 - C:\Support\graphicsbase\content\amd64\release\drv\I2CDriver\Intel_NF_I2C_Child.inf: The driver package was successfully installed.
            #     # [0219-21:06:15] [NORMAL]  Installing 6 of 125 - C:\Support\graphicsbase\content\amd64\release\drv\memcntrl.inf: The driver package was successfully installed.
            #     # [0219-21:06:15] [NORMAL]  Installing 7 of 125 - C:\Support\graphicsbase\content\amd64\release\drv\MiniCtaDriver\MiniCtaDriver.inf: The driver package was successfully installed.
            #     # [0219-21:06:15] [NORMAL]  Installing 8 of 125 - C:\Support\surfacethunderbolt4dockfwupdate\SurfaceThunderbolt4DockFwUpdate.inf: The driver package was successfully installed.
            #     # [0219-21:06:15] [NORMAL]  Installing 9 of 125 - oem1.inf: The driver package was successfully installed.
            #     # [0219-21:06:15] [NORMAL]  Installing 10 of 125 - oem10.inf: The driver package was successfully installed.

            #     # [0219-21:06:18] [NORMAL]  Installing 124 of 125 - oem98.inf: The driver package was successfully installed.
            #     # [0219-21:06:18] [NORMAL]  Installing 125 of 125 - oem99.inf: The driver package was successfully installed.
            #     # [0219-21:06:18] [NORMAL]  The operation completed successfully.

            #     $i = 0
            #     foreach ($Line in $LogTxtData) {
            #         $Line = $Line.Trim()
            #         if ($Line -match ".*Found (\d+) driver package\(s\) to install") {
            #             [int]$DriverCount = $matches[1]

            #         }
            #         $i++
            #     }
        }

        # =================================================================================================
        # drivers added to image are in c:\windows\inf\setupapi.setup.log
        # parse setupapi.setup.log for the infs
        # Sample entry from setupapi.setup.log
        # >>>  [Setup Update Driver Package Signatures]
        # >>>  Section start 2025/01/23 07:30:25.095
        #      set: oem76.inf/acpiaudiocompositor.inf -> Signed by 'Microsoft Windows Hardware Compatibility Publisher' (SignerScore = 0x0D000005).
        #      set: oem12.inf/dax3_ext_rtk.inf -> Signed by 'Microsoft Windows Hardware Compatibility Publisher' (SignerScore = 0x0D000005).
        # <<<  Section end 2025/01/23 07:30:25.238
        # <<<  [Exit status: SUCCESS]
        [array]$SetupApiSetupInfNames = @()
        if (Test-Path -Path $Script:SetupApiSetupLogPath ) {
            Copy-Item -Path $Script:SetupApiSetupLogPath -Destination $Script:ScriptPath -Force | Out-Null
            "" | Logit
            "Getting .infs from: $Script:SetupApiSetupLogPath" | Logit
            [array]$SetupApiSetupLogData = Get-Content -Path $Script:SetupApiSetupLogPath 
            $i = 0
            while ($i -lt $SetupApiSetupLogData.Count) {
                # Driver Section Begin
                if ($SetupApiSetupLogData[$i].Trim() -match ">>>  \[Setup Update Driver Package Signatures\]") {
                    $SetupApiSetupLogData[$i] | Logit
                    [bool]$SectionExit = $false
                    $i++
                    while (($i -lt $SetupApiSetupLogData.Count) -and ($SectionExit -eq $false)) {
                        # Driver Section Start Timestamp
                        if ($SetupApiSetupLogData[$i].Trim() -match ">>>  Section start\.*") {
                            $SetupApiSetupLogData[$i] | Logit
                        }

                        # Driver Inf Entry
                        if ($SetupApiSetupLogData[$i].Trim() -match "\s*set: (oem\d+\.inf)\/(.*\.inf)") {
                            $SetupApiSetupLogData[$i] | Logit
                            $SetupApiSetupInfNames += [PSCustomObject]@{
                                OemInfName = $matches[1]
                                OrgInfName = $matches[2]
                                v2Folder = $null
                            }
                        }

                        # Driver Section End Timestamp
                        if ($SetupApiSetupLogData[$i].Trim() -match "<<<  Section end\.*") {
                            $SetupApiSetupLogData[$i] | Logit
                        }

                        # Driver Section Exit
                        if ($SetupApiSetupLogData[$i].Trim() -match "<<<  \[Exit status\.*") {
                            $SetupApiSetupLogData[$i] | Logit
                            $SectionExit = $true
                            $i = $SetupApiSetupLogData.Count
                        }
                        $i++
                    }
                }
                $i++
            }        
        }
        else {
            throw "Path not found: $Script:SetupApiSetupLogPath"
        }

        # =================================================================================================
        # drivers imported into image are first boot are in setupapi.offline.log
        # parse setupapi.offline.log for the infs
        # Sample entries from setupapi.offline.log
        # first boot drivers imported c:\windows\inf\setupapi.offline.log
        # >>>  [Import Driver Package - C:\Support\graphicsbase\content\amd64\release\drv\MiniCtaDriver\MiniCtaDriver.inf]
        # >>>  Section start 2025/02/19 21:06:15.218
        #      idb:      Created driver INF file object 'oem125.inf' in DRIVERS database node.
        #      cpy:      Published 'minictadriver.inf_amd64_42289b710b97c4d3\minictadriver.inf' to 'oem125.inf'.
        # <<<  Section end 2025/02/19 21:06:15.250
        # <<<  [Exit status: SUCCESS]

        # >>>  [Import Driver Package - D:\Updates\Drivers_OS\_Win11_Only\Surface Realtek USB Ethernet Chips\x64\RTL8156\msu56cx22x64sta.INF]
        # >>>  Section start 2025/02/19 21:06:35.312
        #      idb:      Created driver INF file object 'oem138.inf' in DRIVERS database node.
        #      cpy:      Published 'msu56cx22x64sta.inf_amd64_20bd0ca719d408d9\msu56cx22x64sta.inf' to 'oem138.inf'.
        # <<<  Section end 2025/02/19 21:06:35.375
        # <<<  [Exit status: SUCCESS
        [array]$SetupApiOfflineInfNames = @()
        if (Test-Path -Path $Script:SetupApiOfflineLogPath) {
            Copy-Item -Path $Script:SetupApiOfflineLogPath -Destination $Script:ScriptPath -Force | Out-Null
            "" | Logit
            "Getting .infs from: $Script:SetupApiOfflineLogPath" | Logit
            [array]$SetupApiOfflineLogData = Get-Content -Path $Script:SetupApiOfflineLogPath

            $i = 0
            while ($i -lt $SetupApiOfflineLogData.Count) {
                # Driver Section Begin
                if ($SetupApiOfflineLogData[$i].Trim() -match ">>>  \[Import Driver Package - \w:\\Support|\w:\\Updates|\w:\\bin\\postdeploy\\dev\\drivers|\w:\\PostOs\\Drivers_OS") {
                    $SetupApiOfflineLogData[$i] | Logit
                    $v2Folder = $null
                    if ($SetupApiOfflineLogData[$i] -match ".*\\(v2_w1\d)\\.*") {
                        $v2Folder = $matches[1]
                    }
                    
                    [bool]$SectionExit = $false
                    $i++
                    while (($i -lt $SetupApiOfflineLogData.Count) -and ($SectionExit -eq $false)) {
                        # Driver Section Start Timestamp
                        if ($SetupApiOfflineLogData[$i].Trim() -match ">>>  Section start\.*") {
                            $SetupApiOfflineLogData[$i] | Logit
                        }

                        # Driver Inf Entry
                        if ($SetupApiOfflineLogData[$i].Trim() -match "\s*cpy:\s*Published.*\\(.*\.inf)' to '(oem\d+\.inf)'\.") {
                            $SetupApiOfflineLogData[$i] | Logit
                            $SetupApiOfflineInfNames += [PSCustomObject]@{
                                OrgInfName = $matches[1]
                                OemInfName = $matches[2]
                                v2Folder = $v2Folder
                            }
                        }

                        # Driver Section End Timestamp
                        if ($SetupApiOfflineLogData[$i].Trim() -match "<<<  Section end\.*") {
                            $SetupApiOfflineLogData[$i] | Logit
                        }

                        # Driver Section Exit
                        if ($SetupApiOfflineLogData[$i].Trim() -match "<<<  \[Exit status\.*") {
                            $SetupApiOfflineLogData[$i] | Logit
                            $SectionExit = $true
                            # $i = $SetupApiOfflineLogData.Count
                        }
                        $i++
                    }
                }
                $i++
            }   
        }
        else {
            throw "Path not found: $Script:SetupApiOfflineLogPath"
        }

        "`n`n" | Logit
        [array]$SetupApiInfNames = @()
        if ($SetupApiSetupInfNames.Count -gt 0) {
            $SetupApiSetupInfNames = $SetupApiSetupInfNames | Sort-Object -Property OemInfName
            "Inf data from setupapi.setup.log: `n$($SetupApiSetupInfNames | Sort-Object -Property OemInfName | Select-Object OemInfName,OrgInfName | Out-String)" | Logit
            $SetupApiInfNames += $SetupApiSetupInfNames
        }
        else {
            "Inf data from setupapi.setup.log: None" | Logit -Warn
        }

        
        if ($SetupApiOfflineInfNames.Count -gt 0) {
            $SetupApiOfflineInfNames = $SetupApiOfflineInfNames | Sort-Object -Property OemInfName
            "Inf data from setupapi.offline.log: `n$($SetupApiOfflineInfNames | Sort-Object -Property OemInfName | Select-Object OemInfName,OrgInfName | Out-String)" | Logit
            
            foreach ($SetupApiOfflineInfName in $SetupApiOfflineInfNames) {
                if ($SetupApiOfflineInfName.v2Folder) {
                    # "Updating $SetupApiOfflineInfName" | Logit
                    # $SetupApiInfNames = $SetupApiInfNames | Where-Object {$_.OemInfName -ne $SetupApiOfflineInfName.OemInfName}
                    $SetupApiInfNames | Where-Object {($_.OemInfName -eq $SetupApiOfflineInfName.OemInfName) -and ($_.OrgInfName -eq $SetupApiOfflineInfName.OrgInfName)} | ForEach-Object {$_.v2Folder = $SetupApiOfflineInfName.v2Folder}
                }
            }
            $SetupApiInfNames += $SetupApiOfflineInfNames
        }
        else {
            "Inf data from setupapi.offline.log: None" | Logit -Warn
        }

        if (Test-Path -Path $Script:SetupApiDevLogPath) {
            Copy-Item -Path $Script:SetupApiDevLogPath -Destination $Script:ScriptPath -Force | Out-Null
        }



        $SetupApiInfNames | ConvertTo-Json -Depth 5 | Out-File "$Script:ScriptPath\SetupApiInfNames.json"
        # =================================================================================================
        # Compare the logs inf data to driverstore inf data
        $WindowsDrivers = Get-WindowsDriver -Online
        foreach ($WindowsDriver in $WindowsDrivers) {
            $WindowsDriver.Driver -match "oem(?<OemNum>.*).inf" | Out-Null
            [int]$OemNum = $matches['OemNum']
            $WindowsDriver | Add-Member -NotePropertyName 'OemNum' -NotePropertyValue $OemNum
        }
        "`n`n" | Logit
        "Driver Store infs: `n$($WindowsDrivers | Sort-Object -Property OemNum | Select-Object Driver,ClassName,CatalogFile,OriginalFileName | Format-Table -AutoSize | Out-String -Width 300)" | Logit
        # $SetupApiInfNames = $SetupApiInfNames | Sort-Object -Property OemInfName,OrgInfName,v2Folder 
        # $SetupApiInfNames = $SetupApiInfNames | Group-Object -Property OemInfName,OrgInfName,v2Folder | ForEach-Object { $_.Group[0] }
        $SetupApiInfNames = $SetupApiInfNames | Sort-Object -Property v2Folder -Descending | Group-Object -Property OemInfName,OrgInfName | ForEach-Object { $_.Group[0] }
        
        
        [array]$NotFoundInDriverStore = @()
        foreach ($Inf in $SetupApiInfNames) {
            "----------------------" | Logit
            if ($Inf.OemInfName -in $WindowsDrivers.Driver) {
                # "$($Inf.OemInfName) found in Driver Store" | Logit
                $WindowsDriver = $WindowsDrivers | Where-Object {$_.Driver -eq $Inf.OemInfName}
                if ($WindowsDriver.OriginalFileName -match "\\$($Inf.OrgInfName)$") {
                    "$($Inf.OemInfName) - $($Inf.OrgInfName) found in Driver Store" | Logit
                    $WindowsDrivers = $WindowsDrivers | Where-Object {$_.Driver -ne $Inf.OemInfName}

                    $WindowsDriver.Driver -match "oem(?<OemNum>.*).inf" | Out-Null
                    [int]$OemNum = $matches['OemNum']
                    [string]$OemNumNNN =  '{0:d3}' -f $OemNum
                    $OriginalFileName = Split-Path $WindowsDriver.OriginalFileName -Leaf
                    $WindowsDriverPath = Split-Path $WindowsDriver.OriginalFileName -Parent
                    
                    "Copying: $WindowsDriverPath" | Logit
                    if ($Inf.v2Folder) {
                        $SupportDriverPath = "$Script:SupportDriversPath\$($Inf.v2Folder)\$($OemNumNNN)_$($OriginalFileName -replace '.inf$','')"
                    }
                    else {
                        $SupportDriverPath = "$Script:SupportDriversPath\$($OemNumNNN)_$($OriginalFileName -replace '.inf$','')"
                    }
                    
                    New-Item -Path $SupportDriverPath -ItemType Directory | Out-Null
                    
                    if ($WindowsDriver.ClassName -eq 'Firmware') {
                        "ClassName = Firmware" | Logit
                        Copy-Item -Path $WindowsDriverPath\* -Destination $SupportDriverPath  | Out-Null
                    }
                    else {
                        Copy-Item -Path $WindowsDriverPath\* -Destination $SupportDriverPath -Include '*.inf','*.cat' | Out-Null
                    }
                    
                }
                else {
                    "$($Inf.OemInfName) found in Driver Store" | Logit -Warn
                    "Original inf file name does not match: SetupApi $($Inf.OrgInfName) - DriverStore $(Split-Path $WindowsDriver.OriginalFileName -Leaf)" | Logit -Warn
                    $NotFoundInDriverStore += "$($Inf.OemInfName) - $($Inf.OrgInfName)"
                }
            } 
            else {
                "$($Inf.OemInfName) - $($Inf.OrgInfName) not found in Driver Store" | Logit -Warn
                $NotFoundInDriverStore += "$($Inf.OemInfName) - $($Inf.OrgInfName)"
            }
        }

        if (Test-Path -Path $Script:SupportDriversPath) {
            [array]$SupportFolderInfs = Get-ChildItem -Path $Script:SupportDriversPath -Filter *.inf -Recurse

            foreach ($SupportFolderInf in $SupportFolderInfs) {
                [array]$InfData = Get-Content -Path $SupportFolderInf.FullName
                $InfVersionElementsObj = Get-InfVersionElements -InfData $InfData
                if ($InfVersionElementsObj) {
                    $SupportFolderInf | Add-Member -NotePropertyName 'DriverVer' -NotePropertyValue $InfVersionElementsObj.DriverVer | Out-Null
                    $SupportFolderInf | Add-Member -NotePropertyName 'Class' -NotePropertyValue $InfVersionElementsObj.Class | Out-Null
                }
                else {
                    "Error occurred getting Inf Version Elements for inf: $($SupportFolderInf.FullName)" | Logit -Err
                }
            }

            "Support folder infs: $Script:SupportDriversPath `n$($SupportFolderInfs | Select-Object DriverVer,Class,FullName | Format-Table -AutoSize | Out-String -Width 300)" | Logit
        }

        if ($NotFoundInDriverStore.Count -gt 0) {
            "Infs not found in the Driver Store: `n$($NotFoundInDriverStore | Sort-Object | Format-List | Out-String)" | Logit -Warn
        }

        "`n`n" | Logit
        "Driver Store infs not found in the original image logs: `n$($WindowsDrivers | Sort-Object -Property Driver | Select-Object Driver,ClassName,CatalogFile,OriginalFileName | Format-Table -AutoSize | Out-String -Width 300)" | Logit -Warn
        return 0
    }
    catch {
        "!!! Exception caught in Main. [Exception: $($_.Exception.Message)] - [Line: $($_.InvocationInfo.ScriptLineNumber)] - [File: $($_.InvocationInfo.ScriptName)]" | Logit -Err
        return 1
    }
    finally {
        if ((Test-Path -Path $Script:SupportDriversPath) -and (Test-Path -Path $Script:LogFile)) {
            Copy-Item -Path $Script:LogFile -Destination $Script:SupportDriversPath | Out-Null        
        }
    }
}


"****************** Begin Script: $Script:ScriptName" | Logit
$ret = Main
"Exit Code: [$ret]" | Logit
"****************** End Script: $Script:ScriptName `n`n" | Logit
if ($ret -eq 0) {
    # if ((Test-Path -Path $Script:SupportDriversTempPath) -and (Test-Path -Path $Script:SupportDriversPath)) {
    #     $SupportDrivers = Get-ChildItem -Path $Script:SupportDriversPath -Recurse -Filter *.inf
    #     $SupportDriversGen = Get-ChildItem -Path $Script:SupportDriversTempPath -Recurse -Filter *.inf

    #     $SupportDrivers.Name.ToLower() | Sort-Object | Out-File -FilePath "$Script:ScriptPath\SupportDriversOriginal.log" | Out-Null
    #     $SupportDriversGen.Name.ToLower() | Sort-Object | Out-File -FilePath "$Script:ScriptPath\SupportDriversGenerated.log" | Out-Null

    # }
    #   
    #   $Script:ExpectedDriversRoot
}

exit $ret
