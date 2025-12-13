@echo off
REM Batch file wrapper for PowerShell scheduler setup
REM This makes it easier to run the setup

echo ==========================================
echo Option Chain Monitor - Windows Setup
echo ==========================================
echo.

REM Check if PowerShell is available
where powershell >nul 2>&1
if errorlevel 1 (
    echo Error: PowerShell not found. Please install PowerShell.
    pause
    exit /b 1
)

REM Run the PowerShell script
echo Running PowerShell setup script...
echo.

powershell.exe -ExecutionPolicy Bypass -File "%~dp0setup_windows_scheduler.ps1"

if errorlevel 1 (
    echo.
    echo Setup failed. Please check the errors above.
    pause
    exit /b 1
)

echo.
echo Setup complete! Press any key to exit...
pause >nul

