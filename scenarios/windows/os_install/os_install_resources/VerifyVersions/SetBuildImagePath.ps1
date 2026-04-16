
## Look for full Image path on PLEWUSRV1 server

Param(

    [string] $ManualPath

)

$scriptPath = Split-Path -parent $MyInvocation.MyCommand.Definition
$global:LocalExitCode = 0
$script:fullImagePath = ""

$SystemSKUs =@{}
# Surface BOOK
$SystemSKUs.add("Surface_Book", "OEMCH")
$SystemSKUs.add("SurfaceBook", "OEMCH")
$SystemSKUs.add("OEMCH", "OEMCH")
$SystemSKUs.add("SurfaceLaptop", "OEMLA")
$SystemSKUs.add("Surface_Laptop", "OEMLA")
$SystemSKUs.add("OEMLA", "OEMLA")
# Surface PRO
$SystemSKUs.add("SurfacePro", "OEMCA")
$SystemSKUs.add("Surface_Pro", "OEMCA")
$SystemSKUs.add("Surface_Pro_1796", "OEMCA")
$systemSKUs.add("OEMCA", "OEMCA")
$SystemSKUs.add("Surface_Pro_4", "OEMAP")
$SystemSKUs.add("SurfacePro4", "OEMAP")
$SystemSKUs.add("OEMAP", "OEMAP")
$SystemSKUs.add("Surface_Pro_3", "OEMC")
$SystemSKUs.add("SurfacePro3", "OEMC")
$SystemSKUs.add("OEMC", "OEMC")
$SystemSKUs.add("Surface_Pro_1807", "OEMCA")   # LTE
# Surface
$SystemSKUs.add("Surface_3_US1", "OEMB")
$SystemSKUs.add("Surface_3_US2", "OEMB")
$SystemSKUs.add("Surface_3_NAG", "OEMB")
$SystemSKUs.add("Surface_3_ROW", "OEMB")
$SystemSKUs.add("Surface_3_WIFI", "OEMB")
$SystemSKUs.Add("Surface_3", "OEMB")
$SystemSKUs.Add("Surface3", "OEMB")
$SystemSKUs.Add("OEMB", "OEMB")
# Cardinal / Studio
$SystemSKUs.add("Cardinal", "OEMNH")
$SystemSKUs.add("Surface_Studio", "OEMNH")
$SystemSKUs.add("SurfaceStudio", "OEMNH")
$SystemSKUs.add("OEMNH", "OEMNH")
$SystemSKUs.add("OEMCR", "OEMCR")
# Other
$SystemSKUs.add("OEMSH", "OEMSH")
$SystemSKUs.add("Surface_Book_1832", "OEMSH")
$SystemSKUs.add("Surface_Book_1793", "OEMSH")

