#-------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation.  All rights reserved.
#-------------------------------------------------------------------------------
<#
OWNER: Dwight Carver (DCarv)

.SYNOPSIS
    This will find a TOAST install partiton, or create it
    Partition will be used to copy then install image across network
.PARAMETER -
    ----
#> 

$scriptPath = Split-Path -parent $MyInvocation.MyCommand.Definition
$CPU_Arch = $Env:Processor_Architecture
#$ToastVolExists = $FALSE
$OSIndex=$null
$OSPartition=$null
$ToastPartition=$null

function Invoke-DiskPartCommand {

    param(
        [Parameter(Mandatory=$true, Position=0)] [string]$DiskpartCommands, 
        [Parameter(Mandatory=$false)] [string]$InfoString,
        [Parameter(Mandatory=$false)] [boolean]$ContinueOnError=$false
    )

        $DiskpartCmdFile = $InfoString + '_Invoke-DiskPartCommand.cmd.txt'
        $DiskpartCmdFile = $DiskpartCmdFile
        $DiskpartCommands | Out-File -FilePath "$DiskpartCmdFile" -Encoding "ASCII"
        
        $DiskpartLogFile = $InfoString + '_Invoke-DiskPartCommand.log'
        $DiskpartLogFile = $DiskpartLogFile

        Write-host "diskpart.exe  $InfoString"     
        & "diskpart.exe" /s $DiskpartCmdFile $MyInvocation.UnboundArguments | Out-File -FilePath "$DiskpartLogFile" -Encoding "ASCII"
        if ($LASTEXITCODE -ne 0) {
            if (-not $ContinueOnError) {
                Write-Host -BackgroundColor Red "Last exit code: $LASTEXITCODE"
                if (Test-Path $DiskpartLogFile) {
                    Write-Host "Diskpart output (tail):"
                    Get-Content $DiskpartLogFile -Tail 40 | Write-Host
                }
                throw "Disk Partitioning Failed - error log at: $DiskpartLogFile"
            } else {
                Write-Host -ForegroundColor Yellow "Last exit code: $LASTEXITCODE"
                Write-Host -ForegroundColor Yellow "Disk Partitioning Failed - error log at: $DiskpartLogFile"
                return $LASTEXITCODE
            }
        }

}

function New-ToastPartitionWithStorageCmdlets {

    param(
        [Parameter(Mandatory=$true)] [int]$DiskNumber,
        [Parameter(Mandatory=$true)] [int]$OSPartitionNumber
    )

    # Keep TOAST between 30-32 GB. Request 32 GB, but honor supported shrink limits.
    $targetShrinkBytes = 32000MB
    $minShrinkBytes = 30001MB

    $osPart = Get-Partition -DiskNumber $DiskNumber -PartitionNumber $OSPartitionNumber
    $supported = Get-PartitionSupportedSize -DiskNumber $DiskNumber -PartitionNumber $OSPartitionNumber
    $currentSize = [int64]$osPart.Size
    $maxShrinkBytes = $currentSize - [int64]$supported.SizeMin

    if ($maxShrinkBytes -lt $minShrinkBytes) {
        throw "Unable to shrink OS partition by at least 30001MB. Max available shrink is $([math]::Round($maxShrinkBytes / 1MB, 2))MB."
    }

    $actualShrink = [math]::Min($targetShrinkBytes, $maxShrinkBytes)
    $newSize = $currentSize - $actualShrink
    Write-Host "Resizing C: partition by approximately $([math]::Round($actualShrink / 1MB, 2))MB"
    Resize-Partition -DiskNumber $DiskNumber -PartitionNumber $OSPartitionNumber -Size $newSize -ErrorAction Stop | Out-Null

    # Create and format the new partition for WiFi ODE content.
    $newPart = New-Partition -DiskNumber $DiskNumber -UseMaximumSize -DriveLetter U -ErrorAction Stop
    Format-Volume -DriveLetter U -FileSystem FAT32 -NewFileSystemLabel "TOAST" -Confirm:$false -Force -ErrorAction Stop | Out-Null
    return $newPart
}

