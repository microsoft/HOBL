@echo off
pushd %~dp0
if exist ..\downloads\python_embed\python.exe (
    ..\downloads\python_embed\python.exe ScenarioMaker.pyw %*
) else (
    python ScenarioMaker.pyw %*
)