function GetImagePath {

    # EXAMPLE: \\plewusrv1\BUILDS\RELEASE\OEMSH\imaging_rel1\dev_rs3\5.290.0

    $rootpath = "\\plewusrv1\Builds\Release\"
    $registry_Key = $null

    # Check for existing Image Path:
    $registry_Key= Get-ItemProperty -path "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -name "Image" -ErrorAction Continue
    if($registry_Key)
    {    
        if ($registry_Key.Image.IndexOf("\\") -eq 0)
        {
            $rootpath = $registry_Key.Image
            #$script:fullImagePath = $rootpath.Substring(0, ($rootpath.length-6))
            $script:fullImagePath = $rootpath
            "Found full image path to a server in the Image registry key, using this path" | OutputStatusMessage
            return
        }
    }

    # Get the info from Surface Registry
    $registry_Key= Get-ItemProperty -path "HKLM:\SOFTWARE\Microsoft\Surface\OSImage" -name "ImageProductName" -ErrorAction Continue
    if($registry_Key)
    {

        $SystemSKU = $registry_Key.ImageProductName
        "ImageProductName: $SystemSKU" | OutputStatusMessage

        # Map Friendy SKU name to Folder (OEM*) share name
        if ($SystemSKUs.ContainsKey($systemSKU))
        {
            $SystemSKU=$SystemSKUs.$systemSKU
            "Found SKU match in table lookup: $SystemSKU" | OutputStatusMessage

        # More SKU updates for Wildcard matches (Dev units). Due to wildcard, longer SKU's are on top and not using Hash table.
        } elseif ($SystemSKU -like "OEMCH*") {
            $SystemSku = "OEMCH"

        } elseif ($SystemSKU -like "OEMAP*") {
            $SystemSku = "OEMAP"

        } elseif ($SystemSKU -like "OEMNH*") {
            $SystemSku = "OEMNH"

        } elseif ($SystemSKU -like "OEMCA*") {
            $SystemSku = "OEMCA"

        } elseif ($SystemSKU -like "OEMLA*") {
            $SystemSku = "OEMLA"

        } elseif ($SystemSKU -like "OEMSH*") {
            $SystemSku = "OEMSH"

        } elseif ($SystemSKU -like "OEMCR*") {
            $SystemSku = "OEMCR"

        } elseif ($SystemSKU -like "OEMC*") {
            $SystemSku = "OEMC"

        } elseif ($SystemSKU -like "OEMB*") {
            $SystemSku = "OEMB"

        }else{
            #ThrowFailure ("System ($SystemSKU) is not currently enabled, Please email DWIGHT CARVER for support.")
        }

        "Using install SKU: $SystemSKU" | OutputStatusMessage
        $rootpath = $rootPath + $SystemSKU + "\"
        $rootpath  | OutputStatusMessage

    } else {
        "Failed to find OSImage registry key, cannot continue" | OutputStatusMessage
        return
    }

    $registry_Key= Get-ItemProperty -path "HKLM:\SOFTWARE\Microsoft\Surface\OSImage" -name "BranchName" -ErrorAction Continue
    if($registry_Key)
    {
        $rootpath = $rootPath + $registry_Key.BranchName + "\"
        $rootpath | OutputStatusMessage
    }

    $registry_Key= Get-ItemProperty -path "HKLM:\SOFTWARE\Microsoft\Surface\OSImage" -name "ImageVersion" -ErrorAction Continue
    if($registry_Key)
    {
        $imageVersion = $registry_Key.ImageVersion
        $imageVersion  | OutputStatusMessage
    }

    foreach ($f in (Get-ChildItem $rootpath | Where-Object {$_.psiscontainer}))
    {
        foreach ($folderFound in (Get-ChildItem $f.fullname | Where-Object {$_.psiscontainer}))
        {
            if ($folderFound.fullname -like ("*\$imageVersion"))
            {
                $script:fullImagePath = $folderFound.fullname + "\Image"
                $script:fullImagePath  | OutputStatusMessage
                return
            }
        }
    }

} # GetImagePath


#region main
############################
# MAIN
############################

$global:ErrorActionPreference = 'stop'
$IsWTTLogger = $false

# WTT LOGGING
$WttLogFileName = "GetImagePath.wtl"
$SBCT_DefaultTest = "Find image path from USB install registry keys."
Invoke-Expression ". $scriptpath\PSWttLogger.ps1" -ErrorAction Stop


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

    # no manual path then attempt search
    if ([string]::IsNullOrWhitespace($ManualPath))
    {
        if ($IsWTTLogger) {Start-WTTTest "Get Image Path"}
        GetImagePath
        if ($IsWTTLogger) {Stop-WTTTest -result "Pass" -name "Get Image Path"}
    } else {
        $script:fullImagePath = $ManualPath
    }

    if ($script:fullImagePath.IndexOf("\\") -eq 0)
    {
        # Set WTT Dimension
        & wttcmd.exe /ConfigReg /add /Value:WTT\AltOSBinRoot /Data:$script:fullImagePath
        New-ItemProperty -path "HKLM:SOFTWARE\Microsoft\Windows NT\CurrentVersion" -name "FullImagePath" -value $script:fullImagePath -PropertyType "string"  -force | out-null
        New-ItemProperty -path "HKLM:SOFTWARE\Microsoft\Surface\OSImage" -name "FullImagePath" -value $script:fullImagePath -PropertyType "string"  -force | out-null
    }

} catch {

    if ( $IsWTTLogger -eq $false)
    {
        Write-Host "----- TRAP ----"
        Write-Host "Unhandled Exception: $_"
        $_ | Format-List -Force
        #pause

    } else {
        GetErrorInfo | OutputStatusMessage
        Start-WTTTest "Catch Exception"
        Stop-WTTTest -result "Fail" -name "Catch Exception"

    }
    $Global:LocalExitCode = 1
    $ResultsXmlWriter.Close()

}

if ($IsWTTLogger) {Stop-WTTLog}

exit $Global:LocalExitCode
#endregion main
