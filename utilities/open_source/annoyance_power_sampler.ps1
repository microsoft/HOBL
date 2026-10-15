param(
    [Parameter(Mandatory = $true)][string]$OutFile,
    [Parameter(Mandatory = $true)][string]$StopFile,
    [Parameter(Mandatory = $true)][string]$StartedFile,
    [double]$IntervalSeconds = 1
)

$ErrorActionPreference = 'Continue'
$doneFile = "$OutFile.done"
$nanoJoulesPerMillisecondToMilliWatts = 1000.0

try {
    $allPaths = (Get-Counter -ListSet 'Energy Meter' -ErrorAction Stop).Paths
    $energyPath = $allPaths | Where-Object { $_ -like '*\Energy' } | Select-Object -First 1
    $timePath = $allPaths | Where-Object { $_ -like '*\Time' } | Select-Object -First 1
    $powerPath = $allPaths | Where-Object { $_ -like '*\Power' } | Select-Object -First 1
    if (-not $energyPath -or -not $timePath) {
        throw 'Energy and/or Time counters missing from Energy Meter set'
    }
}
catch {
    "ERROR: Energy Meter counters not available: $($_.Exception.Message)" |
        Out-File -FilePath $doneFile -Encoding ascii
    return
}

function Read-CounterMaps {
    $maps = @{
        Energy = @{}
        Time = @{}
        Power = @{}
        Memory = @{}
    }
    $paths = @($energyPath, $timePath)
    if ($powerPath) {
        $paths += $powerPath
    }
    try {
        $samples = (Get-Counter -Counter $paths -MaxSamples 1 -ErrorAction Stop).CounterSamples
        foreach ($counterSample in $samples) {
            if ($counterSample.Path -like '*\Energy') {
                $maps.Energy[$counterSample.InstanceName] = [double]$counterSample.CookedValue
            }
            elseif ($counterSample.Path -like '*\Time') {
                $maps.Time[$counterSample.InstanceName] = [double]$counterSample.CookedValue
            }
            elseif ($counterSample.Path -like '*\Power') {
                $maps.Power[$counterSample.InstanceName] = [double]$counterSample.CookedValue
            }
        }
    }
    catch { }
    try {
        $operatingSystem = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
        $performanceMemory = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory -ErrorAction Stop
        $maps.Memory['PhysicalMemoryTotalBytes'] = [double]$operatingSystem.TotalVisibleMemorySize * 1024.0
        $maps.Memory['Available Bytes'] = [double]$operatingSystem.FreePhysicalMemory * 1024.0
        $maps.Memory['Committed Bytes'] = [double]$performanceMemory.CommittedBytes
        $maps.Memory['Commit Limit'] = [double]$performanceMemory.CommitLimit
        $maps.Memory['% Committed Bytes In Use'] = [double]$performanceMemory.PercentCommittedBytesInUse
    }
    catch { }
    return $maps
}

$previousMaps = Read-CounterMaps
$previousEnergy = $previousMaps.Energy
$previousTime = $previousMaps.Time
$channels = @()
$headerWritten = $false
$sample = 0
$start = Get-Date
$start.ToUniversalTime().ToString('o') | Out-File -FilePath $StartedFile -Encoding ascii
$emptyCycles = 0
$maxEmptyCycles = 3
$abortReason = ''

