@echo off
REM Copyright (c) Microsoft. All rights reserved.
REM Licensed under the MIT license. See LICENSE file in the project root for full license information.

pushd %~dp0
..\..\downloads\python_embed\Scripts\pip.exe %*
