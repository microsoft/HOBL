# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

<#
.SYNOPSIS
Creates three large files and one ZIP containing all three files.
.DESCRIPTION
Creates temp_0.bin through temp_2.bin, each containing 1.5 GiB of random data by
default, pacing incremental writes over approximately 420 seconds per file.
Slower storage can take longer. This does not throttle network transfers.
Then creates large_files.zip containing all three without throttling compression.
Originals are retained. Random data keeps the ZIP close to the total input size.
Existing destination files or archives cause an error; nothing is overwritten.
When ProcessStateFile is supplied, records this process's PID and creation time
for targeted cleanup without searching other processes.
.EXAMPLE
.\create_large_files.ps1
.EXAMPLE
.\create_large_files.ps1 -OutputDirectory .\testdata -FileSizeBytes 2097169 -FileCreationSeconds 2
#>
[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\enterprise_collab\resources\large"),

    [string]$ProcessStateFile = "",

    [ValidateRange(1, [long]::MaxValue)]
    [long]$FileSizeBytes = 1610612736,

    [ValidateRange(1, [int]::MaxValue)]
    [int]$FileCreationSeconds = 420
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$directory = New-Item -ItemType Directory -Path $OutputDirectory -Force
$outputPath = $directory.FullName
Write-Host "Output directory: $outputPath"

$files = 0..2 | ForEach-Object { Join-Path $outputPath "temp_$_.bin" }
$archivePath = Join-Path $outputPath "large_files.zip"

foreach ($path in @($files) + @($archivePath)) {
    if (Test-Path -LiteralPath $path) {
        throw " ERROR - Destination already exists: $path. Choose another output directory or move the existing files."
    }
}

if ($ProcessStateFile) {
    $process = Get-Process -Id $PID -ErrorAction Stop
    @{ pid = $PID; started_ticks = $process.StartTime.ToUniversalTime().Ticks.ToString() } |
        ConvertTo-Json -Compress | Set-Content -LiteralPath $ProcessStateFile -Encoding UTF8
}

$buffer = New-Object byte[] (1MB)
foreach ($file in $files) {
    Write-Host "Creating $file ($FileSizeBytes bytes over approximately $FileCreationSeconds seconds)"
    $stream = [System.IO.File]::Open(
        $file,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::Read
    )
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $random = $null
    try {
        $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        [long]$bytesWritten = 0
        while ($bytesWritten -lt $FileSizeBytes) {
            $chunkSize = [int][Math]::Min($buffer.Length, $FileSizeBytes - $bytesWritten)
            $random.GetBytes($buffer)
            $targetMilliseconds = (($bytesWritten + $chunkSize) / [double]$FileSizeBytes) * $FileCreationSeconds * 1000
            # Use cumulative deadlines so write and sleep overhead do not accumulate.
            while (($remainingMilliseconds = $targetMilliseconds - $timer.Elapsed.TotalMilliseconds) -gt 0) {
                Start-Sleep -Milliseconds ([int][Math]::Min(1000, [Math]::Ceiling($remainingMilliseconds)))
            }
            $stream.Write($buffer, 0, $chunkSize)
            $stream.Flush()
            $bytesWritten += $chunkSize
        }
    }
    finally {
        $stream.Dispose()
        if ($null -ne $random) {
            $random.Dispose()
        }
        $timer.Stop()
    }
    Write-Host "Created $file in $([Math]::Round($timer.Elapsed.TotalSeconds, 2)) seconds."
}

Write-Host "Creating $archivePath"
$archive = [System.IO.Compression.ZipFile]::Open(
    $archivePath,
    [System.IO.Compression.ZipArchiveMode]::Create
)
try {
    foreach ($file in $files) {
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive,
            $file,
            [System.IO.Path]::GetFileName($file),
            [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
    }
}
finally {
    $archive.Dispose()
}

Write-Host "Created three files and one combined ZIP in $outputPath"
