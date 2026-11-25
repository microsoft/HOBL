# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

param(
    [string]$run_idle_tasks = "0"
)

# Build Defender Cache to prevent abnormal activity during testing
if ($run_idle_tasks -ne "0"){
    start-process "c:\program files\Windows Defender\mpcmdrun.exe" ("BuildSFC -Timeout 7200000") -Wait
}

#  Build NGen Cache:
start-process "$env:windir\Microsoft.NET\Framework\v4.0.30319\ngen.exe" ("ExecuteQueuedItems") -Wait

# Run process Idle Tasks to prevent abnormal activity during testing
# Default is set to "1"
if ($run_idle_tasks -ne "0"){
    start "rundll32.exe" ("advapi32.dll,ProcessIdleTasks") -Wait
}
