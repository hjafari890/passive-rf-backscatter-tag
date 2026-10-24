@echo off
setlocal enabledelayedexpansion
title Launch GNU Radio Backscatter Tag Detector (NI USRP-2900)
color 0B

echo =====================================================================
echo  Launching Backscatter Tag GNU Radio QT Dashboard
echo  Hardware Target: NI USRP-2900 / B200 (Full-Duplex TX+RX)
echo =====================================================================
echo.

cd /d "%~dp0"

:: Discover Radioconda directory
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


if defined RADIOCONDA_DIR (
    set "PATH=%RADIOCONDA_DIR%;%RADIOCONDA_DIR%\Scripts;%RADIOCONDA_DIR%\Library\bin;!PATH!"
    set "PYTHONPATH=%RADIOCONDA_DIR%\Lib\site-packages;!PYTHONPATH!"
    set "PY_CMD=%RADIOCONDA_DIR%\python.exe"
) else (
    set "PY_CMD=python"
)

set "SCRIPT_FILE=software\gnuradio\backscatter_detector_gnuradio.py"
if not exist "%SCRIPT_FILE%" (
    set "SCRIPT_FILE=ant test\03_sdr_software\gnuradio\backscatter_detector_gnuradio.py"
)

echo Starting GNU Radio Dashboard:
echo   %SCRIPT_FILE%
echo.

"%PY_CMD%" "%SCRIPT_FILE%" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with code %ERRORLEVEL%.
    pause
)
