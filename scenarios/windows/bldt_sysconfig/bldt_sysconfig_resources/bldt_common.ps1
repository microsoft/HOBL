# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$script:BldtProductName = "Intel$([char]0x00AE) Battery Life Diagnostic Tool"
$script:BldtVersionPrefix = '3.1.1.'
$script:BldtUpgradeCode = '{B0ECCF05-0125-4FA1-B8D2-9B22BD1DCD8D}'
$script:BldtStandardProductCode = '{F6F5593F-70FE-4126-9415-99DAFCCF14F9}'
$script:BldtAiProductCode = '{E7ED588D-B332-4B9D-A0C0-90B1CC1403B2}'

function log {
    [CmdletBinding()] Param([Parameter(ValueFromPipeline)] $msg)
    process {
        if ($msg -Match " ERROR - ") {
            Write-Host $msg -ForegroundColor Red
        } else {
            Write-Host $msg
        }
        Add-Content -LiteralPath $logFile -Value "$msg" -Encoding UTF8
    }
}

function Assert-BldtCompatibility {
    $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
    $processors = @(Get-CimInstance -ClassName Win32_Processor -ErrorAction Stop)
    if ($null -eq $os -or $processors.Count -eq 0) {
        throw 'Unable to determine the DUT operating system and processor for BLDT compatibility checks.'
    }
    "Detected OS: $($os.Caption); version: $($os.Version)" | log
    foreach ($processor in $processors) {
        "Detected processor: $($processor.Name); manufacturer: $($processor.Manufacturer)" | log
    }
    if ([string]::IsNullOrWhiteSpace($os.Version)) {
        throw 'Unable to determine the Windows version for BLDT compatibility checks.'
    }
    if ([version]$os.Version -lt [version]'10.0') {
        throw "BLDT requires Windows 10 or later. Detected: $($os.Caption) ($($os.Version))."
    }

    foreach ($processor in $processors) {
        $manufacturer = ([string]$processor.Manufacturer).Trim()
        $name = ([string]$processor.Name).Trim()
        if (-not $manufacturer -or -not $name) {
            throw 'Unable to determine the processor name and manufacturer for BLDT compatibility checks.'
        }
        if ($manufacturer -notin @('GenuineIntel', 'Intel', 'Intel Corporation')) {
            throw "BLDT requires an Intel Core or Intel Ultra processor. Detected: $name ($manufacturer)."
        }

        $normalizedName = $name -replace '\((?:R|TM)\)|[\u00ae\u2122]', ''
        if ($normalizedName -match '\b(?:Atom|Celeron|Pentium|Xeon)\b|\bCore\s*2\b' -or
            $normalizedName -match '\bCore\s+i[3579][ -]+(?:CPU\s+)?(?:\d{3}|[2-7]\d{3})[A-Z]*\b') {
            throw "BLDT requires an Intel Core or Intel Ultra processor, 8th generation or later. Unsupported processor: $name."
        }

        # Recognize common Core naming schemes without treating unknown names as unsupported.
        if ($normalizedName -notmatch '\bCore\s+i[3579][ -]+(?:[89]\d{3}|1[0-4]\d{3}|1[01]\d{2}G[147])[A-Z]*\b' -and
            $normalizedName -notmatch '\bCore\s+(?:Ultra\s+)?[3579]\s+\d{3}[A-Z]*\b') {
            " WARNING - Cannot confirm BLDT processor family/generation from '$name'. Continuing; verify Intel Core/Ultra 8th generation or later support manually." | log
        }
    }
}

