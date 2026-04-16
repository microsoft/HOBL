@echo off
REM Copyright (c) Microsoft. All rights reserved.
REM Licensed under the MIT license. See LICENSE file in the project root for full license information.

SetLocal EnableDelayedExpansion

set CLEAN=false
set BUILD_ARCHIVE=false
for %%x in (%*) do (
    if "%%x"=="-c" set CLEAN=true
    if "%%x"=="-b" set BUILD_ARCHIVE=true
)

set PYTHON_VERSION=3.11.9
set PYTHON_DOWNLOAD_URL="https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip"

REM https://pip.pypa.io/en/stable/installation/#get-pip-py
set GET_PIP_DOWNLOAD_URL="https://bootstrap.pypa.io/get-pip.py"

pushd %~dp0
set PYTHON_DIR=..\..\downloads\python_embed
set HOBL_PY=..\..\core\hobl.py

if not exist %PYTHON_DIR% (
    set CLEAN=true
)

if %CLEAN% == true (
    if exist %PYTHON_DIR% rmdir /s /q %PYTHON_DIR%
    if exist %PYTHON_DIR% (
        echo Failed to delete %PYTHON_DIR%.
        goto ERROR
    )
    mkdir %PYTHON_DIR%

    echo Setting up Python and pip
    pushd %PYTHON_DIR%

    echo Downloading Python
    curl --output python-archive.zip %PYTHON_DOWNLOAD_URL%
    tar -xf python-archive.zip
    if %errorlevel% neq 0 goto ERROR
    del python-archive.zip
    echo Python downloaded and extracted successfully

    for %%f in (python*._pth) do (
        findstr /R /V "^#" %%f > temp_%%~nxf
        move /Y temp_%%~nxf %%f > nul

        rem Append new lines
        >>%%f echo import site
        >>%%f echo Lib
        >>%%f echo Lib\site-packages
    )

    echo Installing pip
    curl --output get-pip.py %GET_PIP_DOWNLOAD_URL%
    .\python.exe get-pip.py --no-warn-script-location
    del get-pip.py
    .\python.exe -m pip install pip==25.2 --no-warn-script-location
    echo Pip set up successful

    popd
) else (
    echo Python setup already exists at %PYTHON_DIR%. Skipping setup
)

REM Install setuptools and wheel
echo Installing setuptools wheel
%PYTHON_DIR%\python.exe -m pip install setuptools wheel --no-warn-script-location

for %%f in ("%PYTHON_DIR%\python*._pth") do (
    echo Disabling %%f
    ren "%%f" "%%~nxf.disabled"
)

echo Installing requirements.txt
%PYTHON_DIR%\python.exe -Im pip install --requirement ..\..\requirements.txt --no-warn-script-location
if %errorlevel% neq 0 goto ERROR

for %%f in ("%PYTHON_DIR%\python*._pth.disabled") do (
    echo Enabling %%f
    ren "%%f" "%%~nf"
)

REM Check if hobl can run
%PYTHON_DIR%\python.exe %HOBL_PY% -d "web teams"
if %errorlevel% neq 0 goto ERROR
echo Hobl command successful

echo Adding firewall entry if needed
powershell.exe Unblock-File -Path .\firewall_add.ps1
powershell.exe .\firewall_add.ps1

if %BUILD_ARCHIVE% == true (
    echo Building archive
    powershell.exe Compress-Archive -Path "%PYTHON_DIR%\*" -DestinationPath "%PYTHON_DIR%.zip" -Force
    if %errorlevel% neq 0 goto ERROR
)

goto END

:ERROR
echo Error occurred, please check the output for details
exit /b 1

:END
exit /b 0