while (-not (Test-Path -LiteralPath $StopFile)) {
    $deadline = $start.AddSeconds(($sample + 1) * $IntervalSeconds)
    while ((Get-Date) -lt $deadline -and -not (Test-Path -LiteralPath $StopFile)) {
        Start-Sleep -Milliseconds 100
    }
    if (Test-Path -LiteralPath $StopFile) {
        break
    }

    $sample++
    $now = Get-Date
    $elapsed = [math]::Round(($now - $start).TotalSeconds, 3)
    $timestamp = $now.ToUniversalTime().ToString('o')
    $currentMaps = Read-CounterMaps
    $currentEnergy = $currentMaps.Energy
    $currentTime = $currentMaps.Time
    $currentPower = $currentMaps.Power

    if (-not $headerWritten) {
        $channels = $currentEnergy.Keys | Sort-Object
        $channelColumns = ($channels | ForEach-Object { ($_ -replace ',', ';') + '_mW' }) -join ','
        $memoryColumns = 'PhysicalMemoryUtilizationPercent,PhysicalMemoryUsedBytes,PhysicalMemoryTotalBytes,CommittedBytes,CommitLimitBytes,PercentCommittedBytesInUse,AvailableBytes'
        "Sample,TimestampUtc,Elapsed_s,$memoryColumns,$channelColumns" | Out-File -FilePath $OutFile -Encoding ascii
        $headerWritten = $true
    }

    $memory = $currentMaps.Memory
    $availableBytes = if ($memory.ContainsKey('Available Bytes')) { $memory['Available Bytes'] } else { 0.0 }
    $physicalMemoryTotalBytes = if ($memory.ContainsKey('PhysicalMemoryTotalBytes')) {
        $memory['PhysicalMemoryTotalBytes']
    }
    else { 0.0 }
    $physicalMemoryUsedBytes = [math]::Max(0.0, $physicalMemoryTotalBytes - $availableBytes)
    $physicalMemoryUtilizationPercent = if ($physicalMemoryTotalBytes -gt 0) {
        100.0 * $physicalMemoryUsedBytes / $physicalMemoryTotalBytes
    }
    else { 0.0 }
    $committedBytes = if ($memory.ContainsKey('Committed Bytes')) { $memory['Committed Bytes'] } else { 0.0 }
    $commitLimitBytes = if ($memory.ContainsKey('Commit Limit')) { $memory['Commit Limit'] } else { 0.0 }
    $percentCommittedBytesInUse = if ($memory.ContainsKey('% Committed Bytes In Use')) {
        $memory['% Committed Bytes In Use']
    }
    elseif ($commitLimitBytes -gt 0) { 100.0 * $committedBytes / $commitLimitBytes }
    else { 0.0 }

    $cycleHasSignal = $false
    $values = foreach ($channel in $channels) {
        $valueMilliWatts = 0.0
        if ($currentPower.ContainsKey($channel) -and $currentPower[$channel] -gt 0) {
            $valueMilliWatts = $currentPower[$channel]
        }
        elseif (
            $previousEnergy.ContainsKey($channel) -and
            $previousTime.ContainsKey($channel) -and
            $currentEnergy.ContainsKey($channel) -and
            $currentTime.ContainsKey($channel)
        ) {
            $deltaEnergy = $currentEnergy[$channel] - $previousEnergy[$channel]
            $deltaTime = $currentTime[$channel] - $previousTime[$channel]
            if ($deltaTime -gt 0) {
                $valueMilliWatts = ($deltaEnergy / $deltaTime) / $nanoJoulesPerMillisecondToMilliWatts
            }
        }
        if ($valueMilliWatts -gt 0) {
            $cycleHasSignal = $true
        }
        [math]::Round($valueMilliWatts, 3)
    }

    $memoryValues = @(
        [math]::Round($physicalMemoryUtilizationPercent, 3),
        [math]::Round($physicalMemoryUsedBytes),
        [math]::Round($physicalMemoryTotalBytes),
        [math]::Round($committedBytes),
        [math]::Round($commitLimitBytes),
        [math]::Round($percentCommittedBytesInUse, 3),
        [math]::Round($availableBytes)
    )
    "$sample,$timestamp,$elapsed,$($memoryValues -join ','),$($values -join ',')" |
        Out-File -FilePath $OutFile -Append -Encoding ascii
    $previousEnergy = $currentEnergy
    $previousTime = $currentTime

    if ($cycleHasSignal) {
        $emptyCycles = 0
    }
    else {
        $emptyCycles++
        if ($emptyCycles -ge $maxEmptyCycles) {
            $abortReason = "NO_SIGNAL: Energy Meter counters returned all zeros for $maxEmptyCycles consecutive cycles."
            break
        }
    }
}

if ($abortReason) {
    "ABORT,$sample,$abortReason" | Out-File -FilePath $doneFile -Encoding ascii
}
else {
    "OK,$sample" | Out-File -FilePath $doneFile -Encoding ascii
}