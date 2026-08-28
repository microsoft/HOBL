param(
    [string]$logFile = ""
)

# Require PowerShell > 7
$required = [version]"7.0"
if (-not $PSVersionTable.PSVersion) {
    Write-Host "Cannot determine PowerShell version; aborting." -ForegroundColor Red
    Exit 1
}
if ([version]$PSVersionTable.PSVersion -le $required) {
    Write-Host "This script requires PowerShell greater than $required. Current: $($PSVersionTable.PSVersion)" -ForegroundColor Yellow
    Write-Host "Please install PowerShell 7 or later from https://aka.ms/powershell" -ForegroundColor Yellow
    Exit 1
}

$scriptDrive = Split-Path -Qualifier $PSScriptRoot
if (-not (Test-Path "$scriptDrive\hobl_data")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_data" -ForegroundColor Red
    Exit 1
}
if (-not (Test-Path "$scriptDrive\hobl_bin")) {
    Write-Host " ERROR - Required directory not found: $scriptDrive\hobl_bin" -ForegroundColor Red
    Exit 1
}
if (-not $logFile) { $logFile = "$scriptDrive\hobl_data\vscode_prep.log" }
$vscodePath = "$scriptDrive\vscode"

# Ensure log directory exists
$logDir = Split-Path $logFile -Parent
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

# Set execution policy for current process (required for pyenv's Expand-Archive)
$executionPolicy = Get-ExecutionPolicy -Scope Process
if ($executionPolicy -eq "Restricted" -or $executionPolicy -eq "Undefined") {
    Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope Process -Force -ErrorAction Stop
}

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Determine processor architecture and set appropriate variables
$osInfo = Get-CimInstance Win32_OperatingSystem
$arch = $osInfo.OSArchitecture
$processorArch = $env:PROCESSOR_ARCHITECTURE

if ($arch -eq "64-bit" -and $processorArch -eq "AMD64") {
    $isARM64 = $false
    $vsArchParam = "x64"
    $vsHostArchParam = "x64"
    $logSuffix = "x64"
    $vsProduct = "BuildTools"
    $pythonVersion = "3.12.10"
} elseif ($arch -match "ARM" -or $processorArch -match "ARM") {
    $isARM64 = $true
    $vsArchParam = "arm64"
    $vsHostArchParam = "arm64"
    $logSuffix = "ARM64"
    $vsProduct = "Community"
    $pythonVersion = "3.12.10-arm"
} else {
    Write-Host " ERROR - Unsupported architecture: $arch (Processor: $processorArch)" -ForegroundColor Red
    Add-Content -Path $logFile -encoding utf8 " ERROR - Unsupported architecture: $arch (Processor: $processorArch)"
    Exit 1
}

# Update log file name to include architecture
$logFile = $logFile -replace "\.log$", "_$($logSuffix.ToLower()).log"

function log {
    [CmdletBinding()] Param([Parameter(ValueFromPipeline)] $msg)
    process {
        if ($msg -Match " ERROR - ") {
            Write-Host $msg -ForegroundColor Red
        } else {
            Write-Host $msg
        }
        Add-Content -Path $logFile -encoding utf8 "$msg"
    }
}

function check {
    param($code)
    if ($code -ne 0) {
        " ERROR - Last command failed." | log
        Exit $code
    }
}

function checkWinget {
    param($code)
    # Winget exit codes:
    # 0 = Success
    # -1978335189 (0x8A15002B) = Already installed
    # -1978335215 (0x8A150011) = No applicable upgrade found
    # Other non-zero = Actual error
    if ($code -eq 0) {
        "Winget command succeeded" | log
    } elseif ($code -eq -1978335189) {
        "Package already installed (this is OK)" | log
    } elseif ($code -eq -1978335215) {
        "No applicable upgrade found (this is OK)" | log
    } else {
        " ERROR - Winget command failed with exit code: $code" | log
        Exit $code
    }
}

function checkGitClone {
    param($code, $repoPath)
    if ($code -eq 0) {
        "Git clone succeeded" | log
    } elseif ($code -eq 128 -and (Test-Path $repoPath)) {
        "Repository already exists (this is OK)" | log
    } else {
        " ERROR - Git clone failed with exit code: $code" | log
        Exit $code
    }
}

function getVSVersion {
    param([string]$product)

    $vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path $vswhere)) {
        $vswhere = "${env:ProgramFiles}\Microsoft Visual Studio\Installer\vswhere.exe"
        if (-not (Test-Path $vswhere)) {
            return $null
        }
    }

    try {
        $productFilter = if ($product -eq "BuildTools") { "Microsoft.VisualStudio.Product.BuildTools" } else { "Microsoft.VisualStudio.Product.Community" }
        $instances = & $vswhere -products $productFilter -format json | ConvertFrom-Json

        if ($instances) {
            $instance = $instances | Select-Object -First 1
            return @{
                Version     = $instance.installationVersion
                DisplayName = $instance.displayName
                Path        = $instance.installationPath
            }
        }
    } catch {
        return $null
    }

    return $null
}

Set-Content -Path $logFile -encoding utf8 "-- vscode prep started ($logSuffix version)"

