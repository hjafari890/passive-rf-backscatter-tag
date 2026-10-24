@echo off
setlocal enabledelayedexpansion
title Launch GNU Radio Companion (Visual Flowgraph Editor)
color 0E

echo =====================================================================
echo  Opening GNU Radio Companion (GRC) Flowgraph
echo  File: backscatter_detector_gnuradio.grc
echo =====================================================================
echo.

cd /d "%~dp0"

set "RADIOCONDA_DIR="
if exist "%USERPROFILE%\radioconda" (
    set "RADIOCONDA_DIR=%USERPROFILE%\radioconda"
) else if exist "C:\radioconda" (
    set "RADIOCONDA_DIR=C:\radioconda"
) else if exist "%LOCALAPPDATA%\radioconda" (
    set "RADIOCONDA_DIR=%LOCALAPPDATA%\radioconda"
) else if exist "C:\ProgramData\radioconda" (
    set "RADIOCONDA_DIR=C:\ProgramData\radioconda"
)

set "GRC_FILE=software\gnuradio\backscatter_detector_gnuradio.grc"
if not exist "%GRC_FILE%" (
    if exist "ant test\03_sdr_software\gnuradio\backscatter_detector_gnuradio.grc" (
        set "GRC_FILE=ant test\03_sdr_software\gnuradio\backscatter_detector_gnuradio.grc"
    )
)

if defined RADIOCONDA_DIR (
    set "PATH=%RADIOCONDA_DIR%;%RADIOCONDA_DIR%\Scripts;%RADIOCONDA_DIR%\Library\bin;!PATH!"
    set "PYTHONPATH=%RADIOCONDA_DIR%\Lib\site-packages;!PYTHONPATH!"
    echo Launching GRC via Radioconda...
    if exist "%RADIOCONDA_DIR%\Scripts\gnuradio-companion.exe" (
        start "" "%RADIOCONDA_DIR%\Scripts\gnuradio-companion.exe" "%GRC_FILE%"
    ) else if exist "%RADIOCONDA_DIR%\Library\bin\gnuradio-companion.exe" (
        start "" "%RADIOCONDA_DIR%\Library\bin\gnuradio-companion.exe" "%GRC_FILE%"
    ) else (
        start "" "%RADIOCONDA_DIR%\python.exe" "%RADIOCONDA_DIR%\Library\bin\gnuradio-companion.py" "%GRC_FILE%"
    )
) else (
    echo Launching GRC via system path...
    start "" gnuradio-companion "%GRC_FILE%"
)

