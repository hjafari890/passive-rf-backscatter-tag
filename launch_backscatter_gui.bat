@echo off
setlocal enabledelayedexpansion
title Backscatter Tag SDR Detection and Analysis Suite
echo =====================================================================
echo  Launching Backscatter Tag SDR Detection Suite (Native Tkinter + Matplotlib)
echo  Hardware Target: NI USRP-2900 / B200 (USB 3.0) or Mock Streaming
echo =====================================================================
echo.

cd /d "%~dp0"

:: 1. Discover Python executable (prefer local venv, Radioconda, then system python / py launcher)
set "PY_CMD="
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0venv\Scripts\python.exe"
) else if exist "%USERPROFILE%\radioconda\python.exe" (
    set "PY_CMD=%USERPROFILE%\radioconda\python.exe"
) else if exist "C:\radioconda\python.exe" (
    set "PY_CMD=C:\radioconda\python.exe"
) else if exist "%LOCALAPPDATA%\radioconda\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\radioconda\python.exe"
) else (
    where python >nul 2>nul
    if !ERRORLEVEL! EQU 0 (
        set "PY_CMD=python"
    ) else (
        where py >nul 2>nul
        if !ERRORLEVEL! EQU 0 (
            set "PY_CMD=py -3"
        )
    )
)


if not defined PY_CMD (
    echo [ERROR] No Python interpreter found in PATH or %%USERPROFILE%%\radioconda.
    pause
    exit /b 1
)

:: 2. Determine target GUI script path
set "GUI_SCRIPT=software\backscatter_gui_app.py"
if not exist "%GUI_SCRIPT%" (
    if exist "ant test\03_sdr_software\backscatter_gui_app.py" (
        set "GUI_SCRIPT=ant test\03_sdr_software\backscatter_gui_app.py"
    )
)

echo Using Python: "%PY_CMD%"
echo Target Script: "%GUI_SCRIPT%"
echo.

"%PY_CMD%" "%GUI_SCRIPT%" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with code %ERRORLEVEL%.
    pause
)
