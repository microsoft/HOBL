# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$logFile = "c:\temp\host_setup.log",
    [switch]$framework,
    [switch]$local,
    [switch]$ui
)

# HOBL UI and Dut Setup versions
$hobl_ui_version = "1.6"
# Set $dut_setup_version to value at top of setup_src\src_dut_win\dut_setup.cmd
$dut_setup_cmd = "$PSScriptRoot\..\src_dut_win\dut_setup.cmd"
if (Test-Path $dut_setup_cmd) {
    $firstLine = (Get-Content -Path $dut_setup_cmd -TotalCount 1).Trim()
    if ($firstLine -match 'set\s+DUT_SETUP_VERSION=(.+)') {
        $dut_setup_version = $matches[1]
    } else {
        $dut_setup_version = "ERROR"
    }
} else {
    $dut_setup_version = "ERROR"
}

# Disable progress bars to speed up downloads
$ProgressPreference = 'SilentlyContinue'

function log {
    [CmdletBinding()] Param([Parameter(ValueFromPipeline)] $msg)
    process {
        if ($msg -Match "ERROR:") {
            Write-Host $msg -ForegroundColor Red
        } else {
            Write-Host $msg
        }
        Add-Content -Path $logFile -encoding utf8 "$msg"
    }
}

function check {
    param($code)
    if ($code -ne 0) {
        "ERROR: Last command failed." | log
        Exit $code
    }
}

function checkCmd {
    param($code)
    if ($code -ne "True") {
        "ERROR: Last command failed." | log
        Exit 1
    }
}

New-Item -ItemType Directory -Force -Path c:\temp > $null
New-Item -ItemType Directory -Force -Path c:\hobl_results > $null

Set-Content -Path $logFile -encoding utf8 "-- HOBL Install started"
"Install framework: $framework" | log
"Install ui: $ui" | log
"Install local: $local" | log

# Validate args
if ($framework -eq $false -and $ui -eq $false) {
    "No components specifed. Aborting." | log
    "`nYou must specify at least one of: " | log
    "  -framework" | log
    "  -ui" | log
    exit 1
}

# Check sector size for SQL Server LocalDB.  If the sector size is greater than 4K, SQL Server LocalDB will not work.
if ($ui) {
    $bigSectorFlag = $false
    try {
        # Get all disks and their physical sector sizes
        $disks = Get-Disk | Select-Object Number, FriendlyName, PhysicalSectorSize

        if (-not $disks) {
            "ERROR: No disks found or insufficient permissions." | log
            exit 1
        }

        foreach ($disk in $disks) {
            $sectorSize = [int64]$disk.PhysicalSectorSize

            if ($sectorSize -gt 4096) {
                $bigSectorFlag = $true
                "ERROR: Disk $($disk.Number) [$($disk.FriendlyName)]: Physical sector size ($sectorSize bytes) is > 4096." | log
            }
        }
    }
    catch {
        "ERROR: Error retrieving disk information: $_" | log
    }

    if ($bigSectorFlag) {
        reg add "HKLM\SYSTEM\CurrentControlSet\Services\stornvme\Parameters\Device" /v "ForcedPhysicalSectorSizeInBytes" /t REG_MULTI_SZ /d "* 4096" /f
        "ERROR: One or more disks have a physical sector size greater than 4K, which will prevent SQL Server from working." | log
        "ERROR: I've set the sector size to 4K in the registry to resolve this, but a reboot is needed for it to take effect." | log
        "ERROR: Please reboot and rerun the installer." | log
        Read-Host -Prompt "-- Press Enter to exit"
        exit 1
    }
}

##
## HOBL
##