Function EnumToastVol {

    # Need to get Disk info dynamically due to StorageSpaces
    $Disks = @(Get-VirtualDisk | Get-Disk)
    if ($Disks) {
        $DeviceDisk = New-Object PSObject -Property @{
            Index = $Disks[0].Number
            Model = $Disks[0].Model
        }
    } else {
        $Disks = @(Get-Disk | Where-Object BusType -ne "USB" | Where-Object Size -gt 20GB)
        if ($Disks) {
            $DeviceDisk = New-Object PSObject -Property @{
                Index = $Disks[0].Number
                Model = $Disks[0].Model
            }
        }
    }
    $OSIndex = $($DeviceDisk.Index)
    "OSIndex: $OSIndex"   

    $OSPartition = (Get-Partition -DriveLetter C).PartitionNumber
    "OSPartition: $OSPartition" 

    $ToastPartition = (get-partition | where-object -FilterScript {$_.Type -eq "Basic"} | where-object -FilterScript {$_.Size -lt 34000000000} | where-object -FilterScript {$_.Size -gt 30000000000}).PartitionNumber
    "ToastPartition: $ToastPartition" 

    # Check if TOAST volume exists and is SHIFU_SCOTT - Install failed.
    $ToastLetter = (get-volume -FriendlyName 'SHIFU_SCOTT' -erroraction ignore | Where-Object {$_.DriveType -eq "Fixed"}).DriveLetter
    if ($ToastLetter -ne $NULL) {
        "Found SHIFU_SCOTT Part.  Renaming"  
        $DriveLetter = $ToastLetter + ":"
        label $DriveLetter TOAST
    }
    # Check for failed Install
    $ToastLetter = (get-volume -FriendlyName 'BOOTME' -erroraction ignore | Where-Object {$_.DriveType -eq "Fixed"}).DriveLetter
    if ($ToastLetter -ne $NULL) {
        "Found BOOTME Partition,  Renaming"  
        $DriveLetter = $ToastLetter + ":"
        label $DriveLetter TOAST
    }
    # Check for TOAST
    $ToastLetter = (get-volume -FriendlyName 'TOAST' -erroraction ignore | Where-Object {$_.DriveType -eq "Fixed"}).DriveLetter
    if ($ToastLetter -ne $NULL) {
        if ($ToastLetter -eq "U") {
            "Toast Drive exists: $ToastLetter"  
            # Volume exists and has a drive letter, we are done.
            $global:LocalExitCode = 0
            return
        }

        # Exists and not U: so we need to Remove letter and reassign
        $ToastLetter = $ToastLetter + ":"
        "Toast Volume exists with drive letter and not U: ($ToastLetter)."  
        Remove-PartitionAccessPath -DiskNumber $OSIndex -PartitionNumber $ToastPartition -AccessPath $ToastLetter
        Get-Partition -disknumber $OSIndex -PartitionNumber $ToastPartition | Set-Partition -NewDriveLetter U -ErrorAction SilentlyContinue
        $ToastLetter = (get-volume -FriendlyName 'TOAST').DriveLetter
        "New Toast letter: $ToastLetter"  
        $global:LocalExitCode = 0
        return
    }

    get-volume
    # If TOAST exists -  assign letter
    if ((get-volume -FriendlyName 'TOAST' -erroraction ignore)) {
        "Toast Volume does exist, assiging letter."  
        # Assign letter
        Get-Partition -disknumber $OSIndex -PartitionNumber $ToastPartition | Set-Partition -NewDriveLetter U -ErrorAction SilentlyContinue
        $ToastLetter = (get-volume -FriendlyName 'TOAST').DriveLetter
        "New Toast letter: $ToastLetter"  
        $global:LocalExitCode = 0
        return
    }

    # need to Create the Partition and assing U:
    "Toast Partition not found, calling Create function."
    
    # Disable Bitlocker on Windows
    if (test-path "C:\Windows\SysNative\manage-bde.exe") {
        C:\Windows\SysNative\manage-bde.exe -off C:
    } else {
        manage-bde -off C:
    }
    $BitlockerStatus = $(Get-BitLockerVolume -mountpoint C:).EncryptionPercentage
    while ($BitlockerStatus -ne 0) {
        write-host  "Waiting for Bitlocker decryption... Encryption Percentage: $BitlockerStatus%"
        start-sleep 30
        $BitlockerStatus = $(Get-BitLockerVolume -mountpoint C:).EncryptionPercentage
    }

    $OSPartition = (Get-Partition -DriveLetter C).PartitionNumber
    "OSPartition: $OSPartition"

$DiskpartCommands = @"
select disk $OSIndex
sel par $OSPartition
shrink desired=32000 minimum=30001
create part pri
format fs=fat32 label="TOAST" quick
assign letter=U:
"@

    # SKip drives 64gig and smaller
    $SmallDiskSize = get-disk | where-object {$_.size -gt 64300200100 -and $_.PartitionStyle -ne "MBR"}

    if ($SmallDiskSize -ne $null) {
        try {
            Invoke-DiskpartCommand -DiskpartCommands $DiskpartCommands -continueOnError $false
        } catch {
            Write-Host -ForegroundColor Yellow "Diskpart failed, retrying with Storage cmdlets: $($_.Exception.Message)"
            New-ToastPartitionWithStorageCmdlets -DiskNumber $OSIndex -OSPartitionNumber $OSPartition | Out-Null
        }

        if (-not (Test-Path "U:\")) {
            New-PSDrive "U" -PSProvider FileSystem -Root "U:\" -Scope Global -ErrorAction SilentlyContinue | Out-Null
        }
    } else {
        $global:LocalExitCode = 1
        "Disk to small - Cannot create TOAST Partition" | OutputErrorMessage
        return 
    } 

    # Partiton craeted, and added as U:
    $ToastLetter = (get-volume -FriendlyName 'TOAST').DriveLetter
    "New Toast letter: $ToastLetter" 
    
    
    $global:LocalExitCode = 0

}


#region main
############################
# MAIN
############################
$global:ErrorActionPreference = 'stop'

# Call main worker functions, trap exceptions and log
try
{
    EnumToastVol

} catch {

    

        Write-Host "----- TRAP ----"
        Write-Host "Unhandled Exception: $_"
        $_ | Format-List -Force
        & mountvol O: /d | out-null
        & mountvol s: /d | out-null

    $Global:LocalExitCode = 1

}

# Main worker function complete, log results

    if ($global:LocalExitCode -eq 0)
    {
        Write-Host "SUCCESS!!"
    } else {
        Write-Host "FAILED!!"
    }


exit $Global:LocalExitCode

#endregion main