function Invoke-BldtProcess {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$ArgumentList,
        [Parameter(Mandatory)][string]$StandardOutput,
        [Parameter(Mandatory)][string]$StandardError,
        [Parameter(Mandatory)][ValidateRange(1, 7200)][int]$TimeoutSeconds
    )

    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList `
        -RedirectStandardOutput $StandardOutput -RedirectStandardError $StandardError -PassThru
    try {
        # Retain the handle before exit; Windows PowerShell otherwise can lose ExitCode.
        $null = $process.Handle
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            Stop-Process -Id $process.Id -Force -ErrorAction Stop
            if (-not $process.WaitForExit(10000)) {
                throw "BLDT SysConfigChecks exceeded the $TimeoutSeconds second timeout and could not be terminated."
            }
            throw "BLDT SysConfigChecks exceeded the $TimeoutSeconds second timeout."
        }
        $process.WaitForExit()
        if ($null -eq $process.ExitCode) {
            throw 'Unable to retrieve the BLDT process exit code.'
        }
        return $process.ExitCode
    } finally {
        $process.Dispose()
    }
}

function Get-BldtPackageDefinition {
    param([Parameter(Mandatory)][ValidateSet('standard', 'ai')][string]$Edition)

    if ($Edition -eq 'ai') {
        return [pscustomobject]@{
            Edition = 'ai'
            Url = 'https://downloadmirror.intel.com/925424/bldt-ai_setup-v3.1.1.zip'
            ZipName = 'bldt-ai_setup-v3.1.1.zip'
            ZipSha256 = '036B5486EE05EDBE3D9B81E655BE3583774C40F126A336600413551793141253'
            MsiName = 'bldt-ai_setup-v3.1.1.msi'
            MsiSha256 = '9E15817BBF784545B08E6C1F6565F7C9AEB7981236DF2EBC9313A78D6ED4A94F'
            ProductCode = $script:BldtAiProductCode
            ProductVersion = '3.1.1.26073107'
        }
    }

    return [pscustomobject]@{
        Edition = 'standard'
        Url = 'https://downloadmirror.intel.com/925424/bldt_setup-v3.1.1.zip'
        ZipName = 'bldt_setup-v3.1.1.zip'
        ZipSha256 = 'B3EDE18017750D51BFA73435D1C9C89E260B278835906D7BFFF4EA626A523DAD'
        MsiName = 'bldt_setup-v3.1.1.msi'
        MsiSha256 = '2AE4271EC6281B1D30215B992D0650F6A298BB776CBEB4E3E537E02A1FEA2449'
        ProductCode = $script:BldtStandardProductCode
        ProductVersion = '3.1.1.26073103'
    }
}

function Test-BldtElevated {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    try {
        $principal = [Security.Principal.WindowsPrincipal]::new($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } finally {
        $identity.Dispose()
    }
}

function Get-BldtUninstallEntries {
    $registryPaths = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'
    )

    foreach ($registryPath in $registryPaths) {
        if (-not (Test-Path -LiteralPath $registryPath)) {
            continue
        }
        foreach ($key in Get-ChildItem -LiteralPath $registryPath -ErrorAction SilentlyContinue) {
            $entry = Get-ItemProperty -LiteralPath $key.PSPath -ErrorAction SilentlyContinue
            if ($null -eq $entry) {
                continue
            }
            $displayNameProperty = $entry.PSObject.Properties['DisplayName']
            if ($null -ne $displayNameProperty -and $displayNameProperty.Value -eq $script:BldtProductName) {
                $displayVersionProperty = $entry.PSObject.Properties['DisplayVersion']
                $installLocationProperty = $entry.PSObject.Properties['InstallLocation']
                $displayIconProperty = $entry.PSObject.Properties['DisplayIcon']
                $uninstallStringProperty = $entry.PSObject.Properties['UninstallString']
                [pscustomobject]@{
                    RegistryPath = $key.PSPath
                    ProductCode = $key.PSChildName.ToUpperInvariant()
                    DisplayVersion = if ($null -ne $displayVersionProperty) { [string]$displayVersionProperty.Value } else { '' }
                    InstallLocation = if ($null -ne $installLocationProperty) { [string]$installLocationProperty.Value } else { '' }
                    DisplayIcon = if ($null -ne $displayIconProperty) { [string]$displayIconProperty.Value } else { '' }
                    UninstallString = if ($null -ne $uninstallStringProperty) { [string]$uninstallStringProperty.Value } else { '' }
                }
            }
        }
    }
}

function Resolve-BldtExecutable {
    param([Parameter(Mandatory)][object]$Entry)

    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($Entry.InstallLocation) {
        $candidates.Add((Join-Path $Entry.InstallLocation 'BatteryLifeDiagnosticTool.exe'))
    }
    foreach ($registryPath in @(
        'HKLM:\SOFTWARE\Intel\Battery Life Diagnostic Tool',
        'HKLM:\SOFTWARE\WOW6432Node\Intel\Battery Life Diagnostic Tool'
    )) {
        if (Test-Path -LiteralPath $registryPath) {
            $registration = Get-ItemProperty -LiteralPath $registryPath
            $pathProperty = $registration.PSObject.Properties['Path']
            if ($null -ne $pathProperty -and $pathProperty.Value) {
                $candidates.Add((Join-Path ([string]$pathProperty.Value) 'BatteryLifeDiagnosticTool.exe'))
            }
        }
    }
    if ($Entry.DisplayIcon) {
        $displayIcon = $Entry.DisplayIcon.Trim()
        if ($displayIcon.StartsWith('"')) {
            $endQuote = $displayIcon.IndexOf('"', 1)
            if ($endQuote -gt 1) {
                $displayIcon = $displayIcon.Substring(1, $endQuote - 1)
            }
        } else {
            $displayIcon = $displayIcon -replace ',\s*-?\d+\s*$', ''
        }
        if ($displayIcon.EndsWith('.exe', [StringComparison]::OrdinalIgnoreCase)) {
            $candidates.Add($displayIcon)
            $candidates.Add((Join-Path (Split-Path -Parent $displayIcon) 'BatteryLifeDiagnosticTool.exe'))
        }
    }

    if ($Entry.ProductCode -match '^\{[0-9A-F-]{36}\}$') {
        $installer = $null
        try {
            $installer = New-Object -ComObject WindowsInstaller.Installer
            $installLocation = [string]$installer.ProductInfo($Entry.ProductCode, 'InstallLocation')
            if ($installLocation) {
                $candidates.Add((Join-Path $installLocation 'BatteryLifeDiagnosticTool.exe'))
            }
        } catch {
            # Some WiX packages do not populate ProductInfo InstallLocation.
        } finally {
            if ($null -ne $installer) {
                [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($installer)
            }
        }
    }

    foreach ($candidate in $candidates | Select-Object -Unique) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Test-BldtAiArtifacts {
    $analyzerRoot = Join-Path $env:LOCALAPPDATA 'Intel\BLDT-Analyzer'
    $modelsRoot = Join-Path $env:ProgramData 'BLDT-Analyzer\models'
    $analyzerExe = Join-Path $analyzerRoot 'BLDT-Analyzer.exe'
    $versionMarker = Get-ChildItem -LiteralPath $analyzerRoot -Filter '.version_*' -File -ErrorAction SilentlyContinue |
        Select-Object -First 1
    $modelsConfig = Join-Path $modelsRoot 'config.json'
    $embeddingModel = Join-Path $modelsRoot 'OpenVINO\Qwen3-Embedding-0.6B-int8-ov'
    $languageModel = Join-Path $modelsRoot 'OpenVINO\Qwen3-1.7B-int8-ov'

    return [pscustomobject]@{
        Valid = (
            (Test-Path -LiteralPath $analyzerExe -PathType Leaf) -and
            ($null -ne $versionMarker) -and
            (Test-Path -LiteralPath $modelsConfig -PathType Leaf) -and
            (Test-Path -LiteralPath $embeddingModel -PathType Container) -and
            (Test-Path -LiteralPath $languageModel -PathType Container)
        )
        AnalyzerRoot = $analyzerRoot
        AnalyzerExe = $analyzerExe
        VersionMarker = if ($null -ne $versionMarker) { $versionMarker.FullName } else { $null }
        ModelsRoot = $modelsRoot
        ModelsConfig = $modelsConfig
    }
}

function Get-BldtInstallation {
    param([bool]$RequireAi = $false)

    $entries = @(Get-BldtUninstallEntries)
    if ($entries.Count -eq 0) {
        return [pscustomobject]@{
            Registered = $false
            Valid = $false
            MeetsRequest = $false
            Edition = 'missing'
            Version = $null
            ProductCode = $null
            Executable = $null
            InstallRoot = $null
            AiArtifactsValid = $false
            Evidence = 'No BLDT uninstall registration was found in either registry view.'
        }
    }

    $bestCandidate = $null
    foreach ($entry in $entries) {
        $executable = Resolve-BldtExecutable -Entry $entry
        $version = $entry.DisplayVersion
        if ($executable) {
            $fileVersion = (Get-Item -LiteralPath $executable).VersionInfo.ProductVersion
            if ($fileVersion) {
                $version = $fileVersion
            }
        }

        $isAi = (
            $entry.ProductCode -eq $script:BldtAiProductCode -or
            $version -eq '3.1.1.26073107'
        )
        $aiArtifacts = Test-BldtAiArtifacts
        $versionCompatible = $version -and $version.StartsWith($script:BldtVersionPrefix)
        $valid = [bool]($executable -and $versionCompatible)
        $meetsRequest = [bool]($valid -and (-not $RequireAi -or ($isAi -and $aiArtifacts.Valid)))
        $installRoot = if ($executable) { Split-Path -Parent $executable } else { $entry.InstallLocation }

        $candidate = [pscustomobject]@{
            Registered = $true
            Valid = $valid
            MeetsRequest = $meetsRequest
            Edition = if ($isAi) { 'ai' } else { 'standard' }
            Version = $version
            ProductCode = $entry.ProductCode
            Executable = $executable
            InstallRoot = $installRoot
            AiArtifactsValid = [bool]$aiArtifacts.Valid
            AiAnalyzerRoot = $aiArtifacts.AnalyzerRoot
            AiModelsRoot = $aiArtifacts.ModelsRoot
            Evidence = "Registry=$($entry.RegistryPath); DisplayVersion=$($entry.DisplayVersion); Executable=$executable"
        }
        if ($meetsRequest) {
            return $candidate
        }
        if ($null -eq $bestCandidate -or ($candidate.Valid -and -not $bestCandidate.Valid)) {
            $bestCandidate = $candidate
        }
    }
    return $bestCandidate
}

function Assert-BldtInstallation {
    param([bool]$RequireAi = $false)

    $installation = Get-BldtInstallation -RequireAi:$RequireAi
    "BLDT discovery: $($installation.Evidence)" | log
    "BLDT resolved state: edition=$($installation.Edition), version=$($installation.Version), executable=$($installation.Executable)" |
        log
    if ($installation.Edition -eq 'ai') {
        "BLDT AI artifacts: valid=$($installation.AiArtifactsValid), analyzer=$($installation.AiAnalyzerRoot), models=$($installation.AiModelsRoot)" |
            log
    }
    if (-not $installation.MeetsRequest) {
        $requested = if ($RequireAi) { 'AI' } else { 'standard or AI' }
        throw "BLDT installation does not satisfy the requested $requested v3.1.1 state. Discovered edition=$($installation.Edition), version=$($installation.Version), executable=$($installation.Executable), AI artifacts=$($installation.AiArtifactsValid)."
    }
    return $installation
}

function Invoke-BldtDownload {
    param(
        [Parameter(Mandatory)][uri]$Uri,
        [Parameter(Mandatory)][string]$Destination,
        [Parameter(Mandatory)][ValidatePattern('^[0-9A-Fa-f]{64}$')][string]$Sha256
    )

    if ($Uri.Scheme -ne 'https') {
        throw 'BLDT downloads require HTTPS.'
    }
    if (Test-Path -LiteralPath $Destination -PathType Leaf) {
        $existingHash = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash
        if ($existingHash -eq $Sha256) {
            "Reusing verified BLDT package: $Destination" | log
            return
        }
        Remove-Item -LiteralPath $Destination -Force
    }

    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $partial = "$Destination.partial"
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            if (Test-Path -LiteralPath $partial) {
                Remove-Item -LiteralPath $partial -Force
            }
            "Downloading BLDT package (attempt $attempt of 3): $Uri" | log
            Invoke-WebRequest -Uri $Uri -OutFile $partial -UseBasicParsing
            if (-not (Test-Path -LiteralPath $partial -PathType Leaf) -or (Get-Item -LiteralPath $partial).Length -eq 0) {
                throw 'Downloaded BLDT package is empty.'
            }
            $actualHash = (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash
            if ($actualHash -ne $Sha256) {
                throw "BLDT ZIP checksum mismatch. Expected $Sha256, got $actualHash."
            }
            Move-Item -LiteralPath $partial -Destination $Destination -Force
            return
        } catch {
            " ERROR - BLDT package download failed: $($_.Exception.Message)" | log
            if ($attempt -eq 3) {
                throw
            }
            Start-Sleep -Seconds (10 * $attempt)
        }
    }
}

function Get-BldtMsiProperties {
    param([Parameter(Mandatory)][string]$Path)

    $installer = $null
    $database = $null
    $view = $null
    try {
        $installer = New-Object -ComObject WindowsInstaller.Installer
        $database = $installer.OpenDatabase($Path, 0)
        $view = $database.OpenView('SELECT `Property`, `Value` FROM `Property`')
        [void]$view.Execute()
        $properties = @{}
        while ($null -ne ($row = $view.Fetch())) {
            $properties[$row.StringData(1)] = $row.StringData(2)
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($row)
        }
        return $properties
    } finally {
        if ($null -ne $view) {
            [void]$view.Close()
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($view)
        }
        if ($null -ne $database) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($database)
        }
        if ($null -ne $installer) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($installer)
        }
    }
}

function Assert-BldtMsi {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][object]$Package
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "BLDT MSI not found: $Path"
    }
    $actualHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    if ($actualHash -ne $Package.MsiSha256) {
        throw "BLDT MSI checksum mismatch. Expected $($Package.MsiSha256), got $actualHash."
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    $signerSubject = if ($null -ne $signature.SignerCertificate) { $signature.SignerCertificate.Subject } else { '<none>' }
    if ($signature.Status -ne 'Valid' -or $signerSubject -notmatch '(^|,\s*)O=Intel Corporation(,|$)') {
        throw "BLDT MSI signature validation failed. Status=$($signature.Status), signer=$signerSubject"
    }
    $properties = Get-BldtMsiProperties -Path $Path
    if (
        $properties.ProductName -ne $script:BldtProductName -or
        $properties.ProductVersion -ne $Package.ProductVersion -or
        $properties.ProductCode.ToUpperInvariant() -ne $Package.ProductCode -or
        $properties.UpgradeCode.ToUpperInvariant() -ne $script:BldtUpgradeCode
    ) {
        throw "Unexpected BLDT MSI identity: name='$($properties.ProductName)', version='$($properties.ProductVersion)', product='$($properties.ProductCode)', upgrade='$($properties.UpgradeCode)'."
    }
}

function Assert-BldtMsiInstallResult {
    param(
        [int]$ExitCode,
        [Parameter(Mandatory)][string]$InstallLog
    )

    if ($ExitCode -in (1641, 3010)) {
        throw "BLDT MSI requires a reboot (exit $ExitCode). Reboot the DUT and rerun prep. See $InstallLog"
    }
    if ($ExitCode -ne 0) {
        throw "BLDT MSI failed with exit code $ExitCode. See $InstallLog"
    }
}

function Install-BldtMsi {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][object]$Package,
        [Parameter(Mandatory)][string]$InstallLog
    )

    Assert-BldtMsi -Path $Path -Package $Package
    if (-not (Test-BldtElevated)) {
        throw 'BLDT installation requires the elevated HOBL DUT execution context. Interactive elevation will not be attempted.'
    }
    foreach ($value in @($Path, $InstallLog)) {
        if ($value -match '["\r\n]') {
            throw 'Invalid quote or newline in BLDT MSI path.'
        }
    }
    $installer = $null
    try {
        $installer = New-Object -ComObject WindowsInstaller.Installer
        $isInstalled = $installer.ProductState($Package.ProductCode) -ge 3
    } finally {
        if ($null -ne $installer) {
            [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($installer)
        }
    }
    $mode = if ($isInstalled) { '/fvamus' } else { '/i' }
    $arguments = "$mode `"$Path`" /qn /norestart REBOOT=ReallySuppress WIXUI_EXITDIALOGOPTIONALCHECKBOX=0 /L*v `"$InstallLog`""
    "Installing verified BLDT $($Package.Edition) MSI; log=$InstallLog" | log
    $process = Start-Process -FilePath "$env:SystemRoot\System32\msiexec.exe" -ArgumentList $arguments -Wait -PassThru
    Assert-BldtMsiInstallResult -ExitCode $process.ExitCode -InstallLog $InstallLog
}