"Detected architecture: $arch (Processor: $processorArch)" | log

# Verify winget is available
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    " ERROR - winget is not available. Install App Installer from Microsoft Store or visit https://aka.ms/getwinget" | log
    Exit 1
}

# -------------------------------------------------------------------
# Install Git
# -------------------------------------------------------------------
# --- Remove the msstore source before any winget install so a broken pinned
# certificate on that source cannot fail the command (winget 0x8a15005e /
# -1978335138) behind an SSL-inspecting proxy. All needed packages are on 'winget'. ---
try {
    if ((winget source list 2>$null) -match "msstore") {
        "Removing msstore winget source to avoid pinned-certificate failures (0x8a15005e)" | log
        winget source remove msstore 2>&1 | log
    }
} catch {
    "Could not remove msstore source (continuing): $($_.Exception.Message)" | log
}

"-- Installing Git" | log
winget install --id Git.Git --source winget --accept-source-agreements --accept-package-agreements
checkWinget($lastexitcode)
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

"-- Verifying git installation" | log
git --version 2>&1 | log
check($lastexitcode)

# -------------------------------------------------------------------
# Install Node.js 24.18.0
# -------------------------------------------------------------------
"-- Installing Node.js 24.18.0 ($logSuffix)" | log
if ($isARM64) {
    winget install --id OpenJS.NodeJS.LTS --version 24.18.0 --architecture arm64 --source winget --accept-source-agreements --accept-package-agreements --force
} else {
    winget install --id OpenJS.NodeJS.LTS --version 24.18.0 --architecture x64 --source winget --accept-source-agreements --accept-package-agreements --force
}
checkWinget($lastexitcode)
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

"-- Verifying Node.js installation" | log
$installedNodeVersion = (node --version 2>&1).Trim()
$installedNodeVersion | log
check($lastexitcode)
if ($installedNodeVersion -ne "v24.18.0") {
    " ERROR - Node.js version is $installedNodeVersion, expected v24.18.0" | log
    Exit 1
}
npm --version 2>&1 | log

# -------------------------------------------------------------------
# Install Python via pyenv-win
# -------------------------------------------------------------------
"-- Installing pyenv-win for Python version management" | log
try {
    Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "$env:TEMP\install-pyenv-win.ps1"
    & "$env:TEMP\install-pyenv-win.ps1"
    "pyenv-win installation completed" | log
} catch {
    " ERROR - Failed to install pyenv-win: $($_.Exception.Message)" | log
    Exit 1
}

# Setup pyenv PATH
$pyenvRoot = "$env:USERPROFILE\.pyenv"
$env:PATH = "$pyenvRoot\pyenv-win\bin;$pyenvRoot\pyenv-win\shims;$env:PATH"

# --- Install Python via pyenv (conditional — DO NOT use -f) ---
# Force-reinstall (`-f`) wipes the pyenv version directory including any packages
# installed by other scenarios that share this Python version. VS Code only needs
# the interpreter (for node-gyp during native module builds) so no venv is
# required — but we must avoid wiping it.
"-- Installing Python $pythonVersion via pyenv" | log
$installedVersions = (pyenv versions --bare 2>$null) -split "`n" | ForEach-Object { $_.Trim() }
if ($installedVersions -notcontains $pythonVersion) {
    "Installing Python $pythonVersion via pyenv..." | log
    pyenv install $pythonVersion
    check($lastexitcode)
} else {
    "Python $pythonVersion already installed via pyenv — preserving existing install" | log
}

"Setting Python $pythonVersion as global version" | log
pyenv global $pythonVersion
check($lastexitcode)

# Verify python via pyenv which (not Get-Command which returns the shim)
$pythonExeRaw = pyenv which python 2>$null
if ($pythonExeRaw) {
    $pythonExe = $pythonExeRaw.Trim()
    if (Test-Path $pythonExe) {
        "Using Python: $pythonExe" | log
        & $pythonExe --version 2>&1 | log
    } else {
        " ERROR - pyenv which python returned non-existent path: $pythonExe" | log
        Exit 1
    }
} else {
    " ERROR - pyenv which python failed" | log
    Exit 1
}

# -------------------------------------------------------------------
# Install Visual Studio Build Tools / Community
# -------------------------------------------------------------------
"-- Installing Visual Studio $vsProduct ($logSuffix)" | log

$scriptDir = Split-Path -Parent $PSCommandPath

if ($isARM64) {
    $installerUrl = "https://aka.ms/vs/17/release/vs_community.exe"
    $installerPath = "$env:TEMP\vs_community.exe"
    $productName = "VS Community"
    $vsconfigPath = Join-Path $scriptDir ".vsconfig_arm64"
} else {
    $installerUrl = "https://aka.ms/vs/17/release/vs_buildtools.exe"
    $installerPath = "$env:TEMP\vs_buildtools.exe"
    $productName = "VS Build Tools"
    $vsconfigPath = Join-Path $scriptDir ".vsconfig_x64"
}

if (-not (Test-Path $vsconfigPath)) {
    " ERROR - .vsconfig file not found at: $vsconfigPath" | log
    Exit 1
}
"Using .vsconfig file: $vsconfigPath" | log

