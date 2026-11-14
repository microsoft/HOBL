# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [Parameter(Mandatory)][ValidateSet("Pdf", "Workbook", "Presentation")][string]$Kind,
    [Parameter(Mandatory)][string]$Path,
    [string]$Before = ""
)

$ErrorActionPreference = "Stop"
if ($Kind -eq "Pdf") {
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    do {
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            $stream = $null
            try {
                $stream = [IO.File]::OpenRead($Path)
                $header = New-Object byte[] 5
                $validHeader = $stream.Read($header, 0, 5) -eq 5 -and
                    [Text.Encoding]::ASCII.GetString($header) -eq "%PDF-"
                $tailSize = [int][Math]::Min(2048, $stream.Length)
                $null = $stream.Seek(-$tailSize, [IO.SeekOrigin]::End)
                $tail = New-Object byte[] $tailSize
                $null = $stream.Read($tail, 0, $tailSize)
                if ($validHeader -and [Text.Encoding]::ASCII.GetString($tail).Contains("%%EOF")) {
                    @{ verified = $true } | ConvertTo-Json -Compress
                    return
                }
            } catch [IO.IOException] {
                Write-Verbose "PDF is still being written: $Path"
            } finally {
                if ($stream) { $stream.Dispose() }
            }
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    throw " ERROR - Complete PDF output was not published within 60 seconds: $Path"
}

if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    throw " ERROR - Office output not found: $Path"
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($Path)
function Read-XmlEntry([string]$Name) {
    $entry = $zip.GetEntry($Name)
    if (-not $entry) { throw " ERROR - Missing Office package entry: $Name" }
    $reader = [IO.StreamReader]::new($entry.Open())
    try { return [xml]$reader.ReadToEnd() } finally { $reader.Dispose() }
}

try {
    $baseline = if ($Before) { $Before | ConvertFrom-Json } else { $null }
    if ($Kind -eq "Workbook") {
        $pivots = @($zip.Entries | Where-Object { $_.FullName -match '^xl/pivotTables/pivotTable\d+\.xml$' })
        $book = Read-XmlEntry "xl/workbook.xml"
        $sheet = $book.SelectSingleNode("//*[local-name()='sheet'][@name='Additional Data']")
        if (-not $sheet) { throw " ERROR - Additional Data worksheet is missing" }
        $rels = Read-XmlEntry "xl/_rels/workbook.xml.rels"
        $id = $sheet.GetAttribute("id", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
        $target = $rels.SelectSingleNode("//*[local-name()='Relationship'][@Id='$id']").Target
        $sheetPath = if ($target.StartsWith("/")) { $target.TrimStart("/") } else { "xl/$target" }
        $data = Read-XmlEntry $sheetPath
        $strings = Read-XmlEntry "xl/sharedStrings.xml"
        $shared = @($strings.SelectNodes("//*[local-name()='si']"))
        $categories = @()
        $costs = @()
        foreach ($row in $data.SelectNodes("//*[local-name()='row']")) {
            $number = [int]$row.r
            if ($number -lt 3 -or $number -gt 14) { continue }
            $cell = $row.SelectSingleNode("*[local-name()='c'][@r='B$number']")
            $cost = $row.SelectSingleNode("*[local-name()='c'][@r='C$number']")
            if (-not $cell -or -not $cost) { throw " ERROR - Missing source data in row $number" }
            $categories += if ($cell.t -eq "s") { $shared[[int]$cell.v].InnerText } else { $cell.InnerText }
            $costs += [double]::Parse($cost.v, [Globalization.CultureInfo]::InvariantCulture)
        }
        if ($categories.Count -ne 12) { throw " ERROR - Expected 12 budget source rows" }
        $pivotNames = @()
        $populated = $false
        foreach ($pivot in $pivots) {
            $definition = Read-XmlEntry $pivot.FullName
            $pivotNames += $definition.DocumentElement.name
            if ($baseline -and $definition.DocumentElement.name -notin $baseline.names -and
                $definition.SelectSingleNode("//*[local-name()='dataField'][@name='Sum of Cost'][@subtotal='sum'][@fld='1']") -and
                $definition.SelectSingleNode("//*[local-name()='rowField'][@x='0']")) {
                $cacheId = $definition.DocumentElement.cacheId
                $cache = $book.SelectSingleNode("//*[local-name()='pivotCache'][@cacheId='$cacheId']")
                $cacheRelId = $cache.GetAttribute("id", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
                $cacheTarget = $rels.SelectSingleNode("//*[local-name()='Relationship'][@Id='$cacheRelId']").Target
                $cachePath = if ($cacheTarget.StartsWith("/")) { $cacheTarget.TrimStart("/") } else { "xl/$cacheTarget" }
                $cacheXml = Read-XmlEntry $cachePath
                if ($cacheXml.SelectSingleNode("//*[local-name()='worksheetSource'][@sheet='Additional Data'][@ref='B2:C14']")) {
                    $populated = $true
                }
            }
        }
        if ($baseline) {
            if ($pivots.Count -le $baseline.pivots) {
                throw " ERROR - No new Excel PivotTable was saved"
            }
            for ($i = 0; $i -lt $categories.Count; $i++) {
                if ($i -gt 0 -and [string]::Compare($categories[$i - 1], $categories[$i], $true) -gt 0) {
                    throw " ERROR - Excel categories were not sorted ascending"
                }
                $index = [Array]::IndexOf($baseline.categories, $categories[$i])
                if ($index -lt 0 -or $costs[$i] -ne $baseline.costs[$index]) {
                    throw " ERROR - Excel sort did not preserve category/cost pairs"
                }
            }
            if (-not $populated) { throw " ERROR - New Excel PivotTable has no category rows and summed Cost from the selected range" }
        }
        @{ pivots = $pivots.Count; names = $pivotNames; categories = $categories; costs = $costs } | ConvertTo-Json -Compress
    } else {
        $pictures = 0
        $videos = 0
        foreach ($entry in $zip.Entries | Where-Object { $_.FullName -match '^ppt/slides/slide\d+\.xml$' }) {
            $slide = Read-XmlEntry $entry.FullName
            $pictures += $slide.SelectNodes("//*[local-name()='pic'][not(.//*[local-name()='videoFile'])]").Count
            $videos += $slide.SelectNodes("//*[local-name()='videoFile']").Count
        }
        if ($baseline -and ($pictures -le $baseline.pictures -or $videos -le $baseline.videos)) {
            throw " ERROR - PowerPoint did not save both a new picture and a new video"
        }
        @{ pictures = $pictures; videos = $videos } | ConvertTo-Json -Compress
    }
} finally {
    $zip.Dispose()
}
