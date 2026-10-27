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
    Add-Content -LiteralPath (Join-Path $LogRoot 'bldt_ai_analysis_prep.log') -Value $Message -Encoding UTF8
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

function Get-BldtInstallation {
    # Follow the other BLDT scenarios' registry/version fallbacks for custom paths.
    $paths = @()
    $registrations = @{}
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
                $entryPaths = @($entry.InstallLocation)
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
    foreach ($path in $paths | Where-Object { $_ } | Select-Object -Unique) {
        $exe = Join-Path $path 'BatteryLifeDiagnosticTool.exe'
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { continue }
        $entry = $registrations[$path.TrimEnd('\')]
        $version = (Get-Item -LiteralPath $exe).VersionInfo.ProductVersion
        if ([string]::IsNullOrWhiteSpace($version)) { $version = $entry.DisplayVersion }
        if ($version -eq '3.1.1.26073107') {
            $missing = @('AIAnalyzer', 'AIAnalyzerModels' | Where-Object {
                $archive = Join-Path $path "src\$_.tar.gz"
                -not (Test-Path -LiteralPath $archive -PathType Leaf) -or
                    (Get-Item -LiteralPath $archive).Length -eq 0
            })
            if ($missing.Count -gt 0) {
                log "BLDT AI payloads missing at $path; repair required: $($missing -join ', ')"
                continue
            }
            log "Found BLDT AI $version at $exe"
            return [pscustomobject]@{ executable = $exe; version = $version }
        }
    }
}

function Get-FileHashOrEmpty {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    }
    return ''
}

function Install-Bldt {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    try {
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            throw 'BLDT AI installation requires an elevated DUT execution context.'
        }
    } finally { $identity.Dispose() }
    $downloads = Join-Path $CacheRoot 'downloads'
    $expanded = Join-Path $CacheRoot 'packages\ai'
    $stem = 'bldt-ai_setup-v3.1.1'
    $archive = Join-Path $downloads "$stem.zip"
    $zipHash = '036B5486EE05EDBE3D9B81E655BE3583774C40F126A336600413551793141253'
    New-Item -ItemType Directory -Path $downloads, $expanded -Force | Out-Null
    if ((Get-FileHashOrEmpty $archive) -ne $zipHash) {
        $url = "https://downloadmirror.intel.com/925424/$stem.zip"
        log "Downloading $url to $archive"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $url -OutFile "$archive.partial" -UseBasicParsing -TimeoutSec 10800
        if ((Get-FileHashOrEmpty "$archive.partial") -ne $zipHash) {
            throw 'BLDT AI ZIP checksum mismatch; installation was not attempted.'
        }
        Move-Item -LiteralPath "$archive.partial" -Destination $archive -Force
    } else {
        log "Reusing verified BLDT AI package: $archive"
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $expanded -Force
    $installers = @(Get-ChildItem -LiteralPath $expanded -Filter "$stem.msi" -File -Recurse)
    if ($installers.Count -ne 1) { throw "Expected one BLDT AI installer, found $($installers.Count)." }
    $msi = $installers[0].FullName
    if ((Get-FileHashOrEmpty $msi) -ne '9E15817BBF784545B08E6C1F6565F7C9AEB7981236DF2EBC9313A78D6ED4A94F') {
        throw 'BLDT AI MSI checksum mismatch; installation was not attempted.'
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $msi
    if ($signature.Status -ne 'Valid' -or
        $signature.SignerCertificate.Subject -notmatch '(^|,\s*)O=Intel Corporation(,|$)') {
        throw 'BLDT AI MSI does not have a valid Intel signature.'
    }
    $sourceDir = Split-Path -Parent $msi
    foreach ($payloadName in @('AIAnalyzer.tar.gz', 'AIAnalyzerModels.tar.gz')) {
        $payload = Join-Path $sourceDir "src\$payloadName"
        if (-not (Test-Path -LiteralPath $payload -PathType Leaf) -or
            (Get-Item -LiteralPath $payload).Length -eq 0) {
            throw "BLDT AI installer payload missing or empty: $payload"
        }
    }
    $installer = New-Object -ComObject WindowsInstaller.Installer
    try { $repair = $installer.ProductState('{E7ED588D-B332-4B9D-A0C0-90B1CC1403B2}') -ge 3 }
    finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($installer) }
    $mode = if ($repair) { '/fvamus' } else { '/i' }
    $exe = Join-Path $env:SystemRoot 'System32\msiexec.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Windows Installer not found: $exe" }
    $prefix = Join-Path $LogRoot 'bldt_ai_analysis_prep'
    # Intel sets this property only in its UI sequence, which /qn skips.
    $arguments = "$mode `"$msi`" /qn /norestart REBOOT=ReallySuppress " +
        "INSTALLER_SOURCE_DIR=`"$sourceDir`" WIXUI_EXITDIALOGOPTIONALCHECKBOX=0 /L*v `"$prefix.msi.log`""
    log "Installing BLDT AI using $exe; source: $sourceDir; MSI log: $prefix.msi.log"
    $process = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $sourceDir `
        -RedirectStandardOutput "$prefix.stdout.log" -RedirectStandardError "$prefix.stderr.log" -PassThru
    try {
        $null = $process.Handle
        if (-not $process.WaitForExit(10800000)) {
            Stop-Process -Id $process.Id -Force
            $null = $process.WaitForExit(10000)
            throw 'BLDT AI installation timed out after 10800 seconds.'
        }
        $process.WaitForExit()
        $code = $process.ExitCode
        if ($null -eq $code) { throw 'BLDT AI installer exit code is unavailable.' }
    } finally { $process.Dispose() }
    if ($code -in 1641, 3010) { throw 'BLDT AI installation requires a DUT reboot; reboot and rerun prep.' }
    if ($code -ne 0) { throw "BLDT AI installation failed ($code); see the MSI log." }
}

try {
    New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $LogRoot 'bldt_ai_analysis_prep.log') -Value '-- BLDT AI prep --' -Encoding UTF8
    foreach ($name in @('Microsoft.PowerShell.Utility', 'Microsoft.PowerShell.Archive', 'Microsoft.PowerShell.Security')) {
        Import-Module (Join-Path $PSHOME "Modules\$name\$name.psd1")
    }
    Close-Bldt
    $installation = Get-BldtInstallation
    if ($null -eq $installation) {
        Install-Bldt
        $installation = Get-BldtInstallation
        if ($null -eq $installation) { throw 'BLDT AI installation is still incomplete after prep.' }
    }
    $installation | ConvertTo-Json -Compress
} catch {
    $message = " ERROR - $($_.Exception.Message)"
    Write-Output $message
    Add-Content -LiteralPath (Join-Path $LogRoot 'bldt_ai_analysis_prep.log') -Value $message -Encoding UTF8
    exit 1
}
