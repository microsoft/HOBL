# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

function Get-LlvmCompilerInfo {
    param(
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$ExpectedVersion
    )

    $architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
    $machines = @{ x64 = 0x8664; arm64 = 0xAA64 }
    if (-not $machines.ContainsKey($architecture)) { throw "Unsupported compiler architecture: $architecture" }
    $hashes = @{}
    foreach ($name in @('clang.exe', 'clang-cl.exe')) {
        $path = Join-Path $InstallDir "bin\$name"
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing LLVM compiler: $path. Re-prep required." }
        # Verify the payload, not the MSI filename/container architecture, before
        # executing it. An x64 MSI can contain an ARM64 compiler.
        $stream = [System.IO.File]::OpenRead($path)
        $reader = [System.IO.BinaryReader]::new($stream)
        try {
            if ($reader.ReadUInt16() -ne 0x5A4D) { throw "Invalid PE header: $path" }
            $stream.Position = 0x3C
            $offset = $reader.ReadInt32()
            if ($offset -lt 0 -or $offset -gt $stream.Length - 6) { throw "Invalid PE offset: $path" }
            $stream.Position = $offset
            if ($reader.ReadUInt32() -ne 0x00004550 -or $reader.ReadUInt16() -ne $machines[$architecture]) {
                throw "LLVM compiler is not native $architecture : $path. Re-prep with the correct installer."
            }
        } finally {
            $reader.Dispose()
        }
        $output = & $path --version 2>&1
        $exitCode = $LASTEXITCODE
        $versionMatch = [regex]::Match(($output -join "`n"), 'clang version (\d+\.\d+\.\d+)')
        if ($exitCode -ne 0 -or -not $versionMatch.Success -or $versionMatch.Groups[1].Value -ne $ExpectedVersion) {
            throw "LLVM compiler version mismatch at $path. Expected $ExpectedVersion. Re-prep required."
        }
        $hashes[$name] = (Get-FileHash -LiteralPath $path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    }
    return [pscustomobject]@{
        Version = $ExpectedVersion
        Architecture = $architecture
        Clang = (Join-Path $InstallDir 'bin\clang.exe')
        ClangCl = (Join-Path $InstallDir 'bin\clang-cl.exe')
        ClangSha256 = $hashes['clang.exe']
        ClangClSha256 = $hashes['clang-cl.exe']
    }
}

function Assert-LlvmMsi {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$Sha256,
        [Parameter(Mandatory)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version,
        [switch]$AllowUnsigned
    )

    if ([System.IO.Path]::GetExtension($Path) -ne '.msi' -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "LLVM MSI not found: $Path"
    }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash -ne $Sha256) {
        throw 'LLVM MSI checksum mismatch. Installation refused.'
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $Path -ErrorAction Stop
    if ($signature.Status -eq 'NotSigned' -and $AllowUnsigned) {
        'Using explicitly approved unsigned LLVM MSI; SHA-256 matched. Windows policies remain enforced.' | log
    } elseif ($signature.Status -ne 'Valid') {
        throw "LLVM MSI signature status: $($signature.Status). A NotSigned package requires explicit allow_unsigned_installer=1 and an approved hash; invalid signatures are never accepted."
    }

    # Read the MSI database only; do not execute package custom actions here.
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
            [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($row)
        }
        [void]$view.Close()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($view)
        $view = $null
        if ($properties.ProductName -ne 'LLVM' -or $properties.ProductVersion -ne $Version) {
            throw "Expected LLVM MSI version $Version, got '$($properties.ProductName)' '$($properties.ProductVersion)'."
        }
        if ($properties.ProductCode -notmatch '^\{[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}$') {
            throw 'LLVM MSI is missing a valid ProductCode.'
        }
        $view = $database.OpenView('SELECT `Directory` FROM `Directory`')
        [void]$view.Execute()
        $hasInstallRoot = $false
        while ($null -ne ($row = $view.Fetch())) {
            if ($row.StringData(1) -eq 'INSTALL_ROOT') { $hasInstallRoot = $true }
            [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($row)
        }
        if (-not $hasInstallRoot) { throw 'LLVM MSI does not expose the supported INSTALL_ROOT directory property.' }
        return [pscustomobject]@{
            ProductCode = $properties.ProductCode
            IsInstalled = ($installer.ProductState($properties.ProductCode) -ge 3)
        }
    } finally {
        if ($null -ne $view) { [void]$view.Close(); [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($view) }
        if ($null -ne $database) { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($database) }
        if ($null -ne $installer) { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($installer) }
    }
}

function Install-LlvmMsi {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Sha256,
        [Parameter(Mandatory)][string]$Version,
        [Parameter(Mandatory)][string]$InstallDir,
        [Parameter(Mandatory)][string]$InstallLog,
        [switch]$AllowUnsigned
    )

    $package = Assert-LlvmMsi -Path $Path -Sha256 $Sha256 -Version $Version -AllowUnsigned:$AllowUnsigned
    if (-not (Test-LlvmElevated)) {
        throw 'LLVM MSI requires the elevated HOBL DUT execution context. No interactive elevation will be attempted.'
    }
    foreach ($value in @($Path, $InstallDir, $InstallLog)) {
        if ($value -match '["\r\n]') { throw 'Invalid quote or newline in MSI path.' }
    }
    # Reinstall all files and recache this exact package if its ProductCode is
    # already installed, including same-version compiler builds with new hashes.
    $mode = if ($package.IsInstalled) { '/fvamus' } else { '/i' }
    $arguments = "$mode `"$Path`" /qn /norestart REBOOT=ReallySuppress INSTALL_ROOT=`"$InstallDir`" /L*v `"$InstallLog`""
    "Installing approved LLVM MSI; installer log: $InstallLog" | log
    $process = Start-Process -FilePath "$env:SystemRoot\System32\msiexec.exe" -ArgumentList $arguments -Wait -PassThru -ErrorAction Stop
    Assert-LlvmMsiInstallResult -ExitCode $process.ExitCode -InstallLog $InstallLog
}

function Test-LlvmElevated {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    try {
        $principal = [Security.Principal.WindowsPrincipal]::new($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } finally {
        $identity.Dispose()
    }
}

function Assert-LlvmMsiInstallResult {
    param([int]$ExitCode, [string]$InstallLog)
    if ($ExitCode -eq 3010 -or $ExitCode -eq 1641) {
        throw "LLVM MSI requires a reboot (exit $ExitCode). Reboot the DUT and rerun prep; no prep-success marker will be written. See $InstallLog"
    }
    if ($ExitCode -ne 0) {
        throw "LLVM MSI failed (exit $ExitCode). See $InstallLog. Resolve installer/security policy errors; no policy bypass is attempted."
    }
}

function Assert-LlvmMsiReceipt {
    param([string]$Path, [string]$Sha256, [object]$Compiler)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw 'LLVM MSI receipt missing. Re-prep required.' }
    $receipt = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    if ($receipt.InstallerSha256 -ne $Sha256 -or $receipt.Version -ne $Compiler.Version -or
        $receipt.ClangSha256 -ne $Compiler.ClangSha256 -or $receipt.ClangClSha256 -ne $Compiler.ClangClSha256) {
        throw 'LLVM compiler no longer matches the selected MSI receipt. Re-prep required.'
    }
}