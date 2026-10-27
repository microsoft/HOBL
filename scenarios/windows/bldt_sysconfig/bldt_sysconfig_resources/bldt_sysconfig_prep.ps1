# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$CacheRoot = '',
    [string]$LogRoot = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$scriptDrive = Split-Path -Qualifier $PSScriptRoot
if (-not $CacheRoot) { $CacheRoot = "$scriptDrive\hobl_bin\bldt_resources" }
if (-not $LogRoot) { $LogRoot = "$scriptDrive\hobl_data" }

function log {
    param([string]$Message)
    # Keep stdout exclusively for the JSON result consumed by Python.
    Add-Content -LiteralPath (Join-Path $LogRoot 'bldt_sysconfig_prep.log') -Value $Message -Encoding UTF8
}

function Close-Bldt {
    $running = @(Get-Process | Where-Object { $_.ProcessName -in 'BatteryLifeDiagnosticTool', 'bldtUI' })
    foreach ($process in $running) {
        if ($process.HasExited) { continue }
        log "Stopping existing BLDT session: $($process.ProcessName) (PID $($process.Id))"
        try { Stop-Process -Id $process.Id -Force -ErrorAction Stop }
        catch { if (-not $process.HasExited) { throw } }
        if (-not $process.WaitForExit(10000)) {
            throw "BLDT process $($process.Id) did not exit; cannot safely continue prep."
        }
    }
}

