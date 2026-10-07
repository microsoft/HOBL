# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# No installers, RPC, elevation or real compiler binaries are executed.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '..\llvm_resources\llvm_toolchain.ps1')
function log {
    [CmdletBinding()] param([Parameter(ValueFromPipeline)]$msg)
    process { Write-Host $msg }
}
function Assert-Throws {
    param([scriptblock]$Action, [string]$Pattern)
    $message = ''
    try { & $Action | Out-Null } catch { $message = $_.Exception.Message }
    if ($message -notmatch $Pattern) { throw "Expected '$Pattern', got '$message'" }
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ('hobl-llvm-guards-' + [guid]::NewGuid())
try {
    [void](New-Item -ItemType Directory -Path (Join-Path $root 'bin') -Force)
    $msi = Join-Path $root 'fake.msi'
    [System.IO.File]::WriteAllText($msi, 'not an installer')
    Assert-Throws { Assert-LlvmMsi -Path $msi -Sha256 ('0' * 64) -Version '24.0.0' } 'checksum mismatch'
    Write-Host 'PASS: bad MSI hash rejected before signature/database/install'

    & {
        function Get-FileHash { param($LiteralPath, $Algorithm, $ErrorAction) @{ Hash = ('a' * 64) } }
        function Get-AuthenticodeSignature { param($LiteralPath, $ErrorAction) @{ Status = 'HashMismatch' } }
        Assert-Throws { Assert-LlvmMsi -Path $msi -Sha256 ('a' * 64) -Version '24.0.0' -AllowUnsigned } 'signature status: HashMismatch'
    }
    Write-Host 'PASS: unsigned opt-in cannot accept an invalid signature'

    Assert-LlvmMsiInstallResult -ExitCode 0 -InstallLog 'mock.log'
    foreach ($code in @(3010, 1641)) {
        Assert-Throws { Assert-LlvmMsiInstallResult -ExitCode $code -InstallLog 'mock.log' } 'requires a reboot'
    }
    foreach ($code in @(1603, 1618, 1625)) {
        Assert-Throws { Assert-LlvmMsiInstallResult -ExitCode $code -InstallLog 'mock.log' } 'MSI failed'
    }
    Write-Host 'PASS: MSI success/reboot/failure exit-code handling'

    & {
        function Assert-LlvmMsi { [pscustomobject]@{ IsInstalled = $script:installed } }
        function Test-LlvmElevated { $script:elevated }
        function Start-Process {
            param($FilePath, $ArgumentList, [switch]$Wait, [switch]$PassThru, $ErrorAction)
            $script:captured = @{ FilePath = $FilePath; Arguments = $ArgumentList; Wait = $Wait; PassThru = $PassThru }
            [pscustomobject]@{ ExitCode = 0 }
        }
        $script:elevated = $true
        $installParameters = @{ Path = (Join-Path $root "approved compiler's build.msi"); Sha256 = ('a' * 64);
            Version = '24.0.0'; InstallDir = (Join-Path $root 'LLVM'); InstallLog = (Join-Path $root 'install.log') }
        foreach ($installed in @($false, $true)) {
            $script:installed = $installed
            Install-LlvmMsi @installParameters
            $mode = if ($installed) { '/fvamus' } else { '/i' }
            if ($script:captured.Arguments -cne "$mode `"$($installParameters.Path)`" /qn /norestart REBOOT=ReallySuppress INSTALL_ROOT=`"$($installParameters.InstallDir)`" /L*v `"$($installParameters.InstallLog)`"") {
                throw "Unexpected msiexec arguments: $($script:captured.Arguments)"
            }
            if ($script:captured.FilePath -ne "$env:SystemRoot\System32\msiexec.exe" -or
                -not $script:captured.Wait -or -not $script:captured.PassThru) { throw 'Unexpected installer invocation' }
        }
        $script:captured = $null
        $script:elevated = $false
        Assert-Throws { Install-LlvmMsi @installParameters } 'elevated HOBL'
        if ($script:captured) { throw 'Installer started without elevation' }
        $script:elevated = $true
        $installParameters.Path += '"'
        Assert-Throws { Install-LlvmMsi @installParameters } 'Invalid quote or newline'
        if ($script:captured) { throw 'Installer started with an invalid path' }
    }
    Write-Host 'PASS: mocked first install/repair, quoting and elevation refusal'

    # Deliberately x86 fake header, which neither supported native OS can use.
    # Validation must reject it before any executable invocation occurs.
    $bytes = [byte[]]::new(128)
    $bytes[0] = 0x4D; $bytes[1] = 0x5A; $bytes[0x3C] = 0x40
    $bytes[0x40] = 0x50; $bytes[0x41] = 0x45
    $bytes[0x44] = 0x4C; $bytes[0x45] = 0x01
    [System.IO.File]::WriteAllBytes((Join-Path $root 'bin\clang.exe'), $bytes)
    Assert-Throws { Get-LlvmCompilerInfo -InstallDir $root -ExpectedVersion '24.0.0' } 'not native'
    Write-Host 'PASS: wrong PE architecture rejected before compiler execution'

    $compiler = [pscustomobject]@{ Version = '24.0.0'; ClangSha256 = 'clang'; ClangClSha256 = 'clang-cl' }
    $receipt = Join-Path $root 'receipt.json'
    Assert-Throws { Assert-LlvmMsiReceipt -Path $receipt -Sha256 'approved' -Compiler $compiler } 'receipt missing'
    @{ InstallerSha256 = 'approved'; Version = '24.0.0'; ClangSha256 = 'clang'; ClangClSha256 = 'clang-cl' } |
        ConvertTo-Json | Set-Content -LiteralPath $receipt
    Assert-LlvmMsiReceipt -Path $receipt -Sha256 'approved' -Compiler $compiler
    Assert-Throws { Assert-LlvmMsiReceipt -Path $receipt -Sha256 'different' -Compiler $compiler } 'no longer matches'
    $compiler.ClangSha256 = 'changed'
    Assert-Throws { Assert-LlvmMsiReceipt -Path $receipt -Sha256 'approved' -Compiler $compiler } 'no longer matches'
    Write-Host 'PASS: missing/stale/replaced compiler receipt guards'
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}