# Check if VS is already installed
$existingVS = getVSVersion -product $vsProduct
if ($existingVS -and $existingVS.Path) {
    "Found existing $productName at: $($existingVS.Path) (v$($existingVS.Version))" | log

    # Use shared installer to modify existing installation
    $sharedInstaller = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\setup.exe"
    if (Test-Path $sharedInstaller) {
        "Using existing VS installer to apply .vsconfig" | log
        $installerPath = $sharedInstaller
    } else {
        "Shared installer not found, downloading new installer..." | log
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
    }

    $installArgs = @(
        "modify"
        "--installPath", "`"$($existingVS.Path)`""
        "--quiet"
        "--config", "`"$vsconfigPath`""
    )
} else {
    "No existing $productName installation found, downloading installer..." | log
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing

    if (-not (Test-Path $installerPath)) {
        " ERROR - $productName installer not found after download" | log
        Exit 1
    }

    $installArgs = @(
        "install"
        "--quiet"
        "--wait"
        "--config", "`"$vsconfigPath`""
    )
}

"$productName install args: $($installArgs -join ' ')" | log
"Starting $productName installation (this will wait for completion)..." | log

$vsStdOut = Join-Path $logDir "vs_install_vscode_stdout_$($logSuffix.ToLower()).log"
$vsStdErr = Join-Path $logDir "vs_install_vscode_stderr_$($logSuffix.ToLower()).log"
$process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru -RedirectStandardOutput $vsStdOut -RedirectStandardError $vsStdErr
$exitCode = $process.ExitCode
"$productName installer completed with exit code: $exitCode" | log

if ($exitCode -eq 3010) {
    "Installation successful but may require reboot for full functionality" | log
} elseif ($exitCode -ne 0) {
    " ERROR - $productName installation failed with exit code: $exitCode" | log
    Exit $exitCode
}

# Clean up downloaded installer
if ($installerPath -like "$env:TEMP\*" -and (Test-Path $installerPath)) {
    Remove-Item $installerPath -ErrorAction SilentlyContinue
}

# Verify VS installation
$vsInfo = getVSVersion -product $vsProduct
if (-not $vsInfo -or -not $vsInfo.Path) {
    " ERROR - Visual Studio $vsProduct not found after installation" | log
    Exit 1
}
"Verified $productName at: $($vsInfo.Path) (v$($vsInfo.Version))" | log

# Initialize VS environment
"-- Initializing Visual Studio environment ($logSuffix)" | log
$actualVSPath = $vsInfo.Path
$vsDevCmd = Join-Path $actualVSPath "Common7\Tools\VsDevCmd.bat"

if (-not (Test-Path $vsDevCmd)) {
    " ERROR - VsDevCmd.bat not found at: $vsDevCmd" | log
    Exit 1
}

$tempBat = "$env:TEMP\vsinit_$($logSuffix.ToLower()).bat"
Set-Content -Path $tempBat -Value @"
@echo off
call "$vsDevCmd" -arch=$vsArchParam -host_arch=$vsHostArchParam > nul 2>&1
set
"@

$envVars = cmd /c "$tempBat" 2>nul
Remove-Item $tempBat -ErrorAction SilentlyContinue

$envVars | ForEach-Object {
    if ($_ -match "^([^=]+)=(.*)$") {
        $name = $matches[1]
        $value = $matches[2]
        if ($name -match "^(PATH|INCLUDE|LIB|LIBPATH|VS.*|VC.*|WindowsSDK.*|Platform.*|PROCESSOR_ARCHITECTURE)$") {
            Set-Item "env:$name" $value -ErrorAction SilentlyContinue
        }
    }
}
"Visual Studio environment initialized" | log

# Refresh PATH after all installations
$Env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# -------------------------------------------------------------------
# Clone and checkout VS Code repository
# -------------------------------------------------------------------
"-- Cloning VS Code repository to $vscodePath" | log
Set-Location $scriptDrive\
if (Test-Path $vscodePath) {
    "VS Code directory already exists, removing..." | log
    Remove-Item -Recurse -Force $vscodePath
}

git clone https://github.com/microsoft/vscode.git
checkGitClone $lastexitcode "$vscodePath"

"-- Checking out VS Code version 1.132.0" | log
Set-Location $vscodePath
git checkout 1.132.0
check($lastexitcode)

# -------------------------------------------------------------------
# Install npm packages (so run iterations only measure compile)
# -------------------------------------------------------------------
"-- Installing npm packages (this may take several minutes)..." | log

# Ensure pyenv Python is on PATH and set for Node.js native module builds
$env:PATH = "$pyenvRoot\pyenv-win\bin;$pyenvRoot\pyenv-win\shims;$env:PATH"
$env:PYTHON = $pythonExe
$env:PYTHONHOME = (Split-Path $pythonExe -Parent)
"PYTHON=$env:PYTHON" | log
"PYTHONHOME=$env:PYTHONHOME" | log

npm install --loglevel=error
check($lastexitcode)
"npm install completed" | log

"-- vscode prep completed ($logSuffix version)" | log
Exit 0
