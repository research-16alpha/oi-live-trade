# Windows Setup Guide - 24/7 PC

Complete guide to set up the Option Chain Monitor on a Windows PC that runs 24/7.

## Prerequisites

1. **Python 3.7+** installed
2. **Git** installed (optional, for cloning from GitHub)
3. **Administrator access** (for Task Scheduler setup)

## Step 1: Get the Code

### Option A: Clone from GitHub (Recommended)

```cmd
cd C:\Users\YourUsername\Desktop
git clone https://github.com/research-16alpha/oi-live-trade.git
cd oi-live-trade
```

### Option B: Copy Files Manually

1. Copy the entire `Automate_OI` folder to your Windows PC
2. Navigate to the folder in Command Prompt

## Step 2: Setup Python Environment

```cmd
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Step 3: Configure Database Credentials

Edit `credentials.bat` with your database details:

```cmd
notepad credentials.bat
```

Update these variables:
- `DB_TYPE` - `mysql` or `sqlserver`
- `DB_SERVER` - Your database server address
- `DB_DATABASE` - Database name
- `DB_USER` - Username
- `DB_PASSWORD` - Password
- `DB_PORT` - Port (3306 for MySQL, 1433 for SQL Server)
- `TICKER` - Ticker symbol (e.g., `NIFTY`)

## Step 4: Test Connection

```cmd
venv\Scripts\activate
python test_connection.py
```

If successful, you'll see: `✓ Connection successful!`

## Step 5: Setup Auto-Start Scheduler

### Method 1: PowerShell Script (Recommended)

**Right-click PowerShell and select "Run as Administrator"**, then:

```powershell
cd C:\Users\YourUsername\Desktop\oi-live-trade
.\setup_windows_scheduler.ps1
```

Or use the batch file wrapper:

```cmd
# Right-click Command Prompt and "Run as Administrator"
setup_windows_scheduler.bat
```

### Method 2: Manual Task Scheduler Setup

1. Open **Task Scheduler** (search in Start menu)

2. Click **"Create Basic Task"**

3. **General Tab:**
   - Name: `OI-Trading-Monitor-Weekly`
   - Description: `Starts Option Chain Monitor at 9:15 AM IST on weekdays`
   - Check: "Run whether user is logged on or not"
   - Check: "Run with highest privileges"

4. **Triggers Tab:**
   - Click "New"
   - Begin: "On a schedule"
   - Settings: "Weekly"
   - Days: Check Monday, Tuesday, Wednesday, Thursday, Friday
   - Time: **9:15 AM** (adjust for your timezone - IST is UTC+5:30)
   - Click OK

5. **Actions Tab:**
   - Action: "Start a program"
   - Program/script: `C:\Users\YourUsername\Desktop\oi-live-trade\start_monitor_windows.bat`
   - Start in: `C:\Users\YourUsername\Desktop\oi-live-trade`
   - Click OK

6. **Conditions Tab:**
   - Uncheck "Start the task only if the computer is on AC power"
   - Check "Start the task only if the following network connection is available"

7. **Settings Tab:**
   - Check "Allow task to be run on demand"
   - Check "Run task as soon as possible after a scheduled start is missed"
   - If the task fails, restart every: `10 minutes`
   - Attempt to restart up to: `3 times`

8. Click **OK** and enter your Windows password

### Auto-Start After Reboot (Optional)

Create another task for auto-start after reboot:

1. **Create Basic Task** → Name: `OI-Trading-Monitor-Startup`

2. **Trigger:** "When the computer starts"

3. **Action:** Same as above (`start_monitor_windows.bat`)

4. **Settings:** Add delay of 2 minutes (to ensure network is ready)

## Step 6: Verify Setup

### Check Tasks in Task Scheduler

1. Open Task Scheduler
2. Look for tasks starting with `OI-Trading-Monitor`
3. Right-click → **Run** to test manually

### Check Logs

```cmd
cd C:\Users\YourUsername\Desktop\oi-live-trade
type monitor.log
type monitor_error.log
```

## Important Notes

### Timezone Adjustment

⚠️ **Windows Task Scheduler uses your LOCAL timezone, not IST!**

- **IST = UTC+5:30**
- If your PC is in a different timezone, adjust the time in Task Scheduler

**Examples:**
- If PC is in **EST (UTC-5)**: 9:15 AM IST = 10:45 PM EST (previous day)
- If PC is in **PST (UTC-8)**: 9:15 AM IST = 7:45 PM PST (previous day)
- If PC is in **IST**: Use 9:15 AM directly

**To adjust:**
1. Open Task Scheduler
2. Find `OI-Trading-Monitor-Weekly`
3. Double-click → Triggers tab
4. Edit the time to match 9:15 AM IST in your timezone

### Python Script Handles IST

The Python script (`automate_oi_monitor.py`) checks IST time internally, so:
- It will only trade during 9:15 AM - 3:29 PM IST
- It will stop at 3:30 PM IST automatically
- It will skip weekends automatically

So even if Task Scheduler starts it at the wrong time, the Python script will wait until the correct IST time.

## Manual Control

### Start Monitor Manually

```cmd
cd C:\Users\YourUsername\Desktop\oi-live-trade
start_monitor_windows.bat
```

Or:
```cmd
venv\Scripts\activate
python automate_oi_monitor.py
```

### Stop Monitor

Press `Ctrl+C` in the window, or:
```cmd
taskkill /F /IM python.exe /FI "WINDOWTITLE eq automate_oi_monitor*"
```

### Check if Running

```cmd
tasklist | findstr python
```

## Troubleshooting

### Task Not Starting

1. **Check Task Scheduler:**
   - Open Task Scheduler
   - Find your task
   - Check "Last Run Result" - should be `0x0` (success)
   - If error, check "History" tab

2. **Check Logs:**
   ```cmd
   type monitor.log
   type monitor_error.log
   ```

3. **Test Manually:**
   ```cmd
   start_monitor_windows.bat
   ```

### Python Not Found

Make sure Python is in your PATH:
```cmd
python --version
```

If not found, add Python to PATH or use full path in batch file.

### Virtual Environment Not Found

Recreate it:
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Database Connection Issues

1. Check `credentials.bat` has correct values
2. Test connection: `python test_connection.py`
3. Check firewall allows connection to database server

## Uninstall

To remove the scheduled tasks:

```powershell
# Run as Administrator
Unregister-ScheduledTask -TaskName "OI-Trading-Monitor-Weekly" -Confirm:$false
Unregister-ScheduledTask -TaskName "OI-Trading-Monitor-Startup" -Confirm:$false
```

Or manually delete from Task Scheduler.

## What Happens Automatically

✅ **Monday-Friday 9:15 AM**: Monitor starts automatically  
✅ **9:15 AM - 3:29 PM**: Trading active  
✅ **3:30 PM**: Monitor stops automatically  
✅ **After Reboot**: Monitor starts (if during trading hours)  
✅ **Weekends**: No automatic start (script skips weekends)  
✅ **Portfolio Updates**: Auto-synced to GitHub → Streamlit Cloud

## Result

🎉 Your 24/7 Windows PC will now:
- Start monitoring automatically every Monday at 9:15 AM
- Continue running even after reboots
- Keep your Streamlit dashboard updated in real-time!

