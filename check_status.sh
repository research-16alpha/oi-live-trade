#!/bin/bash

# Status check script for Option Chain Monitor

echo "=========================================="
echo "Option Chain Monitor - Status Check"
echo "=========================================="
echo ""

# Check if process is running
PID=$(pgrep -f "automate_oi_monitor.py")
if [ -z "$PID" ]; then
    echo "Status: ❌ Not Running"
else
    echo "Status: ✅ Running"
    echo "Process ID: $PID"
    echo ""
    echo "Process details:"
    ps -p "$PID" -o pid,user,etime,command
fi

echo ""

# Check Launch Agent status
PLIST_NAME="com.oi.monitor.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

if [ -f "$PLIST_DEST" ]; then
    echo "Launch Agent: ✅ Installed"
    echo "Location: $PLIST_DEST"
    echo ""
    echo "Scheduled start: 9:15 AM (Monday-Friday)"
    echo "Auto-stop: 3:30 PM IST (handled by script)"
else
    echo "Launch Agent: ❌ Not Installed"
    echo "Run ./setup_scheduler.sh to install"
fi

echo ""

# Check recent logs
LOG_FILE="oi_monitor.log"
if [ -f "$LOG_FILE" ]; then
    echo "Recent log entries (last 5 lines):"
    echo "-----------------------------------"
    tail -5 "$LOG_FILE"
else
    echo "No log file found."
fi

echo ""

