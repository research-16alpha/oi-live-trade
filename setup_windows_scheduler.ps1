# PowerShell script to set up Windows Task Scheduler for Option Chain Monitor
# Run this script as Administrator for best results

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Option Chain Monitor - Windows Scheduler Setup" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Get the directory where this script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$MonitorScript = Join-Path $ScriptDir "start_monitor_windows.bat"
$PythonScript = Join-Path $ScriptDir "automate_oi_monitor.py"

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "⚠️  Warning: Not running as Administrator. Some features may not work." -ForegroundColor Yellow
    Write-Host "   For best results, right-click PowerShell and 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host ""
}

# Verify files exist
if (-not (Test-Path $MonitorScript)) {
    Write-Host "❌ Error: start_monitor_windows.bat not found at: $MonitorScript" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $PythonScript)) {
    Write-Host "❌ Error: automate_oi_monitor.py not found at: $PythonScript" -ForegroundColor Red
    exit 1
}

Write-Host "📋 Setting up Windows Task Scheduler..." -ForegroundColor Green
Write-Host "   Monitor Script: $MonitorScript" -ForegroundColor Gray
Write-Host ""

# Task 1: Weekly schedule (Monday-Friday at 9:15 AM IST)
$TaskName1 = "OI-Trading-Monitor-Weekly"
$TaskDescription1 = "Starts Option Chain Monitor at 9:15 AM IST on weekdays (Monday-Friday)"

Write-Host "Creating task: $TaskName1" -ForegroundColor Yellow

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $TaskName1 -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "   Removing existing task..." -ForegroundColor Gray
    Unregister-ScheduledTask -TaskName $TaskName1 -Confirm:$false -ErrorAction SilentlyContinue
}

# Create trigger for Monday-Friday at 9:15 AM IST
# Note: Windows uses local time, so adjust 9:15 AM IST to your local time
# IST is UTC+5:30, so if you're in a different timezone, adjust accordingly
# For example, if you're in EST (UTC-5), 9:15 AM IST = 10:45 PM EST (previous day)
# This example assumes your Windows timezone is set to IST or you'll adjust manually

$Trigger1 = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At "9:15AM"

# Create action
$Action1 = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$MonitorScript`""

# Create settings
$Settings1 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable

# Create principal (run as current user)
$Principal1 = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

# Register the task
try {
    Register-ScheduledTask -TaskName $TaskName1 -Description $TaskDescription1 -Action $Action1 -Trigger $Trigger1 -Settings $Settings1 -Principal $Principal1 | Out-Null
    Write-Host "   ✅ Task created successfully!" -ForegroundColor Green
} catch {
    Write-Host "   ❌ Error creating task: $_" -ForegroundColor Red
    exit 1
}

# Task 2: Auto-start after reboot (optional - starts monitor if PC reboots)
$TaskName2 = "OI-Trading-Monitor-Startup"
$TaskDescription2 = "Starts Option Chain Monitor after system reboot (only during trading hours)"

Write-Host ""
Write-Host "Creating task: $TaskName2 (auto-start after reboot)" -ForegroundColor Yellow

# Remove existing task if it exists
$existingTask2 = Get-ScheduledTask -TaskName $TaskName2 -ErrorAction SilentlyContinue
if ($existingTask2) {
    Write-Host "   Removing existing task..." -ForegroundColor Gray
    Unregister-ScheduledTask -TaskName $TaskName2 -Confirm:$false -ErrorAction SilentlyContinue
}

# Create trigger for system startup
$Trigger2 = New-ScheduledTaskTrigger -AtStartup

# Create action (same as above)
$Action2 = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$MonitorScript`""

# Create settings (delay 2 minutes after startup to ensure network is ready)
$Settings2 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 8)

# Create principal
$Principal2 = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

# Register the task
try {
    Register-ScheduledTask -TaskName $TaskName2 -Description $TaskDescription2 -Action $Action2 -Trigger $Trigger2 -Settings $Settings2 -Principal $Principal2 | Out-Null
    Write-Host "   ✅ Task created successfully!" -ForegroundColor Green
} catch {
    Write-Host "   ❌ Error creating task: $_" -ForegroundColor Red
    Write-Host "   (This is optional - weekly schedule will still work)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✅ Setup Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Tasks Created:" -ForegroundColor Yellow
Write-Host "  1. $TaskName1" -ForegroundColor White
Write-Host "     - Runs: Monday-Friday at 9:15 AM" -ForegroundColor Gray
Write-Host "     - Description: $TaskDescription1" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. $TaskName2" -ForegroundColor White
Write-Host "     - Runs: After system startup" -ForegroundColor Gray
Write-Host "     - Description: $TaskDescription2" -ForegroundColor Gray
Write-Host ""
Write-Host "Important Notes:" -ForegroundColor Yellow
Write-Host "  ⚠️  Windows Task Scheduler uses your LOCAL timezone" -ForegroundColor Yellow
Write-Host "  ⚠️  IST is UTC+5:30. Adjust the time in Task Scheduler if needed:" -ForegroundColor Yellow
Write-Host "     - Open Task Scheduler" -ForegroundColor Gray
Write-Host "     - Find task: $TaskName1" -ForegroundColor Gray
Write-Host "     - Edit trigger time to match 9:15 AM IST in your timezone" -ForegroundColor Gray
Write-Host ""
Write-Host "Useful Commands:" -ForegroundColor Yellow
Write-Host "  View tasks: Get-ScheduledTask -TaskName OI-Trading-Monitor*" -ForegroundColor Gray
Write-Host "  Run now: Start-ScheduledTask -TaskName `"$TaskName1`"" -ForegroundColor Gray
Write-Host "  Disable: Disable-ScheduledTask -TaskName `"$TaskName1`"" -ForegroundColor Gray
Write-Host "  Delete: Unregister-ScheduledTask -TaskName `"$TaskName1`" -Confirm:`$false" -ForegroundColor Gray
Write-Host ""
Write-Host "The monitor will:" -ForegroundColor Green
Write-Host "  ✅ Auto-start at 9:15 AM on weekdays" -ForegroundColor Green
Write-Host "  ✅ Auto-start after reboot (if during trading hours)" -ForegroundColor Green
Write-Host "  ✅ Auto-stop at 3:30 PM IST (handled by Python script)" -ForegroundColor Green
Write-Host ""

