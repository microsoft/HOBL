# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$downloadUrl = "https://github.com/microsoft/HOBL/archive/refs/heads/main.zip"
$zipPath = Join-Path $env:TEMP "hobl-main.zip"
$targetPath = "C:\hobl"
$extractedPath = "C:\hobl-main"

try {
    # Remove any existing hobl folder
    Write-Host "Removing $targetPath"
    if (Test-Path -LiteralPath $targetPath) {
        Remove-Item -LiteralPath $targetPath -Recurse -Force
    }

    # Remove any existing extracted archive
    Write-Host "Checking if $extractedPath exists"
    if (Test-Path -LiteralPath $extractedPath) {
        Remove-Item -LiteralPath $extractedPath -Recurse -Force
    }

    # Download latest hobl zip from GitHub
    Write-Host "Downloading $downloadUrl"
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath

    # Extract the zip
    Write-Host "Extracting $zipPath to C:\"
    Expand-Archive -LiteralPath $zipPath -DestinationPath "C:\" -Force

    # Wait a second for lock to clear (sometimes the extraction can take a moment to release the file lock)
    Start-Sleep -Seconds 1

    # Rename the extracted folder to hobl
    Write-Host "Renaming $extractedPath to $targetPath"
    if (-not (Test-Path -LiteralPath $extractedPath -PathType Container)) {
        throw "The downloaded archive did not contain the expected hobl-main folder."
    }
    Rename-Item -LiteralPath $extractedPath -NewName "hobl"

    # Set date and time as the version
    (Get-Date).ToString("yyyy-MM-dd HH:mm") | Set-Content -LiteralPath (Join-Path $targetPath "hobl_version.txt")

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
