# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$downloadUrl = "https://github.com/microsoft/HOBL/archive/refs/heads/main.zip"
$zipPath = Join-Path $env:TEMP "hobl-main.zip"
$targetPath = "C:\hobl"
$extractedPath = "C:\hobl-main"

try {
    Write-Host "Removing $targetPath"
    if (Test-Path -LiteralPath $targetPath) {
        Remove-Item -LiteralPath $targetPath -Recurse -Force
    }

    Write-Host "Checking if $extractedPath exists"
    if (Test-Path -LiteralPath $extractedPath) {
        Remove-Item -LiteralPath $extractedPath -Recurse -Force
    }

    Write-Host "Downloading $downloadUrl"
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath

    Write-Host "Extracting $zipPath to C:\"
    Expand-Archive -LiteralPath $zipPath -DestinationPath "C:\" -Force

    Write-Host "Renaming $extractedPath to $targetPath"
    if (-not (Test-Path -LiteralPath $extractedPath -PathType Container)) {
        throw "The downloaded archive did not contain the expected hobl-main folder."
    }
    Rename-Item -LiteralPath $extractedPath -NewName "hobl"
    Write-Host "HOBL installed at $targetPath"
}
catch {
    Write-Host " ERROR - Failed to install HOBL: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host -Prompt "-- Press Enter to exit"
    exit 1
}
finally {
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
}