if ($framework) {

    $runtimeVersion = "8.0.29"
    $runtimeX64DownloadUrl = "https://builds.dotnet.microsoft.com/dotnet/WindowsDesktop/$runtimeVersion/windowsdesktop-runtime-$runtimeVersion-win-x86.exe"
    $vcRedistUrl = "https://aka.ms/vs/17/release/vc_redist.x86.exe"

    # Create downloads directory structure if it doesn't exist
    New-Item -ItemType Directory -Force -Path "$PSScriptRoot\..\..\downloads\setup\assets" > $null

    # Download .NET Windows Desktop Runtime installers
    $runtimeFilePath = "$PSScriptRoot\..\..\downloads\setup\assets\windowsdesktop-runtime-$runtimeVersion-win-x86.exe"
    if (-not (Test-Path $runtimeFilePath)) {
        "-- Downloading .NET Windows Desktop Runtime $runtimeVersion" | log
        Invoke-WebRequest -Uri $runtimeX64DownloadUrl -OutFile $runtimeFilePath 2>&1 | log
        checkCmd($?)
        "-- Installing .NET Windows Desktop Runtime $runtimeVersion" | log
        & "$runtimeFilePath" /quiet 2>&1 | log
        # check($lastexitcode)
    } else {
        "   $runtimeFilePath already exists, skipping download" | log
    }

    # Download Visual C++ Redistributable
    $vcRedistPath = "$PSScriptRoot\..\..\downloads\setup\assets\vc_redist.x86.exe"
    if (-not (Test-Path $vcRedistPath)) {
        "-- Downloading Visual C++ Redistributable" | log
        Invoke-WebRequest -Uri $vcRedistUrl -OutFile $vcRedistPath 2>&1 | log
        checkCmd($?)
        "-- Installing Visual C++ Redistributable" | log
        & "$vcRedistPath" /install /quiet /norestart 2>&1 | log
        # check($lastexitcode)
    } else {
        "   $vcRedistPath already exists, skipping download" | log
    }

    # Download dut_setup
    "-- Downloading DUT setup" | log
    $dut_setupUrl = "https://github.com/microsoft/HOBL/releases/download/dut_setup/dut_setup_$dut_setup_version.exe"
    $dut_setupZip = "$PSScriptRoot\..\..\downloads\setup\dut_setup_$dut_setup_version.exe"
    if (-not (Test-Path $dut_setupZip)) {
        Invoke-WebRequest -Uri $dut_setupUrl -OutFile $dut_setupZip 2>&1 | log
        checkCmd($?)
    }
    $dut_setupUrl = "https://github.com/microsoft/HOBL/releases/download/dut_setup/dut_setup_$dut_setup_version.sh"
    $dut_setupZip = "$PSScriptRoot\..\..\downloads\setup\dut_setup_$dut_setup_version.sh"
    if (-not (Test-Path $dut_setupZip)) {
        Invoke-WebRequest -Uri $dut_setupUrl -OutFile $dut_setupZip 2>&1 | log
        checkCmd($?)
    }

    # Install embedded python
    "-- Installing embedded Python" | log
    & "$PSScriptRoot\python_embed_install.cmd" 2>&1 | log
    check($lastexitcode)

    # Download ffmpeg
    "-- Downloading ffmpeg win64" | log
    $ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-02-28-12-59/ffmpeg-N-123073-g743df5ded9-win64-gpl.zip"
    $ffmpegZip = "$PSScriptRoot\..\..\downloads\ffmpeg_win64.zip"
    if (-not (Test-Path "$PSScriptRoot\..\..\downloads\ffmpeg_win64")) {
        Invoke-WebRequest -Uri $ffmpegUrl -OutFile $ffmpegZip 2>&1 | log
        checkCmd($?)
        start-sleep -seconds 1 # Wait a bit to ensure file is fully written before expanding
        Expand-Archive -Path $ffmpegZip -DestinationPath "$PSScriptRoot\..\..\downloads" -Force 2>&1 | log
        checkCmd($?)
        start-sleep -seconds 2 # Wait a bit to ensure all file handles are released before moving/deleting
        Move-Item "$PSScriptRoot\..\..\downloads\ffmpeg-N-123073-g743df5ded9-win64-gpl" "$PSScriptRoot\..\..\downloads\ffmpeg_win64" -Force 2>&1 | log
        Remove-Item $ffmpegZip 2>&1 | log        
    }
    # "-- Downloading ffmpeg arm64" | log
    # $ffmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-02-28-12-59/ffmpeg-N-123073-g743df5ded9-winarm64-gpl.zip"
    # $ffmpegZip = "$PSScriptRoot\..\..\downloads\ffmpeg_arm64.zip"
    # Invoke-WebRequest -Uri $ffmpegUrl -OutFile $ffmpegZip 2>&1 | log
    # check($lastexitcode)
    # Expand-Archive -Path $ffmpegZip -DestinationPath "$PSScriptRoot\..\..\downloads" -Force 2>&1 | log
    # check($lastexitcode)
    # Move-Item "$PSScriptRoot\..\..\downloads\ffmpeg-N-123073-g743df5ded9-winarm64-gpl" "$PSScriptRoot\..\..\downloads\ffmpeg_arm64" -Force 2>&1 | log
    # Remove-Item $ffmpegZip 2>&1 | log

    if (Test-Path -Path ".git") {
        # Set git hooks if git exists
        if (Get-Command git.exe -ErrorAction SilentlyContinue) {
            "-- Setting git hooks path" | log
            pushd $PSScriptRoot\..\.. > $null
            git.exe config core.hooksPath git_hooks 2>&1 | log
            # check($lastexitcode)

            "-- Updating hobl version" | log
            git.exe hook run post-checkout 2>&1 | log
            popd > $null
        }
        else {
            "-- git not found, skipping git hook setup" | log
        }
    }
    else {
        "-- Not a git repository, skipping git hook setup" | log
    }

    # Disable error reporting UI
    "-- Disabling Windows Error Reporting UI" | log
    reg add "HKLM\Software\Microsoft\Windows\Windows Error Reporting" /f /v DontShowUI /t REG_DWORD /d 1 2>&1 | log
    check($lastexitcode)
}

