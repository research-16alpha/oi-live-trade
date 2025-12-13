@echo off
REM Windows batch file to start Option Chain Monitor
REM This file is used by Windows Task Scheduler

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM Load credentials if credentials.sh exists (convert to .bat format)
if exist credentials.bat (
    call credentials.bat
)

REM Activate virtual environment
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found. Using system Python.
)

REM Run the monitor
python automate_oi_monitor.py

REM Keep window open if there's an error (for debugging)
if errorlevel 1 (
    echo.
    echo Monitor exited with error. Press any key to close...
    pause >nul
)