function Get-BldtState {
    # Registry fallbacks support custom paths and incomplete installations.
    $paths = @()
    $registrations = @{}
    $aiRegistered = $false
    foreach ($root in @('HKLM:\SOFTWARE', 'HKLM:\SOFTWARE\WOW6432Node')) {
        $intelKey = "$root\Intel\Battery Life Diagnostic Tool"
        $intelPath = $null
        if (Test-Path -LiteralPath $intelKey) {
            $intelPath = (Get-ItemProperty -LiteralPath $intelKey).Path
            $paths += $intelPath
        }
        $uninstall = "$root\Microsoft\Windows\CurrentVersion\Uninstall"
        if (Test-Path -LiteralPath $uninstall) {
            $entries = @(Get-ItemProperty -Path "$uninstall\*" | Where-Object {
                $_.DisplayName -like 'Intel* Battery Life Diagnostic Tool'
            })
            foreach ($entry in $entries) {
                if ($entry.PSChildName -eq '{E7ED588D-B332-4B9D-A0C0-90B1CC1403B2}') {
                    $aiRegistered = $true
                }
                $entryPaths = @($entry.InstallLocation)
                # Intel's MSI can leave InstallLocation empty; avoid guessing between registrations.
                if (-not $entry.InstallLocation -and $entries.Count -eq 1 -and $intelPath) {
                    $entryPaths += $intelPath
                }
                if ($entry.DisplayIcon) {
                    $icon = $entry.DisplayIcon -replace ',\s*-?\d+\s*$', ''
                    $entryPaths += Split-Path -Parent $icon.Trim('"')
                }
                foreach ($entryPath in $entryPaths | Where-Object { $_ }) {
                    $paths += $entryPath
                    $registrations[$entryPath.TrimEnd('\')] = $entry
                }
            }
        }
    }
    $installations = @(
        foreach ($path in $paths | Where-Object { $_ } | Select-Object -Unique) {
            $exe = Join-Path $path 'BatteryLifeDiagnosticTool.exe'
            if (Test-Path -LiteralPath $exe -PathType Leaf) {
                $registration = $registrations[$path.TrimEnd('\')]
                $version = (Get-Item -LiteralPath $exe).VersionInfo.ProductVersion
                $versionSource = 'executable'
                # Some BLDT executables omit version metadata; use only the matching registration.
                if ([string]::IsNullOrWhiteSpace($version)) {
                    $version = $registration.DisplayVersion
                    $versionSource = 'registry'
                }
                if ([string]::IsNullOrWhiteSpace($version)) { $versionSource = 'missing' }
                $isAi = $version -eq '3.1.1.26073107' -or
                    $registration.PSChildName -eq '{E7ED588D-B332-4B9D-A0C0-90B1CC1403B2}'
                [pscustomobject]@{
                    executable = $exe; version = $version; version_source = $versionSource
                    edition = if ($isAi) { 'ai' } else { 'standard' }
                }
            }
        }
    )
    return [pscustomobject]@{
        installations = $installations; ai_registered = $aiRegistered
    }
}

function Select-BldtInstallation {
    param([object]$State)
    foreach ($installation in $State.installations) {
        if ($installation.version -like '3.1.1.*') {
            return $installation
        }
    }
}

function Get-BldtPackage {
    param([string]$Edition)
    # Exact hashes pin the downloaded archive and the MSI extracted from it.
    if ($Edition -eq 'ai') {
        return @{
            stem = 'bldt-ai_setup-v3.1.1'
            zip_hash = '036B5486EE05EDBE3D9B81E655BE3583774C40F126A336600413551793141253'
            msi_hash = '9E15817BBF784545B08E6C1F6565F7C9AEB7981236DF2EBC9313A78D6ED4A94F'
            product = '{E7ED588D-B332-4B9D-A0C0-90B1CC1403B2}'
        }
    }
    return @{
        stem = 'bldt_setup-v3.1.1'
        zip_hash = 'B3EDE18017750D51BFA73435D1C9C89E260B278835906D7BFFF4EA626A523DAD'
        msi_hash = '2AE4271EC6281B1D30215B992D0650F6A298BB776CBEB4E3E537E02A1FEA2449'
        product = '{F6F5593F-70FE-4126-9415-99DAFCCF14F9}'
    }
}

function Get-BldtFileHash {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    }
    return ''
}

function Install-Bldt {
    param([string]$Edition)
    # 1. Fail before downloading when this DUT context cannot install software.
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    try {
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            throw 'BLDT installation requires an elevated DUT execution context.'
        }
    } finally {
        $identity.Dispose()
    }
    $package = Get-BldtPackage $Edition
    $downloads = Join-Path $CacheRoot 'downloads'
    $expanded = Join-Path $CacheRoot "packages\$Edition"
    $archive = Join-Path $downloads ($package.stem + '.zip')
    New-Item -ItemType Directory -Path $downloads, $expanded -Force | Out-Null

    # 2. A partial download never replaces the cache until its hash is verified.
    if ((Get-BldtFileHash $archive) -ne $package.zip_hash) {
        $url = "https://downloadmirror.intel.com/925424/$($package.stem).zip"
        log "Downloading $url to $archive"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $url -OutFile "$archive.partial" -UseBasicParsing -TimeoutSec 10800
        if ((Get-BldtFileHash "$archive.partial") -ne $package.zip_hash) {
            throw 'BLDT ZIP checksum mismatch; installation was not attempted.'
        }
        Move-Item -LiteralPath "$archive.partial" -Destination $archive -Force
    } else {
        log "Reusing verified BLDT package: $archive"
    }

    # 3. Verify the exact installer, then check Intel's Authenticode signature.
    log "Extracting BLDT package to $expanded"
    Expand-Archive -LiteralPath $archive -DestinationPath $expanded -Force
    $installers = @(Get-ChildItem -LiteralPath $expanded -Filter ($package.stem + '.msi') -File -Recurse)
    if ($installers.Count -ne 1) {
        throw "Expected exactly one BLDT installer, found $($installers.Count)."
    }
    $msi = $installers[0].FullName
    if ((Get-BldtFileHash $msi) -ne $package.msi_hash) {
        throw 'BLDT MSI checksum mismatch; installation was not attempted.'
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $msi
    if ($signature.Status -ne 'Valid' -or
        $signature.SignerCertificate.Subject -notmatch '(^|,\s*)O=Intel Corporation(,|$)') {
        throw 'BLDT MSI does not have a valid Intel signature.'
    }

    # 4. Repair a registered product instead of silently treating it as ready.
    $installer = New-Object -ComObject WindowsInstaller.Installer
    try { $repair = $installer.ProductState($package.product) -ge 3 }
    finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($installer) }
    $mode = if ($repair) { '/fvamus' } else { '/i' }
    $prefix = Join-Path $LogRoot 'bldt_sysconfig_prep'
    $exe = Join-Path $env:SystemRoot 'System32\msiexec.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw "Windows Installer executable not found: $exe"
    }
    $arguments = "$mode `"$msi`" /qn /norestart REBOOT=ReallySuppress " +
        "WIXUI_EXITDIALOGOPTIONALCHECKBOX=0 /L*v `"$prefix.msi.log`""
    log "Installing BLDT $Edition using $exe; MSI log: $prefix.msi.log"
    $process = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory (Split-Path -Parent $msi) `
        -RedirectStandardOutput "$prefix.stdout.log" -RedirectStandardError "$prefix.stderr.log" -PassThru
    try {
        # An RPC timeout alone would leave the installer running on the DUT.
        $null = $process.Handle
        if (-not $process.WaitForExit(10800000)) {
            Stop-Process -Id $process.Id -Force
            if (-not $process.WaitForExit(10000)) { throw 'Timed-out BLDT installer could not be stopped.' }
            throw 'BLDT installation timed out after 10800 seconds.'
        }
        $process.WaitForExit()
        $code = $process.ExitCode
        if ($null -eq $code) { throw 'BLDT installer exit code is unavailable.' }
    } finally {
        $process.Dispose()
    }
    if ($code -in 1641, 3010) {
        throw 'BLDT installation requires a DUT reboot; reboot and rerun prep.'
    }
    if ($code -ne 0) { throw "BLDT installation failed ($code); see the MSI log." }
}

function Initialize-Bldt {
    # A prep marker is not consulted here: inspect the installation on every run.
    $state = Get-BldtState
    log ("BLDT discovery: " + ($state | ConvertTo-Json -Depth 4 -Compress))
    $installation = Select-BldtInstallation $state
    $installed = $false
    if ($null -eq $installation) {
        # Preserve an existing AI edition, even when its executable is missing.
        $edition = if ($state.ai_registered -or
            @($state.installations | Where-Object edition -eq 'ai').Count -gt 0) { 'ai' } else { 'standard' }
        Install-Bldt $edition
        $state = Get-BldtState
        log ("BLDT discovery after prep: " + ($state | ConvertTo-Json -Depth 4 -Compress))
        $installation = Select-BldtInstallation $state
        if ($null -eq $installation) { throw 'BLDT installation is still incomplete after prep.' }
        $installed = $true
    }
    log ("BLDT ready: " + ($installation | ConvertTo-Json -Compress))
    return [pscustomobject]@{ installation = $installation; installed = $installed }
}

try {
    New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $LogRoot 'bldt_sysconfig_prep.log') -Value '-- BLDT prep --' -Encoding UTF8
    # Use this PowerShell's modules, not PowerShell 7 modules from PSModulePath.
    foreach ($name in @('Microsoft.PowerShell.Utility', 'Microsoft.PowerShell.Archive', 'Microsoft.PowerShell.Security')) {
        Import-Module (Join-Path $PSHOME "Modules\$name\$name.psd1")
    }
    Close-Bldt
    Initialize-Bldt | ConvertTo-Json -Depth 4 -Compress
} catch {
    $message = " ERROR - $($_.Exception.Message)"
    Write-Output $message
    Add-Content -LiteralPath (Join-Path $LogRoot 'bldt_sysconfig_prep.log') -Value $message -Encoding UTF8
    exit 1
}