##
## Local
##

if ($local) {
    "-- Installing DUT setup" | log
    # create c:\hobl_data and c:\hobl_bin if they don't exist
    New-Item -ItemType Directory -Force -Path c:\hobl_bin > $null
    New-Item -ItemType Directory -Force -Path c:\hobl_data > $null
    # run dut_setup.cmd with local_setup=1
    & "$PSScriptRoot\..\..\hobl.cmd" -s dut_setup local_setup=1 2>&1 | log
    check($lastexitcode)
}

##
## UI 
##

if ($ui) {
    # SQL Server requires storage sector size to be 4K or less.  This might require a reboot to take effect.
    reg add "HKLM\SYSTEM\CurrentControlSet\Services\stornvme\Parameters\Device" /v "ForcedPhysicalSectorSizeInBytes" /t REG_MULTI_SZ /d "* 4096" /f

    # Backup existing appsettings.json and delete existing hoblweb folder
    if (test-path c:\hoblweb) {
        "-- Backing up HOBLweb appsettings.json" | log
        Copy-Item c:\HOBLweb\appsettings.json c:\temp\appsettings.json 2>&1 | log
        "-- Deleting existing HOBLweb" | log
        Stop-Process -Name hoblweb -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        remove-item c:\hoblweb -recurse -force 2>&1 | log
    }

    # Download hobl ui zip file
    "-- Downloading HOBLweb" | log
    $uiUrl = "https://github.com/microsoft/HOBL/releases/download/hobl_ui/hobl_ui_$hobl_ui_version.tar"
    $uiZip = "c:\hoblweb.tar"
    Invoke-WebRequest -Uri $uiUrl -OutFile $uiZip 2>&1 | log
    checkCmd($?)
    "-- Unpacking HOBLweb" | log
    mkdir c:\hoblweb
    tar -xf $uiZip -C "c:\hoblweb" 2>&1 | log
    checkCmd($?)
    Remove-Item $uiZip 2>&1 | log
    checkCmd($?)

    "-- Installing vc_redist" | log
    c:\hoblweb\vc_redist.x64.exe /install /quiet /norestart 2>&1 | log
    c:\hoblweb\vc_redist.x86.exe /install /quiet /norestart 2>&1 | log

    "-- Installing dotnet hosting" | log
    # This will throw error if IIS not installed, so don't check
    c:\hoblweb\dotnet-hosting-10.0.5-win.exe /install /quiet /norestart 2>&1 | log

    "-- Installing local DB" | log
    msiexec /i c:\hoblweb\SqlLocalDB.msi /qb IACCEPTSQLLOCALDBLICENSETERMS=YES 2>&1 | log
    check($lastexitcode)
    &"c:\Program Files\microsoft sql server\150\tools\binn\sqllocaldb.exe" create HOBL 2>&1 | log
    check($lastexitcode)
    &"c:\Program Files\microsoft sql server\150\tools\binn\sqllocaldb.exe" start HOBL 2>&1 | log
    check($lastexitcode)

    # Restore appsettings.json
    if (test-path c:\temp\appsettings.json) {
        "-- Restoring backed up appsettings.json" | log
        Copy-Item c:\temp\appsettings.json c:\HOBLweb\appsettings.json 2>&1 | log
    } else {
        "-- Copying default appsettings.json" | log
        Copy-Item c:\HOBLweb\appsettings.default.json c:\HOBLweb\appsettings.json 2>&1 | log
    }

    # Open firewall
    "-- Opening firewall for hoblweb.exe" | log
    netsh advfirewall firewall delete rule name="HOBLweb" 2>&1 > $null
    netsh advfirewall firewall add rule name="HOBLweb" program="C:\hoblweb\hoblweb.exe" dir=in action=allow enable=yes localport=any protocol=TCP profile=public,private,domain 2>&1 | log
    check($lastexitcode)

    # Add desktop shortcut
    "-- Copying launch shortcut to desktop" | log
    $desktopPath = [Environment]::GetFolderPath('Desktop')
    Copy-Item c:\HOBLweb\HOBLweb.lnk "$desktopPath\HOBLweb.lnk" 2>&1 | log

    # Update appsettings.json with path to hobl set to the location of hobl, which is the location of this script and up two levels.
    "-- Adding HoblPath to appsettings.json" | log
    $appSettingsPath = "c:\HOBLweb\appsettings.json"
    # Set $hoblPath to the parent directory of the script's directory (which is the root of the HOBL repo)
    $hoblPath = Join-Path $PSScriptRoot "..\.."
    $hoblPath = (Resolve-Path $hoblPath).Path | ConvertTo-Json
    if (Test-Path $appSettingsPath) {
        $appSettingsContent = Get-Content $appSettingsPath -Raw
        # if HoblPath already exists, replace it, otherwise add it
        if ($appSettingsContent -match '"HoblPath"\s*:\s*".*?"') {
            $appSettingsContent = $appSettingsContent -replace '"HoblPath"\s*:\s*".*?"', "`"HoblPath`": $hoblPath"
        } else {
            # Add HoblPath before the last closing curly brace
            $appSettingsContent = $appSettingsContent -replace '(?s)\}\s*$', ",`n  `"HoblPath`": $hoblPath`n}"
        }
        Set-Content -Path $appSettingsPath -Value $appSettingsContent -Encoding UTF8
    }

    # Launch HOBL UI
    "-- Launching HOBLweb" | log
    start-process -FilePath "c:\hoblweb\hoblweb.cmd" -ArgumentList "install" -WorkingDirectory "c:\hoblweb" -WindowStyle hidden
    checkCmd($?)

    # Register scheduled task to launch HOBLweb at login
    "-- Registering scheduled task to launch HOBLweb at login" | log
    # Delete task if it exists, but ignore errors if it doesn't exist
    Unregister-ScheduledTask -TaskName "Launch HOBL UI" -Confirm:$false -ErrorAction SilentlyContinue
    # Register new task
    $taskName = "Launch HOBL UI"
    $taskAction = New-ScheduledTaskAction -Execute "c:\hoblweb\hoblweb.cmd" -WorkingDirectory "c:\hoblweb"
    $taskTrigger = New-ScheduledTaskTrigger -AtLogOn
    $taskSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $taskTrigger -Settings $taskSettings -RunLevel Highest -Force 2>&1 | log
    checkCmd($?)

    "-- Install complete, it may take about a minute for the UI to auto-launch for the first time." | log
    #"-- Waiting ~30 seconds for first time app launch" | log
    # Start-Sleep -seconds 15
    # Press any key to exit
    # Read-Host -Prompt "-- Press Enter to exit"

    # Wait up to 60 seconds for the UI to become available.
    $uiUrl = "http://localhost/support/Contact"
    $deadline = (Get-Date).AddSeconds(60)
    $uiReady = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $uiUrl -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                $uiReady = $true
                break
            }
        } catch {
            # The UI may still be starting; retry until the deadline.
        }
        Start-Sleep -Seconds 1
    }
    if ($uiReady) {
        "-- HOBLweb is ready" | log
    } else {
        "-- Timed out after 60 seconds waiting for $uiUrl" | log
    }
    
}

Exit 0